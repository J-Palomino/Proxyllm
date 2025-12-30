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

---

## Critical Build & Deploy Fixes (December 2024)

This section documents critical fixes required for successful Railway deployment.

### Railway SOCKS5 Proxy Injection

Railway injects proxy environment variables at both build and runtime:
```
HTTP_PROXY=socks5://localhost:1055
HTTPS_PROXY=socks5://localhost:1055
ALL_PROXY=socks5://localhost:1055
```

These break pip, apt-get, and Python HTTP clients.

**Build-time fix** - Use inline unset and noproxy wrapper:
```dockerfile
# For apt-get - inline unset
RUN unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy && \
    apt-get update && apt-get install -y ...

# Create noproxy wrapper for pip
RUN echo '#!/bin/sh' > /usr/local/bin/noproxy && \
    echo 'unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy' >> /usr/local/bin/noproxy && \
    echo 'exec "$@"' >> /usr/local/bin/noproxy && \
    chmod +x /usr/local/bin/noproxy

# Use wrapper for pip commands
RUN /usr/local/bin/noproxy pip install ...
RUN /usr/local/bin/noproxy python -m build
RUN /usr/local/bin/noproxy prisma generate
```

**Runtime fix** - Clear at the very start of entrypoint script:
```sh
#!/bin/sh
export HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" http_proxy="" https_proxy="" all_proxy="" NO_PROXY="*"
# ... rest of startup
```

### Base Image Selection

Use official Python slim, NOT Chainguard:
```dockerfile
ARG LITELLM_BUILD_IMAGE=python:3.12-slim-bookworm
ARG LITELLM_RUNTIME_IMAGE=python:3.12-slim-bookworm
```

Chainguard's `latest-dev` can auto-upgrade to Python 3.14 which lacks pre-built wheels for grpcio, cryptography, and other C extensions.

### Node.js for Prisma Client Generation

Prisma requires Node.js. Install via nodesource apt repo:
```dockerfile
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y nodejs

# Then generate with noproxy wrapper
RUN /usr/local/bin/noproxy prisma generate
```

### Health Check Endpoint

Use the unauthenticated endpoint in `railway.toml`:
```toml
[deploy]
healthcheckPath = "/health/liveliness"  # NOT "/health" which requires auth
healthcheckTimeout = 300
```

### startCommand Must Include Full Path

Railway's startCommand overrides Docker ENTRYPOINT/CMD:
```toml
[deploy]
startCommand = "/app/start_with_tailscale.sh --config proxy_server_config.railway.yaml --port 4000"
```

### PostgreSQL in Container

PostgreSQL runs inside the container. Install and setup:
```dockerfile
RUN apt-get install -y postgresql postgresql-contrib

RUN mkdir -p /var/run/postgresql && chown -R postgres:postgres /var/run/postgresql && \
    mkdir -p /var/lib/postgresql/data && chown -R postgres:postgres /var/lib/postgresql
```

Startup script auto-initializes:
```sh
PGDATA=/var/lib/postgresql/data
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  su postgres -c "/usr/lib/postgresql/15/bin/initdb -D $PGDATA"
fi
su postgres -c "/usr/lib/postgresql/15/bin/pg_ctl -D $PGDATA -l /var/lib/postgresql/logfile start"
```

Override DATABASE_URL to use local PostgreSQL:
```sh
if [ -z "$DATABASE_URL" ] || echo "$DATABASE_URL" | grep -q "railway.internal"; then
  export DATABASE_URL="postgresql://litellm:litellm@localhost:5432/litellm"
fi
```

### Tailscale Non-Blocking Startup

Don't use `set -e` - Tailscale failures should not prevent LiteLLM from starting:
```sh
#!/bin/sh
# NO set -e here

tailscale up --authkey=$TAILSCALE_AUTH_KEY --timeout=30s || echo "Tailscale failed, continuing anyway"
```

### Build Optimization for Layer Caching

Copy requirements before source code:
```dockerfile
COPY requirements.txt pyproject.toml ./
RUN pip wheel --wheel-dir=/wheels/ -r requirements.txt
COPY . .
```

### Common Build Errors

| Error | Solution |
|-------|----------|
| `Missing dependencies for SOCKS support` | Wrap with noproxy script |
| `grpcio failed to build` | Use Python 3.12, not 3.14 |
| `Unsupported proxy configured` | Inline unset before apt-get |
| `nodeenv couldn't download` | Install Node.js via nodesource |
| `npm can't reach registry` | Wrap prisma generate with noproxy |
| `Container failed: executable --config not found` | Fix startCommand in railway.toml |
| `Health check 401 Unauthorized` | Use /health/liveliness endpoint |
| `Can't reach database server` | Add PostgreSQL to container |
| `httpx.ConnectError: All connection attempts failed` | Clear proxy vars at script start |

### Monitoring Deployment

```bash
# Check logs
railway logs --lines 100

# Look for success indicators
railway logs | grep -E "200 OK|Started server|initialized"

# Check status
railway status
```
