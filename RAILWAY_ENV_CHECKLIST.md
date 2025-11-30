# Railway Environment Variables Checklist

## Current Status: 2025-11-04

### ✅ Required Variables - ALL SET

| Variable | Value | Status | Purpose |
|----------|-------|--------|---------|
| **TAILSCALE_AUTH_KEY** | `tskey-auth-ke7Sf7hZJ811CNTRL-...` | ✅ SET | Tailscale VPN connection |
| **LITELLM_MASTER_KEY** | `sk-1234567890abcdef1234567890abcdef` | ✅ SET | Admin API authentication |
| **LITELLM_SALT_KEY** | `daisykey-` | ✅ SET | Key encryption salt |
| **PORT** | `4000` | ✅ SET | Server port |
| **STORE_MODEL_IN_DB** | `False` | ✅ SET | Use config file instead of DB |

### ✅ Stripe Variables - ALL SET

| Variable | Value | Status | Purpose |
|----------|-------|--------|---------|
| **STRIPE_API_KEY** | `sk_test_51RmyWPIPPKIieVTh...` | ✅ SET | Stripe API access |
| **STRIPE_SECRET** | `sk_test_51RmyWPIPPKIieVTh...` | ✅ SET | Stripe secret (duplicate) |
| **STRIPE_PUBLISHABLE_KEY** | `pk_test_51RmyWPIPPKIieVTh...` | ✅ SET | Public Stripe key |
| **STRIPE_METER_EVENT_NAME** | `tokens` | ✅ SET | Meter billing event name |
| **STRIPE_USE_PREPAID_BALANCE** | `true` | ✅ SET | Enable prepaid system |

### ✅ Database Variables - ALL SET

| Variable | Value | Status | Purpose |
|----------|-------|--------|---------|
| **DATABASE_URL** | `postgresql://postgres:...@postgres.railway.internal:5432/railway` | ✅ SET | PostgreSQL connection |
| **DATABASE_POOL_MAX** | `5` | ✅ SET | Max DB connections |
| **DATABASE_POOL_MIN** | `1` | ✅ SET | Min DB connections |

### ⚠️ Optional Variables - NOT SET (OK)

| Variable | Default | Status | Purpose |
|----------|---------|--------|---------|
| **STRIPE_CHARGE_BY** | `end_user_id` | ⚠️ NOT SET | Who to charge (defaults to end_user_id) |
| **STRIPE_BILLING_METHOD** | `auto` | ⚠️ NOT SET | Billing method (auto-detected) |
| **ALLOWED_IPS** | None | ⚠️ NOT SET | IP whitelist (open to all) |
| **TAILSCALE_ADVERTISE_ROUTES** | None | ⚠️ NOT SET | Subnet routes to advertise (e.g., `10.0.0.0/24,192.168.1.0/24`) |
| **TAILSCALE_ACCEPT_ROUTES** | `true` | ⚠️ NOT SET | Accept routes from other subnet routers |

---

## Configuration Summary

### Deployment Mode
- **Config File**: `proxy_server_config.railway.yaml`
- **Database**: PostgreSQL (for prepaid balances only)
- **Storage Mode**: File-based config (`STORE_MODEL_IN_DB=False`)

### Tailscale Integration
- **Connection**: Enabled via `TAILSCALE_AUTH_KEY`
- **Target**: hab:11434 (100.75.148.4:11434)
- **Access Control**: Restricted via Tailscale ACL (tag: `railway-proxy`)
- **Models**: llama3, llama2, mistral, ollama/*

### Stripe Integration
- **Mode**: Hybrid (Meters + Prepaid Balance)
- **Billing Method**: Auto-detected (`meters+prepaid`)
- **Meter Event**: `tokens`
- **Prepaid**: Enabled with database tracking
- **Test Mode**: Using `sk_test_...` keys

---

## Environment Variable Recommendations

### 1. Set STRIPE_CHARGE_BY (Optional but Recommended)
```bash
railway variables --set STRIPE_CHARGE_BY=end_user_id
```

Options:
- `end_user_id` - Charge based on request's `user` parameter (default)
- `user_id` - Charge based on API key owner
- `team_id` - Charge based on team

### 2. Enable IP Whitelist (Production Recommended)
Edit `proxy_server_config.railway.yaml`:
```yaml
general_settings:
  allowed_ips:
    - "1.2.3.4"      # Your approved IP 1
    - "5.6.7.8"      # Your approved IP 2
    - "10.0.0.0/24"  # IP range
```

### 3. Add Webhook Secret (Production Required)
```bash
railway variables --set STRIPE_WEBHOOK_SECRET=whsec_...
```
Get from: https://dashboard.stripe.com/webhooks

---

## Verification Steps

### 1. Check Environment Variables
```bash
cd C:/Users/jpalo/code/Proxyllm
railway variables | grep -E "STRIPE|TAILSCALE|LITELLM"
```

### 2. Test Deployment
```bash
# Health check
curl https://litellm-production-a013.up.railway.app/health

# Test Stripe connection
curl https://litellm-production-a013.up.railway.app/stripe/meters/test-connection \
  -X POST \
  -H "Authorization: Bearer sk-1234567890abcdef1234567890abcdef"

# Test Ollama via Tailscale
curl https://litellm-production-a013.up.railway.app/v1/chat/completions \
  -H "Authorization: Bearer sk-1234567890abcdef1234567890abcdef" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### 3. Verify Tailscale Connection
Check Tailscale admin panel:
- https://login.tailscale.com/admin/machines
- Look for machine named `railway-litellm`
- Verify IP address in 100.x.x.x range
- Check connection status is "active"

---

## Missing Variables Check

✅ **All Required Variables Present**

### Confirmed Present:
1. ✅ TAILSCALE_AUTH_KEY
2. ✅ LITELLM_MASTER_KEY
3. ✅ LITELLM_SALT_KEY
4. ✅ STRIPE_API_KEY
5. ✅ STRIPE_METER_EVENT_NAME
6. ✅ STRIPE_USE_PREPAID_BALANCE
7. ✅ DATABASE_URL
8. ✅ PORT
9. ✅ STORE_MODEL_IN_DB

### Optional (Not Critical):
- STRIPE_CHARGE_BY (defaults to end_user_id)
- STRIPE_BILLING_METHOD (auto-detected)
- STRIPE_WEBHOOK_SECRET (for production webhooks)
- ALLOWED_IPS (for IP whitelisting)

---

## Next Steps

1. ✅ All required environment variables are set
2. ⏳ Trigger Railway deployment via web dashboard
3. ⏳ Monitor deployment logs for Tailscale connection
4. ⏳ Test endpoints after deployment completes
5. 📋 Configure IP whitelist (if needed)
6. 📋 Set up Stripe webhooks (for production)

## Deployment Command

Since CLI upload timed out, use **Railway Web Dashboard**:

1. Go to: https://railway.app/project/532ff751-f7a1-4f7e-81fa-57cdf1504771
2. Click "litellm" service
3. Go to "Deployments" tab
4. Click "Deploy" or "Redeploy"
5. Monitor build logs for:
   - "Starting Tailscale..."
   - "Tailscale connected!"
   - "Starting LiteLLM proxy..."

## Status: READY TO DEPLOY ✅

All environment variables are properly configured. The deployment is ready to proceed via Railway web dashboard.
