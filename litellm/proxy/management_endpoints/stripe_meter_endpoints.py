"""
Stripe Meter Management Endpoints for LiteLLM Admin Console

Provides CRUD operations for Stripe Meters to support usage-based billing.
Follows the same patterns as other LiteLLM management endpoints.
"""

import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Union
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, validator

from litellm._logging import verbose_proxy_logger
from litellm.proxy._types import (
    CommonProxyErrors,
    LitellmUserRoles,
    ProxyException,
    UserAPIKeyAuth,
)
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

router = APIRouter()


# Pydantic Models for Stripe Meter Management
class StripeMeterCreate(BaseModel):
    """Request model for creating a new Stripe meter"""
    display_name: str = Field(..., description="Human-readable name for the meter")
    event_name: str = Field(..., description="Event name used to identify meter usage")
    description: Optional[str] = Field(None, description="Optional description of what this meter tracks")
    customer_mapping_key: str = Field(default="customer_id", description="Field in event payload that identifies the customer")
    aggregation_formula: str = Field(default="sum", description="How to aggregate usage (sum, count, etc.)")
    stripe_api_key: Optional[str] = Field(None, description="Stripe API key for creating the meter (optional if using env vars)")

    @validator("stripe_api_key", always=True)
    def validate_api_key(cls, v):
        if v and not v.startswith(('sk_test_', 'sk_live_')):
            raise ValueError("Invalid Stripe API key format")
        return v

    @validator("event_name")
    def validate_event_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Event name cannot be empty")
        # Remove any special characters that might cause issues
        allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
        if not all(c.lower() in allowed_chars for c in v):
            raise ValueError("Event name can only contain letters, numbers, underscores, and hyphens")
        return v.lower()


class StripeMeterUpdate(BaseModel):
    """Request model for updating an existing Stripe meter"""
    display_name: Optional[str] = Field(None, description="Updated display name")
    description: Optional[str] = Field(None, description="Updated description")
    stripe_api_key: Optional[str] = Field(None, description="Stripe API key for updating the meter (optional if using env vars)")

    @validator("stripe_api_key", always=True)
    def validate_api_key(cls, v):
        if v and not v.startswith(('sk_test_', 'sk_live_')):
            raise ValueError("Invalid Stripe API key format")
        return v


class StripeMeterResponse(BaseModel):
    """Response model for Stripe meter operations"""
    id: str
    display_name: str
    event_name: str
    description: Optional[str]
    customer_mapping: Dict
    default_aggregation: Dict
    created: int
    updated: int
    livemode: bool
    status: str


class StripeMeterListResponse(BaseModel):
    """Response model for listing Stripe meters"""
    meters: List[StripeMeterResponse]
    has_more: bool
    total_count: Optional[int]


def get_stripe_api_key(provided_key: Optional[str] = None) -> str:
    """
    Get Stripe API key from either provided parameter or environment variables.
    Tries multiple environment variable names for compatibility.
    """
    if provided_key:
        return provided_key
    
    # Try multiple possible environment variable names
    env_keys = ['STRIPE_SECRET', 'STRIPE_SECRET_KEY', 'STRIPE_API_KEY']
    for env_key in env_keys:
        api_key = os.getenv(env_key)
        if api_key:
            return api_key
    
    raise HTTPException(
        status_code=400,
        detail="No Stripe API key provided. Please provide one in the request or set STRIPE_SECRET environment variable."
    )


class StripeAPIHelper:
    """Helper class for making Stripe API calls"""

    @staticmethod
    def make_stripe_request(
        api_key: str, 
        endpoint: str, 
        method: str = "GET", 
        data: Optional[Dict] = None,
        api_version: str = "2024-11-20.basil"
    ) -> Dict:
        """Make a request to the Stripe API"""
        url = f"https://api.stripe.com/v1/{endpoint}"
        
        # Prepare headers
        auth_string = f"{api_key}:"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        headers = {
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Stripe-Version': api_version
        }
        
        try:
            if method == "GET" and data:
                query_string = urllib.parse.urlencode(data)
                url += f"?{query_string}"
                
            request = urllib.request.Request(url, headers=headers)
            
            if method in ["POST", "PATCH"] and data:
                post_data = urllib.parse.urlencode(data).encode('utf-8')
                request.data = post_data
                
            if method == "DELETE":
                request.get_method = lambda: 'DELETE'
                
            with urllib.request.urlopen(request) as response:
                response_data = response.read().decode('utf-8')
                return json.loads(response_data)
                
        except urllib.error.HTTPError as e:
            error_data = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_data)
                error_message = error_json.get('error', {}).get('message', 'Unknown Stripe API error')
                raise HTTPException(
                    status_code=e.code,
                    detail=f"Stripe API Error: {error_message}"
                )
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=e.code,
                    detail=f"Stripe API Error: {e.reason}"
                )
        except Exception as e:
            verbose_proxy_logger.error(f"Stripe API request failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to communicate with Stripe API: {str(e)}"
            )


# API Endpoints

@router.get(
    "/stripe/meters",
    tags=["Stripe Meter Management"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=StripeMeterListResponse,
)
async def list_stripe_meters(
    stripe_api_key: Optional[str] = None,
    limit: int = 10,
    starting_after: Optional[str] = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    List all Stripe meters
    
    Parameters:
    - stripe_api_key: Stripe secret API key (optional if using environment variables)
    - limit: Number of meters to return (max 100)
    - starting_after: Cursor for pagination
    """
    try:
        # Check user permissions
        if user_api_key_dict.user_role not in [LitellmUserRoles.PROXY_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only proxy admins can manage Stripe meters"
            )

        # Get API key from parameter or environment
        api_key = get_stripe_api_key(stripe_api_key)

        # Prepare request parameters
        params = {"limit": min(limit, 100)}
        if starting_after:
            params["starting_after"] = starting_after

        # Make Stripe API call
        response_data = StripeAPIHelper.make_stripe_request(
            api_key=api_key,
            endpoint="billing/meters",
            method="GET",
            data=params
        )

        # Transform response
        meters = []
        for meter in response_data.get('data', []):
            meters.append(StripeMeterResponse(
                id=meter['id'],
                display_name=meter.get('display_name', ''),
                event_name=meter.get('event_name', ''),
                description=meter.get('description'),
                customer_mapping=meter.get('customer_mapping', {}),
                default_aggregation=meter.get('default_aggregation', {}),
                created=meter.get('created', 0),
                updated=meter.get('updated', 0),
                livemode=meter.get('livemode', False),
                status=meter.get('status', 'active')
            ))

        return StripeMeterListResponse(
            meters=meters,
            has_more=response_data.get('has_more', False),
            total_count=len(meters)
        )

    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"Error listing Stripe meters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/stripe/meters",
    tags=["Stripe Meter Management"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=StripeMeterResponse,
)
async def create_stripe_meter(
    meter_data: StripeMeterCreate,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    Create a new Stripe meter for usage-based billing
    """
    try:
        # Check user permissions
        if user_api_key_dict.user_role not in [LitellmUserRoles.PROXY_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only proxy admins can create Stripe meters"
            )

        # Get API key from request or environment
        api_key = get_stripe_api_key(meter_data.stripe_api_key)

        # Prepare Stripe API request data
        stripe_data = {
            "display_name": meter_data.display_name,
            "event_name": meter_data.event_name,
            f"customer_mapping[event_payload_key]": meter_data.customer_mapping_key,
            f"default_aggregation[formula]": meter_data.aggregation_formula
        }

        if meter_data.description:
            stripe_data["description"] = meter_data.description

        # Create meter via Stripe API
        response_data = StripeAPIHelper.make_stripe_request(
            api_key=api_key,
            endpoint="billing/meters",
            method="POST",
            data=stripe_data
        )

        # Transform response
        meter_response = StripeMeterResponse(
            id=response_data['id'],
            display_name=response_data.get('display_name', ''),
            event_name=response_data.get('event_name', ''),
            description=response_data.get('description'),
            customer_mapping=response_data.get('customer_mapping', {}),
            default_aggregation=response_data.get('default_aggregation', {}),
            created=response_data.get('created', 0),
            updated=response_data.get('updated', 0),
            livemode=response_data.get('livemode', False),
            status=response_data.get('status', 'active')
        )

        verbose_proxy_logger.info(f"Created Stripe meter: {meter_response.id}")
        return meter_response

    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"Error creating Stripe meter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stripe/meters/{meter_id}",
    tags=["Stripe Meter Management"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=StripeMeterResponse,
)
async def get_stripe_meter(
    meter_id: str,
    stripe_api_key: Optional[str] = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    Get details of a specific Stripe meter
    """
    try:
        # Check user permissions
        if user_api_key_dict.user_role not in [LitellmUserRoles.PROXY_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only proxy admins can view Stripe meters"
            )

        # Get API key from parameter or environment
        api_key = get_stripe_api_key(stripe_api_key)

        # Get meter from Stripe API
        response_data = StripeAPIHelper.make_stripe_request(
            api_key=api_key,
            endpoint=f"billing/meters/{meter_id}",
            method="GET"
        )

        # Transform response
        return StripeMeterResponse(
            id=response_data['id'],
            display_name=response_data.get('display_name', ''),
            event_name=response_data.get('event_name', ''),
            description=response_data.get('description'),
            customer_mapping=response_data.get('customer_mapping', {}),
            default_aggregation=response_data.get('default_aggregation', {}),
            created=response_data.get('created', 0),
            updated=response_data.get('updated', 0),
            livemode=response_data.get('livemode', False),
            status=response_data.get('status', 'active')
        )

    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"Error getting Stripe meter {meter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/stripe/meters/{meter_id}",
    tags=["Stripe Meter Management"],  
    dependencies=[Depends(user_api_key_auth)],
    response_model=StripeMeterResponse,
)
async def update_stripe_meter(
    meter_id: str,
    meter_data: StripeMeterUpdate,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    Update an existing Stripe meter
    """
    try:
        # Check user permissions
        if user_api_key_dict.user_role not in [LitellmUserRoles.PROXY_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only proxy admins can update Stripe meters"
            )

        # Get API key from request or environment
        api_key = get_stripe_api_key(meter_data.stripe_api_key)

        # Prepare update data (only include non-None fields)
        stripe_data = {}
        if meter_data.display_name is not None:
            stripe_data["display_name"] = meter_data.display_name
        if meter_data.description is not None:
            stripe_data["description"] = meter_data.description

        if not stripe_data:
            raise HTTPException(
                status_code=400,
                detail="At least one field must be provided for update"
            )

        # Update meter via Stripe API
        response_data = StripeAPIHelper.make_stripe_request(
            api_key=api_key,
            endpoint=f"billing/meters/{meter_id}",
            method="PATCH",
            data=stripe_data
        )

        # Transform response
        meter_response = StripeMeterResponse(
            id=response_data['id'],
            display_name=response_data.get('display_name', ''),
            event_name=response_data.get('event_name', ''),
            description=response_data.get('description'),
            customer_mapping=response_data.get('customer_mapping', {}),
            default_aggregation=response_data.get('default_aggregation', {}),
            created=response_data.get('created', 0),
            updated=response_data.get('updated', 0),
            livemode=response_data.get('livemode', False),
            status=response_data.get('status', 'active')
        )

        verbose_proxy_logger.info(f"Updated Stripe meter: {meter_response.id}")
        return meter_response

    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"Error updating Stripe meter {meter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/stripe/meters/{meter_id}/deactivate",
    tags=["Stripe Meter Management"],
    dependencies=[Depends(user_api_key_auth)],
    response_model=StripeMeterResponse,
)
async def deactivate_stripe_meter(
    meter_id: str,
    stripe_api_key: Optional[str] = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    Deactivate a Stripe meter (Stripe doesn't allow deletion, only deactivation)
    """
    try:
        # Check user permissions
        if user_api_key_dict.user_role not in [LitellmUserRoles.PROXY_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only proxy admins can deactivate Stripe meters"
            )

        # Get API key from parameter or environment
        api_key = get_stripe_api_key(stripe_api_key)

        # Deactivate meter via Stripe API
        response_data = StripeAPIHelper.make_stripe_request(
            api_key=api_key,
            endpoint=f"billing/meters/{meter_id}/deactivate",
            method="POST"
        )

        # Transform response
        meter_response = StripeMeterResponse(
            id=response_data['id'],
            display_name=response_data.get('display_name', ''),
            event_name=response_data.get('event_name', ''),
            description=response_data.get('description'),
            customer_mapping=response_data.get('customer_mapping', {}),
            default_aggregation=response_data.get('default_aggregation', {}),
            created=response_data.get('created', 0),
            updated=response_data.get('updated', 0),
            livemode=response_data.get('livemode', False),
            status=response_data.get('status', 'inactive')
        )

        verbose_proxy_logger.info(f"Deactivated Stripe meter: {meter_response.id}")
        return meter_response

    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"Error deactivating Stripe meter {meter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/stripe/meters/test-connection",
    tags=["Stripe Meter Management"],
    dependencies=[Depends(user_api_key_auth)],
)
async def test_stripe_connection(
    stripe_api_key: Optional[str] = None,
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth)
):
    """
    Test connection to Stripe API with provided key
    """
    try:
        # Check user permissions
        if user_api_key_dict.user_role not in [LitellmUserRoles.PROXY_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only proxy admins can test Stripe connections"
            )

        # Get API key from parameter or environment
        api_key = get_stripe_api_key(stripe_api_key)

        # Test connection by fetching account info
        response_data = StripeAPIHelper.make_stripe_request(
            api_key=api_key,
            endpoint="account",
            method="GET"
        )

        return {
            "success": True,
            "account_id": response_data.get('id'),
            "account_name": response_data.get('business_profile', {}).get('name'),
            "country": response_data.get('country'),
            "currency": response_data.get('default_currency'),
            "charges_enabled": response_data.get('charges_enabled'),
            "livemode": not api_key.startswith('sk_test_')
        }

    except HTTPException:
        raise
    except Exception as e:
        verbose_proxy_logger.error(f"Error testing Stripe connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))