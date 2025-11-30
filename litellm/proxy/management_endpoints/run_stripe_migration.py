"""
Endpoint to run Stripe balance table migration
"""
from fastapi import APIRouter, Depends, HTTPException
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.proxy._types import UserAPIKeyAuth
import traceback

router = APIRouter()


def get_prisma_client():
    """Lazy import to avoid circular dependency"""
    from litellm.proxy.proxy_server import prisma_client
    return prisma_client


@router.post("/stripe/migrate", tags=["stripe"])
async def run_stripe_migration(
    user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
):
    """
    Run database migration to create Stripe balance tables.
    Admin only endpoint.
    """
    # Check if user is admin
    if user_api_key_dict.user_role not in ["proxy_admin", "proxy_admin_viewer"]:
        raise HTTPException(
            status_code=403,
            detail="Only admins can run migrations"
        )

    try:
        # SQL to create tables
        sql_statements = [
            # Create StripeBalanceTable
            """
            CREATE TABLE IF NOT EXISTS "LiteLLM_StripeBalanceTable" (
                "id" TEXT NOT NULL PRIMARY KEY DEFAULT gen_random_uuid()::text,
                "customer_type" TEXT NOT NULL,
                "customer_id" TEXT NOT NULL,
                "stripe_customer_id" TEXT NOT NULL UNIQUE,
                "balance" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                "total_topups" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                "total_spent" DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                "low_balance_threshold" DOUBLE PRECISION,
                "auto_topup_enabled" BOOLEAN NOT NULL DEFAULT false,
                "auto_topup_amount" DOUBLE PRECISION,
                "auto_topup_payment_method_id" TEXT,
                "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
                "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT "LiteLLM_StripeBalanceTable_customer_type_customer_id_key" UNIQUE ("customer_type", "customer_id")
            )
            """,

            # Create indexes for StripeBalanceTable
            """
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeBalanceTable_stripe_customer_id_idx"
            ON "LiteLLM_StripeBalanceTable"("stripe_customer_id")
            """,

            """
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeBalanceTable_customer_id_idx"
            ON "LiteLLM_StripeBalanceTable"("customer_id")
            """,

            # Create StripeTransactionTable
            """
            CREATE TABLE IF NOT EXISTS "LiteLLM_StripeTransactionTable" (
                "transaction_id" TEXT NOT NULL PRIMARY KEY DEFAULT gen_random_uuid()::text,
                "customer_type" TEXT NOT NULL,
                "customer_id" TEXT NOT NULL,
                "stripe_customer_id" TEXT NOT NULL,
                "transaction_type" TEXT NOT NULL,
                "amount" DOUBLE PRECISION NOT NULL,
                "balance_before" DOUBLE PRECISION NOT NULL,
                "balance_after" DOUBLE PRECISION NOT NULL,
                "stripe_payment_intent_id" TEXT,
                "stripe_checkout_session_id" TEXT,
                "request_id" TEXT,
                "description" TEXT,
                "metadata" JSONB DEFAULT '{}',
                "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,

            # Create indexes for StripeTransactionTable
            """
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_customer_id_idx"
            ON "LiteLLM_StripeTransactionTable"("customer_id")
            """,

            """
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_stripe_customer_id_idx"
            ON "LiteLLM_StripeTransactionTable"("stripe_customer_id")
            """,

            """
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_stripe_payment_intent_id_idx"
            ON "LiteLLM_StripeTransactionTable"("stripe_payment_intent_id")
            """,

            """
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_created_at_idx"
            ON "LiteLLM_StripeTransactionTable"("created_at")
            """,

            # Create trigger function
            """
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql'
            """,

            # Create trigger
            """
            DROP TRIGGER IF EXISTS update_stripe_balance_updated_at ON "LiteLLM_StripeBalanceTable"
            """,

            """
            CREATE TRIGGER update_stripe_balance_updated_at
                BEFORE UPDATE ON "LiteLLM_StripeBalanceTable"
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
            """
        ]

        # Execute each statement
        prisma_client = get_prisma_client()
        results = []
        for i, sql in enumerate(sql_statements):
            try:
                await prisma_client.db.execute_raw(sql)
                results.append(f"Statement {i+1}: SUCCESS")
            except Exception as e:
                results.append(f"Statement {i+1}: {str(e)}")

        # Verify tables were created
        tables = await prisma_client.db.query_raw("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE '%Stripe%'
            ORDER BY table_name
        """)

        return {
            "status": "success",
            "message": "Migration completed",
            "execution_results": results,
            "tables_created": [t["table_name"] for t in tables] if tables else []
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )
