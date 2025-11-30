# Stripe Prepaid Credits System

This document describes the hybrid Stripe billing system with prepaid credits support.

## Features

The LiteLLM Stripe integration now supports three billing methods:

1. **Billing Meters** (metered events) - Real-time usage tracking via Stripe Billing Meters API
2. **Subscriptions** (recurring billing) - Legacy subscription-based billing
3. **Prepaid Credits** (one-off top-ups) - Users pre-pay for credits, usage deducts from balance

## Environment Variables

### Required
- `STRIPE_API_KEY` - Your Stripe API secret key

### Billing Method Configuration (at least one required)
- `STRIPE_METER_EVENT_NAME` - Event name for Billing Meters (e.g., "tokens")
- `STRIPE_PRICE_ID` - Price ID for subscription billing
- `STRIPE_USE_PREPAID_BALANCE=true` - Enable prepaid credits system

### Optional
- `STRIPE_BILLING_METHOD` - Override auto-detection: "meters", "subscriptions", "prepaid", or combinations like "meters+prepaid"
- `STRIPE_CHARGE_BY` - Who to charge: "end_user_id", "team_id", or "user_id" (default: "end_user_id")
- `STRIPE_API_BASE` - Custom Stripe API base URL
- `STRIPE_WEBHOOK_SECRET` - Secret for verifying Stripe webhooks (recommended for production)

## API Endpoints

### Balance Management

**GET /stripe/balance**
- Check current prepaid balance
- Returns: balance, total top-ups, total spent, low balance threshold

**POST /stripe/topup**
- Create Stripe Checkout Session for adding credits
- Body:
  ```json
  {
    "amount": 100.00,
    "success_url": "https://yourapp.com/success",
    "cancel_url": "https://yourapp.com/cancel"
  }
  ```
- Returns: checkout_url to redirect user to payment page

**GET /stripe/transactions**
- View transaction history
- Query params: `limit` (default: 50)
- Returns: List of top-ups and deductions

**POST /stripe/webhook**
- Webhook endpoint for Stripe events (payment success, etc.)
- Configure in Stripe Dashboard: https://dashboard.stripe.com/webhooks
- Add this URL: `https://your-domain.com/stripe/webhook`

## Database Schema

Two new tables were added:

### LiteLLM_StripeBalanceTable
- Tracks customer balances and top-up settings
- Fields: customer_id, customer_type, stripe_customer_id, balance, total_topups, total_spent

### LiteLLM_StripeTransactionTable
- Transaction history for auditing
- Fields: transaction_type (topup/deduction/refund), amount, balance_before, balance_after

## How It Works

### Top-Up Flow

1. User calls `POST /stripe/topup` with desired amount
2. Server creates Stripe Checkout Session
3. User completes payment on Stripe
4. Stripe sends webhook to `POST /stripe/webhook`
5. Server adds credits to user's balance
6. Transaction recorded in database

### Usage Deduction Flow

1. User makes API request to LiteLLM
2. LiteLLM calculates cost of request
3. StripeLogger deducts cost from prepaid balance
4. If balance insufficient, deducts available balance (doesn't go negative)
5. Transaction recorded with request ID for auditing
6. Low balance warning logged if below threshold

### Hybrid Billing

You can enable multiple billing methods simultaneously:

```bash
# Enable both meters and prepaid
STRIPE_METER_EVENT_NAME="tokens"
STRIPE_USE_PREPAID_BALANCE="true"

# The system will:
# 1. Deduct from prepaid balance
# 2. Send meter event to Stripe
```

## Migration

Run Prisma migration to create new tables:

```bash
cd litellm/proxy
prisma migrate dev --name add_stripe_prepaid_tables
```

## Testing

### Local Testing

1. Set environment variables in `.env`:
   ```
   STRIPE_API_KEY=sk_test_...
   STRIPE_USE_PREPAID_BALANCE=true
   ```

2. Start proxy server:
   ```bash
   litellm --config proxy_config.yaml
   ```

3. Create a top-up:
   ```bash
   curl -X POST http://localhost:4000/stripe/topup \
     -H "Authorization: Bearer your-api-key" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": 10.00,
       "success_url": "http://localhost:3000/success",
       "cancel_url": "http://localhost:3000/cancel"
     }'
   ```

4. Make an API request and check balance deduction

### Webhook Testing

Use Stripe CLI to forward webhooks to local server:

```bash
stripe listen --forward-to localhost:4000/stripe/webhook
```

## Production Setup

1. Set `STRIPE_WEBHOOK_SECRET` environment variable
2. Configure webhook endpoint in Stripe Dashboard
3. Enable webhook signature verification (already implemented in code)
4. Set up monitoring for low balance alerts
5. Consider implementing auto-topup functionality (fields already in schema)

## Security Notes

- All balance operations are atomic (database transactions)
- Webhook signature verification recommended for production
- Customer IDs are namespaced (e.g., `user_id_123`, `team_id_456`)
- Balances cannot go negative
- All transactions are audited in transaction table
