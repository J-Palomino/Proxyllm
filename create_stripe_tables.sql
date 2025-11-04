-- Create Stripe Balance Table
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
);

-- Create indexes for StripeBalanceTable
CREATE INDEX IF NOT EXISTS "LiteLLM_StripeBalanceTable_stripe_customer_id_idx" ON "LiteLLM_StripeBalanceTable"("stripe_customer_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_StripeBalanceTable_customer_id_idx" ON "LiteLLM_StripeBalanceTable"("customer_id");

-- Create Stripe Transaction Table
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
);

-- Create indexes for StripeTransactionTable
CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_customer_id_idx" ON "LiteLLM_StripeTransactionTable"("customer_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_stripe_customer_id_idx" ON "LiteLLM_StripeTransactionTable"("stripe_customer_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_stripe_payment_intent_id_idx" ON "LiteLLM_StripeTransactionTable"("stripe_payment_intent_id");
CREATE INDEX IF NOT EXISTS "LiteLLM_StripeTransactionTable_created_at_idx" ON "LiteLLM_StripeTransactionTable"("created_at");

-- Create trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_stripe_balance_updated_at ON "LiteLLM_StripeBalanceTable";
CREATE TRIGGER update_stripe_balance_updated_at
    BEFORE UPDATE ON "LiteLLM_StripeBalanceTable"
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
