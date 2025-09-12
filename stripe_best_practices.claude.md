# Stripe Integration Best Practices for LiteLLM

Based on analysis of existing LiteLLM billing integrations (Lago, OpenMeter) and Stripe's current API capabilities, this document outlines best practices for implementing Stripe billing integration.

## Current State Analysis

### Existing Billing Patterns in LiteLLM

1. **Lago Integration** - Usage-based billing with external service
   - Environment variables: `LAGO_API_BASE`, `LAGO_API_KEY`, `LAGO_API_EVENT_CODE`
   - Charges by: `end_user_id`, `user_id`, or `team_id`
   - Sends events with token usage and cost data

2. **OpenMeter Integration** - Usage-based billing with Stripe integration
   - Environment variables: `OPENMETER_API_ENDPOINT`, `OPENMETER_API_KEY`
   - Integrates with Stripe for actual billing
   - Focus on metering and usage tracking

### Stripe API Evolution

Stripe has evolved their billing APIs significantly:

- **Legacy Approach**: Direct metered subscriptions with `usage_type: "metered"`
- **Current Approach**: Meter-based billing system (2024+)
- **Subscription Items**: Usage records attached to subscription items

## Best Practices for Stripe Integration

### 1. Environment Variable Strategy

Follow LiteLLM's established pattern:

```bash
# Required
STRIPE_API_KEY=sk_test_...           # Stripe secret key
STRIPE_PRICE_ID=price_...            # Price ID for billing

# Optional but recommended
STRIPE_CHARGE_BY=end_user_id         # Billing entity: end_user_id | user_id | team_id
STRIPE_API_BASE=https://api.stripe.com  # Custom endpoint (rarely needed)
```

**Security Note**: Never use admin/master keys as fallback for client billing operations.

### 2. Architecture Patterns

#### A. Direct Usage Records (Recommended for Current Implementation)

Use Stripe's subscription items with usage records:

```python
# Create usage record for existing subscription
POST /v1/subscription_items/{item_id}/usage_records
{
    "quantity": token_count,
    "timestamp": unix_timestamp,
    "action": "increment"
}
```

**Pros**:
- Works with current Stripe API
- Simple to implement
- Compatible with existing subscriptions

**Cons**:
- Requires pre-existing subscription items
- Less flexible than meter-based approach

#### B. Meter-Based Billing (Future Implementation)

Use Stripe's newer meter system:

```python
# Send meter event
POST /v1/billing/meter_events
{
    "event_name": "litellm_token_usage",
    "payload": {
        "customer_id": "cus_...",
        "value": token_count
    }
}
```

**Pros**:
- More flexible and scalable
- Better reporting and analytics
- Future-proof architecture

**Cons**:
- Newer API with less established patterns
- May require Stripe account updates

### 3. Customer Identification Strategy

Follow the established LiteLLM pattern:

```python
def get_customer_id(kwargs, litellm_params):
    charge_by = os.getenv("STRIPE_CHARGE_BY", "end_user_id")
    
    if charge_by == "end_user_id":
        # From request body 'user' parameter
        return litellm_params.get("proxy_server_request", {}).get("body", {}).get("user")
    elif charge_by == "user_id":
        # From API key metadata
        return litellm_params["metadata"].get("user_api_key_user_id")
    elif charge_by == "team_id":
        # From API key metadata  
        return litellm_params["metadata"].get("user_api_key_team_id")
```

### 4. Error Handling and Resilience

#### Graceful Degradation
```python
def log_success_event(self, kwargs, response_obj, start_time, end_time):
    try:
        self._send_stripe_usage(kwargs, response_obj)
    except Exception as e:
        # Log error but don't fail the main request
        verbose_logger.error(f"Stripe logging failed: {e}")
        # Optionally: queue for retry, send to fallback system
```

#### Validation Strategy
```python
def validate_environment(self):
    """Validate required environment variables on startup"""
    missing_keys = []
    
    if not os.getenv("STRIPE_API_KEY"):
        missing_keys.append("STRIPE_API_KEY")
    
    if not os.getenv("STRIPE_PRICE_ID"):
        missing_keys.append("STRIPE_PRICE_ID") 
        
    if missing_keys:
        raise Exception(f"Missing Stripe configuration: {missing_keys}")
```

#### API Key Validation
```python
def validate_api_key(self, api_key):
    """Validate API key format and environment"""
    if not api_key.startswith(('sk_test_', 'sk_live_')):
        raise ValueError("Invalid Stripe API key format")
        
    if api_key.startswith('sk_live_') and os.getenv('ENVIRONMENT') != 'production':
        raise ValueError("Live key detected in non-production environment")
```

### 5. Data Payload Structure

Follow the established pattern from Lago integration:

```python
def build_stripe_payload(self, kwargs, response_obj):
    return {
        "quantity": response_obj.get("usage", {}).get("total_tokens", 1),
        "timestamp": int(get_utc_datetime().timestamp()),
        "action": "increment",
        "metadata": {
            "model": kwargs.get("model"),
            "response_cost": str(kwargs.get("response_cost", 0)),
            "prompt_tokens": str(response_obj.get("usage", {}).get("prompt_tokens", 0)),
            "completion_tokens": str(response_obj.get("usage", {}).get("completion_tokens", 0)),
            "litellm_call_id": response_obj.get("id", kwargs.get("litellm_call_id")),
            "customer_id": self._get_customer_id(kwargs),
            "charge_by": os.getenv("STRIPE_CHARGE_BY", "end_user_id")
        }
    }
```

### 6. Testing and Development

#### Test Environment Setup
```python
def setup_test_environment():
    """Create test products and prices for development"""
    # Use test API keys only
    # Create products with descriptive names
    # Set up multiple pricing tiers for testing
    # Create test customers and subscriptions
```

#### Testing Scenarios
1. **Different Customer Types**: end_user_id, user_id, team_id
2. **Various Token Counts**: Small (1-10), Medium (100-1000), Large (10000+)
3. **Error Conditions**: Missing customer ID, invalid API keys, network failures
4. **Edge Cases**: Zero usage, negative usage, missing metadata

### 7. Monitoring and Observability

#### Logging Strategy
```python
def log_stripe_activity(self, activity_type, data, success=True):
    """Structured logging for Stripe activities"""
    log_entry = {
        "timestamp": get_utc_datetime().isoformat(),
        "activity_type": activity_type,  # "usage_record", "customer_lookup", etc.
        "success": success,
        "customer_id": data.get("customer_id"),
        "quantity": data.get("quantity"),
        "stripe_response_id": data.get("stripe_id")
    }
    
    if success:
        verbose_logger.info("Stripe activity successful", extra=log_entry)
    else:
        verbose_logger.error("Stripe activity failed", extra=log_entry)
```

#### Metrics to Track
- Usage records created per hour/day
- Failed API calls and reasons
- Customer ID resolution success rate
- Average API response times
- Cost per token trends

### 8. Configuration Management

#### UI Integration (Similar to Lago/Slack)
```python
# In proxy/_types.py
stripe: CallbackOnUI = CallbackOnUI(
    litellm_callback_name="stripe",
    litellm_callback_params=[
        "STRIPE_API_KEY",
        "STRIPE_PRICE_ID", 
        "STRIPE_CHARGE_BY",
        "STRIPE_API_BASE",
    ],
    ui_callback_name="Stripe Billing",
)
```

#### YAML Configuration
```yaml
litellm_settings:
  success_callback: ["stripe"]

general_settings:
  master_key: sk-1234
```

### 9. Security Considerations

#### API Key Management
- Never log full API keys
- Use environment variables, not hardcoded values
- Validate key format and environment alignment
- Implement key rotation support

#### Customer Data Protection
- Don't include PII in metadata unless necessary
- Use customer IDs, not email addresses or names
- Implement data retention policies
- Ensure GDPR/CCPA compliance for billing data

#### Rate Limiting and Quotas
- Implement exponential backoff for failed requests
- Respect Stripe's rate limits (default: 100/second)
- Queue usage records if necessary
- Monitor quota usage and alerts

### 10. Migration Strategy

#### From Legacy Billing Systems
1. **Parallel Testing**: Run both systems simultaneously
2. **Data Validation**: Compare billing amounts and customer assignments
3. **Gradual Rollout**: Start with test customers, expand gradually
4. **Rollback Plan**: Maintain ability to switch back quickly

#### Future Meter Migration
1. **Create meters alongside existing prices**
2. **Test meter events in parallel with usage records**
3. **Migrate customers to meter-based subscriptions**
4. **Deprecate usage record approach**

## Implementation Checklist

- [ ] Environment variables configured and validated
- [ ] Customer identification logic implemented
- [ ] Error handling and logging in place
- [ ] Test environment with sample data created
- [ ] Usage record creation and validation working
- [ ] Monitoring and alerting configured
- [ ] Security review completed
- [ ] Documentation updated
- [ ] UI integration tested
- [ ] Load testing performed

## Common Pitfalls to Avoid

1. **Using live API keys in development**
2. **Not handling missing customer IDs gracefully**
3. **Failing to validate usage quantities (negative, zero, excessive)**
4. **Insufficient error logging and monitoring**
5. **Not testing with realistic usage patterns**
6. **Hardcoding price IDs instead of using environment variables**
7. **Ignoring Stripe's rate limits and quotas**
8. **Not implementing proper retry mechanisms**
9. **Using admin keys for client-specific operations**
10. **Inadequate testing of the billing flow end-to-end**

## Recommended Next Steps

1. **Implement Direct Usage Records**: Start with subscription items approach
2. **Create Comprehensive Tests**: Cover all customer types and edge cases
3. **Set up Monitoring**: Implement logging and alerting for billing events
4. **Document Configuration**: Create clear setup guides for users
5. **Plan Meter Migration**: Prepare for future Stripe meter-based architecture

This approach balances immediate functionality with future scalability while following LiteLLM's established patterns and Stripe's best practices.