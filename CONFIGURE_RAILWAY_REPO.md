# Configure Railway to Deploy from Proxyllm Repository

## Current Issue

Railway is configured to deploy from `https://github.com/J-Palomino/litellm.git` but we want it to deploy from `https://github.com/J-Palomino/Proxyllm.git`.

All our fixes are in the Proxyllm repo:
- Commit 27a28625: Fix database connection pool
- Commit 45cbd63b: Fix Tailscale installation for Wolfi
- Commit 8ba3833e: Add config file to Docker CMD
- Commit 43fe977e: Trigger redeploy

## Steps to Configure Railway Dashboard

### 1. Open Railway Dashboard
https://railway.app/project/532ff751-f7a1-4f7e-81fa-57cdf1504771

### 2. Navigate to Service Settings
- Click on the "litellm" service
- Go to "Settings" tab

### 3. Update GitHub Repository
Look for "Source" or "GitHub Repository" section:
- Current: `J-Palomino/litellm` (branch: main)
- Change to: `J-Palomino/Proxyllm` (branch: main)

### 4. Trigger Deployment
After changing the repository:
- Railway should automatically trigger a new deployment
- Watch the "Deployments" tab for build progress

### 5. Expected Build Logs
You should see:
```
Installing Tailscale static binary...
Starting Tailscale...
tailscaled --tun=userspace-networking --socks5-server=localhost:1055
Tailscale connected!
Starting LiteLLM proxy...
Loading config from proxy_server_config.railway.yaml
Models loaded: llama3, llama2, mistral, ollama/*
Server started on port 4000
```

## Alternative: Manual Redeploy via Dashboard

If you can't change the repository source:

1. Go to Railway Dashboard
2. Click "litellm" service
3. Go to "Deployments" tab
4. Click "Deploy" or "New Deployment"
5. This will rebuild from the current connected repository

## Verification

Once deployed, test:
```bash
# Health check (should return healthy status or model list)
curl https://litellm-production-a013.up.railway.app/health \
  -H "Authorization: Bearer sk-1234567890abcdef1234567890abcdef"

# Test Ollama via Tailscale
curl https://litellm-production-a013.up.railway.app/v1/chat/completions \
  -H "Authorization: Bearer sk-1234567890abcdef1234567890abcdef" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "Hello from Railway!"}]
  }'
```

## Current Status

- Commits: All pushed to Proxyllm repo (origin)
- Railway: Still watching litellm repo
- Deployment: Old version still running (Model list not initialized error)

**Action Required**: Update Railway dashboard to point to Proxyllm repository.
