"""
Stripe Balance & Top-Up Management Endpoints

This module provides endpoints for managing prepaid Stripe credits/balances:
- GET /stripe/balance - Check current balance
- POST /stripe/topup - Create Stripe Checkout Session for top-up
- GET /stripe/transactions - View transaction history
- POST /stripe/webhook - Handle Stripe webhook events (payment success, etc.)
"""

import os
import traceback
from datetime import datetime
from typing import Dict, List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from litellm._logging import verbose_logger
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

router = APIRouter()


class BalanceResponse(BaseModel):
    customer_id: str
    customer_type: str
    stripe_customer_id: str
    balance: float
    total_topups: float
    total_spent: float
    low_balance_threshold: Optional[float] = None


class TopUpRequest(BaseModel):
    amount: float  # Amount in USD
    success_url: str  # URL to redirect on success
    cancel_url: str  # URL to redirect on cancel
    customer_type: Optional[Literal["user_id", "team_id", "end_user_id"]] = "user_id"
    customer_id: Optional[str] = None  # If not provided, uses authenticated user


class TopUpResponse(BaseModel):
    checkout_session_id: str
    checkout_url: str


class TransactionResponse(BaseModel):
    transaction_id: str
    transaction_type: str
    amount: float
    balance_before: float
    balance_after: float
    description: Optional[str]
    created_at: datetime


async def get_or_create_balance_record(
    prisma_client, customer_type: str, customer_id: str, stripe_customer_id: str
) -> Dict:
    """Get existing balance record or create new one"""

    # Try to find existing record
    existing = await prisma_client.db.litellm_stripebalancetable.find_unique(
        where={
            "customer_type_customer_id": {
                "customer_type": customer_type,
                "customer_id": customer_id,
            }
        }
    )

    if existing:
        return existing

    # Create new balance record
    new_record = await prisma_client.db.litellm_stripebalancetable.create(
        data={
            "customer_type": customer_type,
            "customer_id": customer_id,
            "stripe_customer_id": stripe_customer_id,
            "balance": 0.0,
            "total_topups": 0.0,
            "total_spent": 0.0,
        }
    )

    return new_record


async def record_transaction(
    prisma_client,
    customer_type: str,
    customer_id: str,
    stripe_customer_id: str,
    transaction_type: str,
    amount: float,
    balance_before: float,
    balance_after: float,
    stripe_payment_intent_id: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict] = None,
):
    """Record a transaction in the transaction history"""

    await prisma_client.db.litellm_stripetransactiontable.create(
        data={
            "customer_type": customer_type,
            "customer_id": customer_id,
            "stripe_customer_id": stripe_customer_id,
            "transaction_type": transaction_type,
            "amount": amount,
            "balance_before": balance_before,
            "balance_after": balance_after,
            "stripe_payment_intent_id": stripe_payment_intent_id,
            "stripe_checkout_session_id": stripe_checkout_session_id,
            "request_id": request_id,
            "description": description,
            "metadata": metadata or {},
        }
    )


@router.get(
    "/stripe/balance",
    tags=["Stripe Balance"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=BalanceResponse,
)
async def get_balance(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Get current Stripe prepaid balance for authenticated user/team
    """
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Determine customer based on STRIPE_CHARGE_BY setting
    charge_by = os.getenv("STRIPE_CHARGE_BY", "end_user_id")

    if charge_by == "user_id":
        customer_id = user_api_key_dict.user_id
        customer_type = "user_id"
    elif charge_by == "team_id":
        customer_id = user_api_key_dict.team_id
        customer_type = "team_id"
    else:  # end_user_id
        customer_id = user_api_key_dict.end_user_id
        customer_type = "end_user_id"

    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail=f"No {customer_type} found for authenticated user"
        )

    # Create Stripe customer ID (can be customized)
    stripe_customer_id = f"{customer_type}_{customer_id}"

    # Get or create balance record
    balance_record = await get_or_create_balance_record(
        prisma_client, customer_type, customer_id, stripe_customer_id
    )

    return BalanceResponse(
        customer_id=balance_record["customer_id"],
        customer_type=balance_record["customer_type"],
        stripe_customer_id=balance_record["stripe_customer_id"],
        balance=balance_record["balance"],
        total_topups=balance_record["total_topups"],
        total_spent=balance_record["total_spent"],
        low_balance_threshold=balance_record.get("low_balance_threshold"),
    )


@router.post(
    "/stripe/topup",
    tags=["Stripe Balance"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=TopUpResponse,
)
async def create_topup_checkout(
    request: TopUpRequest,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Create a Stripe Checkout Session for topping up prepaid balance
    """
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Validate amount
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Top-up amount must be positive")

    # Determine customer
    if request.customer_id:
        customer_id = request.customer_id
        customer_type = request.customer_type
    else:
        charge_by = os.getenv("STRIPE_CHARGE_BY", "end_user_id")
        if charge_by == "user_id":
            customer_id = user_api_key_dict.user_id
            customer_type = "user_id"
        elif charge_by == "team_id":
            customer_id = user_api_key_dict.team_id
            customer_type = "team_id"
        else:
            customer_id = user_api_key_dict.end_user_id
            customer_type = "end_user_id"

    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail=f"No {customer_type} found"
        )

    stripe_customer_id = f"{customer_type}_{customer_id}"

    # Ensure balance record exists
    await get_or_create_balance_record(
        prisma_client, customer_type, customer_id, stripe_customer_id
    )

    # Create Stripe Checkout Session
    stripe_api_key = os.getenv("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="STRIPE_API_KEY not configured")

    stripe_base_url = os.getenv("STRIPE_API_BASE", "https://api.stripe.com")

    # Convert amount to cents
    amount_cents = int(request.amount * 100)

    # Create checkout session
    checkout_data = {
        "mode": "payment",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][product_data][name]": "LiteLLM Credits Top-Up",
        "line_items[0][price_data][unit_amount]": str(amount_cents),
        "line_items[0][quantity]": "1",
        "success_url": request.success_url,
        "cancel_url": request.cancel_url,
        "metadata[customer_type]": customer_type,
        "metadata[customer_id]": customer_id,
        "metadata[stripe_customer_id]": stripe_customer_id,
        "metadata[topup_amount]": str(request.amount),
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{stripe_base_url.rstrip('/')}/v1/checkout/sessions",
                data=checkout_data,
                headers={
                    "Authorization": f"Bearer {stripe_api_key}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()
            session_data = response.json()

        verbose_logger.debug(f"Created Stripe Checkout Session: {session_data}")

        return TopUpResponse(
            checkout_session_id=session_data["id"],
            checkout_url=session_data["url"],
        )

    except Exception as e:
        verbose_logger.error(f"Error creating Stripe Checkout Session: {e}")
        verbose_logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create checkout session: {str(e)}"
        )


@router.get(
    "/stripe/transactions",
    tags=["Stripe Balance"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=List[TransactionResponse],
)
async def get_transactions(
    limit: int = 50,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Get transaction history for authenticated user/team
    """
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Determine customer
    charge_by = os.getenv("STRIPE_CHARGE_BY", "end_user_id")

    if charge_by == "user_id":
        customer_id = user_api_key_dict.user_id
        customer_type = "user_id"
    elif charge_by == "team_id":
        customer_id = user_api_key_dict.team_id
        customer_type = "team_id"
    else:
        customer_id = user_api_key_dict.end_user_id
        customer_type = "end_user_id"

    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail=f"No {customer_type} found"
        )

    # Get transactions
    transactions = await prisma_client.db.litellm_stripetransactiontable.find_many(
        where={
            "customer_type": customer_type,
            "customer_id": customer_id,
        },
        order={"created_at": "desc"},
        take=limit,
    )

    return [
        TransactionResponse(
            transaction_id=t["transaction_id"],
            transaction_type=t["transaction_type"],
            amount=t["amount"],
            balance_before=t["balance_before"],
            balance_after=t["balance_after"],
            description=t.get("description"),
            created_at=t["created_at"],
        )
        for t in transactions
    ]


@router.get(
    "/stripe/balances/all",
    tags=["Stripe Balance"],
    dependencies=[Depends(user_api_key_auth)],
)
async def get_all_balances(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Admin endpoint: Get all user balances

    Requires admin role
    """
    from litellm.proxy.proxy_server import prisma_client, general_settings

    if prisma_client is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Check if user is admin
    if user_api_key_dict.user_role not in ["proxy_admin", "proxy_admin_viewer"]:
        raise HTTPException(
            status_code=403,
            detail="Only admins can view all balances"
        )

    # Get all balance records
    balances = await prisma_client.db.litellm_stripebalancetable.find_many(
        order={"updated_at": "desc"},
    )

    return {
        "balances": [
            {
                "id": b["id"],
                "customer_id": b["customer_id"],
                "customer_type": b["customer_type"],
                "stripe_customer_id": b["stripe_customer_id"],
                "balance": b["balance"],
                "total_topups": b["total_topups"],
                "total_spent": b["total_spent"],
                "low_balance_threshold": b.get("low_balance_threshold"),
                "created_at": b["created_at"].isoformat() if b.get("created_at") else None,
                "updated_at": b["updated_at"].isoformat() if b.get("updated_at") else None,
            }
            for b in balances
        ]
    }


@router.post(
    "/stripe/webhook",
    tags=["Stripe Balance"],
)
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events (payment success, refunds, etc.)

    This endpoint should be configured in your Stripe Dashboard:
    https://dashboard.stripe.com/webhooks

    Events handled:
    - checkout.session.completed: Process successful top-up
    - payment_intent.succeeded: Alternative payment success event
    """
    from litellm.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    # Get webhook payload
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # In production, verify webhook signature
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if webhook_secret:
        # TODO: Implement signature verification using stripe library
        pass

    # Parse event
    try:
        event = await request.json()
    except Exception as e:
        verbose_logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("type")
    verbose_logger.info(f"Received Stripe webhook: {event_type}")

    # Handle checkout.session.completed
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]

        # Extract metadata
        metadata = session.get("metadata", {})
        customer_type = metadata.get("customer_type")
        customer_id = metadata.get("customer_id")
        stripe_customer_id = metadata.get("stripe_customer_id")
        topup_amount = float(metadata.get("topup_amount", 0))

        if not all([customer_type, customer_id, stripe_customer_id, topup_amount]):
            verbose_logger.error(f"Missing metadata in checkout session: {metadata}")
            return {"status": "error", "message": "Missing metadata"}

        # Get balance record
        balance_record = await prisma_client.db.litellm_stripebalancetable.find_unique(
            where={
                "customer_type_customer_id": {
                    "customer_type": customer_type,
                    "customer_id": customer_id,
                }
            }
        )

        if not balance_record:
            verbose_logger.error(f"Balance record not found for {customer_type}:{customer_id}")
            return {"status": "error", "message": "Balance record not found"}

        # Update balance
        old_balance = balance_record["balance"]
        new_balance = old_balance + topup_amount

        await prisma_client.db.litellm_stripebalancetable.update(
            where={"id": balance_record["id"]},
            data={
                "balance": new_balance,
                "total_topups": balance_record["total_topups"] + topup_amount,
            },
        )

        # Record transaction
        await record_transaction(
            prisma_client=prisma_client,
            customer_type=customer_type,
            customer_id=customer_id,
            stripe_customer_id=stripe_customer_id,
            transaction_type="topup",
            amount=topup_amount,
            balance_before=old_balance,
            balance_after=new_balance,
            stripe_checkout_session_id=session.get("id"),
            stripe_payment_intent_id=session.get("payment_intent"),
            description=f"Top-up via Stripe Checkout: ${topup_amount}",
        )

        verbose_logger.info(
            f"Processed top-up for {customer_type}:{customer_id}: "
            f"${topup_amount} (balance: ${old_balance} -> ${new_balance})"
        )

    return {"status": "success"}
