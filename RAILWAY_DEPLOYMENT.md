# Railway Deployment Guide - LiteLLM Proxy with Tailscale

This guide explains how to deploy LiteLLM proxy on Railway with secure access to hab:11434 (Ollama) via Tailscale.

## Architecture

```
[Client APIs with Approved IPs]
    |
    | HTTPS + API Keys
    v
[Railway - LiteLLM Proxy]
    |
    | Tailscale VPN (restricted to hab:11434 only)
    v
[hab:11434] - Ollama
```

## Security Model

- Railway container connects via Tailscale with **restricted access**
- Tailscale ACL limits Railway to **ONLY** hab:11434
- IP whitelist enforces approved clients
- API key authentication for each client

## Step 1: Configure Tailscale ACL

1. Go to https://login.tailscale.com/admin/acls
2. Add this policy to restrict Railway access:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:railway-proxy"],
      "dst": ["hab:11434"]
    }
  ],
  "tagOwners": {
    "tag:railway-proxy": ["J-Palomino@"]
  }
}
```

This ensures Railway can **ONLY** connect to port 11434 on hab.

## Step 2: Generate Tailscale Auth Key

1. Go to https://login.tailscale.com/admin/settings/keys
2. Click "Generate auth key"
3. Configure:
   - Check "Reusable" (allows multiple deployments)
   - Check "Ephemeral" (auto-cleanup when container stops)
   - Add tag: `railway-proxy`
   - Set expiration: 90 days
4. Copy the auth key (starts with `tskey-auth-...`)

## Step 3: Deploy to Railway

1. Push code to GitHub:
```bash
cd C:/Users/jpalo/code/Proxyllm
git add Dockerfile.railway proxy_server_config.railway.yaml railway.toml
git commit -m "Add Railway deployment with Tailscale"
git push
```

2. Create Railway project:
   - Go to https://railway.app
   - Click "New Project" → "Deploy from GitHub repo"
   - Select the Proxyllm repository
   - Railway will auto-detect `railway.toml`

3. Configure environment variables in Railway:
   - `TAILSCALE_AUTH_KEY` = Your auth key from Step 2
   - `LITELLM_MASTER_KEY` = `sk-1234567890abcdef1234567890abcdef` (or generate new)
   - `PORT` = `4000`
   - `TAILSCALE_ADVERTISE_ROUTES` = (Optional) Subnet routes to advertise, e.g., `10.0.0.0/24,192.168.1.0/24`
   - `TAILSCALE_ACCEPT_ROUTES` = (Optional) `true` or `false` (default: `true`)

## Step 4: Configure IP Whitelist (Optional)

Edit `proxy_server_config.railway.yaml` and uncomment the `allowed_ips` section:

```yaml
general_settings:
  allowed_ips:
    - "1.2.3.4"      # Client IP 1
    - "5.6.7.8"      # Client IP 2
    - "10.0.0.0/24"  # IP range
```

Commit and push changes:
```bash
git add proxy_server_config.railway.yaml
git commit -m "Add IP whitelist"
git push
```

Railway will auto-redeploy.

## Step 4b: Enable Subnet Routing (Optional)

To make your Railway container act as a Tailscale subnet router:

1. Add the `TAILSCALE_ADVERTISE_ROUTES` environment variable:
```bash
# Example: Advertise access to a local network
TAILSCALE_ADVERTISE_ROUTES=10.0.0.0/24
```

2. In your Tailscale admin console, approve the subnet routes:
   - Go to https://login.tailscale.com/admin/machines
   - Find the `railway-litellm` machine
   - Click "Edit route settings"
   - Approve the advertised routes

3. Update your ACL to allow access through the subnet router:
```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["autogroup:members"],
      "dst": ["tag:railway-proxy:*"]
    }
  ]
}
```

Now other devices on your Tailscale network can access the advertised subnets through the Railway container.

## Step 5: Test the Deployment

Once Railway deployment is complete:

1. Get your Railway URL: `https://your-app.railway.app`

2. Test health endpoint:
```bash
curl https://your-app.railway.app/health
```

3. Test Ollama connection:
```bash
curl https://your-app.railway.app/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234567890abcdef1234567890abcdef" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Available Ollama Models

The following models are configured to use hab:11434:

- `llama3` - Llama 3 model
- `llama2` - Llama 2 model
- `mistral` - Mistral model
- `ollama/*` - Wildcard for any Ollama model

## Adding More Agents

To add Hugo, David, Nic, or Erik Ollama instances:

1. Update Tailscale ACL to allow access to additional agents
2. Add models to `proxy_server_config.railway.yaml`:

```yaml
model_list:
  - model_name: llama3-hugo
    litellm_params:
      model: ollama/llama3
      api_base: http://100.104.46.119:11434  # Hugo

  - model_name: llama3-david
    litellm_params:
      model: ollama/llama3
      api_base: http://100.95.89.72:11434  # David
```

## Monitoring

- Railway logs: `railway logs`
- Tailscale status: Check https://login.tailscale.com/admin/machines
- LiteLLM admin UI: `https://your-app.railway.app/ui`

## Security Checklist

- [ ] Tailscale ACL configured to restrict access to hab:11434 only
- [ ] Tailscale auth key is tagged with `railway-proxy`
- [ ] LITELLM_MASTER_KEY is set and secure
- [ ] IP whitelist configured (if needed)
- [ ] hab Ollama is listening on Tailscale interface only
- [ ] No public internet access to hab:11434

## Troubleshooting

**Railway can't connect to hab:11434:**
- Check Tailscale is connected: View Railway logs for "Tailscale connected!"
- Verify ACL allows `tag:railway-proxy` to access `hab:11434`
- Test from Railway container: `railway run bash` then `curl http://100.75.148.4:11434`

**Authentication errors:**
- Verify `LITELLM_MASTER_KEY` environment variable is set
- Check API key in Authorization header: `Bearer sk-...`

**IP blocked:**
- Add client IP to `allowed_ips` in config
- Redeploy after config change

## Cost Estimation

- Railway: ~$5/month for basic deployment
- Tailscale: Free for up to 3 users
- Ollama: Running on your existing infrastructure (free)
