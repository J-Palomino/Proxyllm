# Stripe Integration

LiteLLM supports integration with Stripe for usage-based billing by creating usage records for metered subscriptions.

## Configuration

### Required Environment Variables

```bash
STRIPE_API_KEY="sk_test_..."       # Your Stripe secret API key
STRIPE_PRICE_ID="price_..."        # Stripe price ID for the metered billing item
```

### Optional Environment Variables

```bash
STRIPE_CHARGE_BY="end_user_id"     # What to charge by: "end_user_id", "user_id", or "team_id"
STRIPE_API_BASE="https://api.stripe.com"  # Stripe API base URL (optional)
```

## Usage

### Config YAML

Add Stripe to your success callbacks:

```yaml
litellm_settings:
  success_callback: ["stripe"]
```

### Direct Integration

```python
import litellm

litellm.success_callback = ["stripe"]

response = litellm.completion(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}],
    user="customer_123"  # This will be used as the customer ID
)
```

## How It Works

1. When a successful LLM request is made, the Stripe integration:
   - Creates a usage record in Stripe using the configured price ID
   - Uses token count as the quantity value
   - Associates the usage with a customer based on the `STRIPE_CHARGE_BY` setting
   - Includes metadata such as model, cost, and token usage

2. The integration maps LiteLLM identifiers to Stripe customers:
   - `end_user_id`: Uses the `user` field from the request body
   - `user_id`: Uses the API key's associated user ID
   - `team_id`: Uses the API key's associated team ID

## Stripe Setup

1. Create a product in Stripe for your LLM usage
2. Add a metered price to the product (e.g., price per token)
3. Create subscriptions for your customers using this price
4. Use the price ID in the `STRIPE_PRICE_ID` environment variable

## Metadata

The integration includes the following metadata with each usage record:

- `model`: The LLM model used
- `response_cost`: Calculated cost of the request
- `prompt_tokens`: Number of input tokens
- `completion_tokens`: Number of output tokens
- `litellm_call_id`: Unique identifier for the request
- `customer_id`: The customer identifier used for billing
- `charge_by`: The charging method used

## Error Handling

If required environment variables are missing or the customer ID cannot be determined, the integration will raise an exception and prevent the request from completing.