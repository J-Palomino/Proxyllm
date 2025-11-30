#!/usr/bin/env python
"""
Run Stripe table migration on startup if tables don't exist
"""
import asyncio
import os
import sys

async def migrate_stripe_tables():
    """Create Stripe balance tables if they don't exist"""
    try:
        from prisma import Prisma

        db = Prisma()
        await db.connect()

        print("Checking if Stripe balance tables exist...")

        # Check if tables exist
        result = await db.query_raw("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('LiteLLM_StripeBalanceTable', 'LiteLLM_StripeTransactionTable')
        """)

        existing_tables = [r['table_name'] for r in result] if result else []

        if len(existing_tables) == 2:
            print("✓ Stripe balance tables already exist")
            await db.disconnect()
            return

        print(f"Creating Stripe balance tables... (found {len(existing_tables)}/2)")

        # Create StripeBalanceTable
        await db.execute_raw("""
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
        """)
        print("✓ Created LiteLLM_StripeBalanceTable")

        # Create indexes for StripeBalanceTable
        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeBalanceTable_stripe_customer_id_idx"
            ON "LiteLLM_StripeBalanceTable"("stripe_customer_id")
        """)

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeBalanceTable_customer_id_idx"
            ON "LiteLLM_StripeBalanceTable"("customer_id")
        """)
        print("✓ Created indexes for StripeBalanceTable")

        # Create StripeTransactionTable
        await db.execute_raw("""
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
        """)
        print("✓ Created LiteLLM_StripeTransactionTable")

        # Create indexes for StripeTransactionTable
        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_customer_id_idx"
            ON "LiteLLM_StripeTransactionTable"("customer_id")
        """)

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_stripe_customer_id_idx"
            ON "LiteLLM_StripeTransactionTable"("stripe_customer_id")
        """)

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_stripe_payment_intent_id_idx"
            ON "LiteLLM_StripeTransactionTable"("stripe_payment_intent_id")
        """)

        await db.execute_raw("""
            CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_created_at_idx"
            ON "LiteLLM_StripeTransactionTable"("created_at")
        """)
        print("✓ Created indexes for StripeTransactionTable")

        # Create trigger function and trigger
        await db.execute_raw("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql'
        """)

        await db.execute_raw("""
            DROP TRIGGER IF EXISTS update_stripe_balance_updated_at ON "LiteLLM_StripeBalanceTable"
        """)

        await db.execute_raw("""
            CREATE TRIGGER update_stripe_balance_updated_at
                BEFORE UPDATE ON "LiteLLM_StripeBalanceTable"
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
        """)
        print("✓ Created trigger for auto-updating timestamps")

        await db.disconnect()
        print("✓ Stripe balance migration completed successfully!")

    except Exception as e:
        print(f"ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Only run if DATABASE_URL is set (i.e., we're on Railway)
    if os.environ.get('DATABASE_URL'):
        asyncio.run(migrate_stripe_tables())
    else:
        print("Skipping migration - DATABASE_URL not set (not on Railway)")
