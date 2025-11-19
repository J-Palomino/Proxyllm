# Tailscale Subnet Routing with LiteLLM on Railway

This guide explains how to configure your Railway-deployed LiteLLM proxy as a Tailscale subnet router, enabling other devices on your Tailscale network to access resources through the Railway container.

## What is Subnet Routing?

Subnet routing allows a Tailscale node to advertise access to IP ranges that it can reach. Other devices on your Tailscale network can then access those IP ranges through the subnet router.

### Use Cases

1. **Cloud-to-On-Prem**: Railway container accesses your on-premises network (e.g., internal databases, APIs)
2. **Multi-Cloud**: Route traffic between different cloud providers through Railway
3. **Development**: Access cloud resources from local development machines
4. **Reverse Proxy**: Expose Railway-accessible services to your Tailscale network

## Architecture

```
[Your Devices on Tailscale]
         |
         | Tailscale VPN
         v
[Railway Container - Subnet Router]
         |
         | Advertised Routes
         v
[Target Networks: 10.0.0.0/24, etc.]
```

## Configuration

### 1. Update Dockerfile (Already Done)

The `Dockerfile.railway` has been updated to support subnet routing with these environment variables:

- `TAILSCALE_ADVERTISE_ROUTES`: Comma-separated list of CIDR ranges to advertise
- `TAILSCALE_ACCEPT_ROUTES`: Whether to accept routes from other subnet routers (default: `true`)

### 2. Set Railway Environment Variables

Add these variables in Railway dashboard:

```bash
TAILSCALE_ADVERTISE_ROUTES=10.0.0.0/24,192.168.1.0/24
TAILSCALE_ACCEPT_ROUTES=true
```

**Examples:**

- Single subnet: `TAILSCALE_ADVERTISE_ROUTES=10.0.0.0/24`
- Multiple subnets: `TAILSCALE_ADVERTISE_ROUTES=10.0.0.0/24,192.168.1.0/24,172.16.0.0/16`
- Accept routes from others: `TAILSCALE_ACCEPT_ROUTES=true`

### 3. Approve Routes in Tailscale Admin

After deploying with `TAILSCALE_ADVERTISE_ROUTES` set:

1. Go to https://login.tailscale.com/admin/machines
2. Find your `railway-litellm` machine
3. You'll see "Subnets" section with advertised routes pending approval
4. Click "Edit route settings"
5. Toggle each route to "Approved"
6. Save changes

### 4. Update Tailscale ACL

Allow traffic through the subnet router by updating your ACL at https://login.tailscale.com/admin/acls:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["autogroup:members"],
      "dst": ["tag:railway-proxy:*"]
    },
    {
      "action": "accept",
      "src": ["tag:railway-proxy"],
      "dst": ["autogroup:internet:*"]
    }
  ],
  "tagOwners": {
    "tag:railway-proxy": ["youremail@example.com"]
  }
}
```

## Testing Subnet Routing

### Verify Routes are Advertised

Check Railway logs for:
```
Starting Tailscale daemon...
Connecting to Tailscale with subnet routes: 10.0.0.0/24,192.168.1.0/24
Tailscale connected successfully!
```

### Test Connectivity

From any device on your Tailscale network:

```bash
# Ping a device in the advertised subnet
ping 10.0.0.5

# Access a service in the subnet
curl http://10.0.0.10:8080

# Verify route is active
tailscale status
```

You should see the Railway container listed as an active peer with subnet routes.

### Check Route Table

On your local machine (must have Tailscale installed):

```bash
# View all Tailscale routes
tailscale status --json | grep -A5 "AllowedIPs"

# Or on macOS/Linux
ip route | grep tailscale
```

## Limitations with Railway/Docker

### Userspace Networking Mode

Railway doesn't allow privileged containers, so we use `--tun=userspace-networking`. This has some limitations:

1. **No true kernel-level routing**: Traffic is proxied through userspace
2. **Performance overhead**: Slightly higher latency compared to kernel mode
3. **Limited protocol support**: Some ICMP features may not work perfectly
4. **No IP forwarding**: Can't act as a traditional router

### What Still Works

- HTTP/HTTPS traffic
- TCP connections
- UDP (most protocols)
- DNS resolution
- Most application-layer protocols

### What Doesn't Work

- Raw ICMP (ping may be unreliable)
- IP-level multicast/broadcast
- Some VPN protocols that require kernel modules

## Common Scenarios

### Scenario 1: Access Internal Database from Railway

**Setup:**
- Internal database at `10.0.0.100:5432`
- Railway needs to connect to it

**Configuration:**
```bash
# On Railway
TAILSCALE_ADVERTISE_ROUTES=10.0.0.0/24
TAILSCALE_ACCEPT_ROUTES=true

# In your LiteLLM config or app
DATABASE_URL=postgresql://user:pass@10.0.0.100:5432/db
```

### Scenario 2: Expose Railway Services to Your Network

**Setup:**
- Railway app running on internal port
- Want to access from your local network via Tailscale

**Configuration:**
```bash
# On Railway - advertise Railway's internal network
TAILSCALE_ADVERTISE_ROUTES=172.17.0.0/16

# From your machine
curl http://172.17.0.2:4000/health
```

### Scenario 3: Multi-Cloud Networking

**Setup:**
- Railway in one region
- AWS/GCP resources in another
- Need secure communication

**Configuration:**
```bash
# On Railway
TAILSCALE_ADVERTISE_ROUTES=10.0.0.0/16  # Your AWS VPC CIDR

# In your app
API_ENDPOINT=http://10.0.1.50:8080
```

## Troubleshooting

### Routes Not Appearing

**Symptom:** Routes aren't shown in Tailscale admin

**Solutions:**
1. Check Railway logs for "Connecting to Tailscale with subnet routes"
2. Verify `TAILSCALE_ADVERTISE_ROUTES` is set correctly
3. Ensure CIDR format is correct (e.g., `10.0.0.0/24`)
4. Redeploy Railway container

### Routes Pending Approval

**Symptom:** Routes show as "pending" in Tailscale admin

**Solutions:**
1. Go to https://login.tailscale.com/admin/machines
2. Click railway-litellm machine
3. Approve each route manually
4. Check that your account has permission to approve routes

### Can't Reach Advertised Subnet

**Symptom:** Routes approved but traffic doesn't flow

**Solutions:**
1. Check ACL allows traffic to `tag:railway-proxy:*`
2. Verify Railway container can actually reach the subnet
3. Test from Railway: `railway run bash` then `curl http://10.0.0.5`
4. Check firewall rules on target subnet
5. Verify `TAILSCALE_ACCEPT_ROUTES=true` if routing through other nodes

### Connection Timeout

**Symptom:** Connections hang or timeout

**Solutions:**
1. Verify target service is actually running
2. Check Railway container networking: `railway run bash` then `ping 10.0.0.5`
3. Increase timeout in your application
4. Check for NAT/firewall issues on target network
5. Try with `curl -v` to see where connection fails

## Security Considerations

### Principle of Least Privilege

Only advertise routes you need:

```bash
# Bad - too broad
TAILSCALE_ADVERTISE_ROUTES=0.0.0.0/0

# Good - specific subnets
TAILSCALE_ADVERTISE_ROUTES=10.0.1.0/24
```

### ACL Best Practices

Restrict who can use the subnet router:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["group:engineering"],
      "dst": ["tag:railway-proxy:10.0.0.0/24"]
    }
  ]
}
```

### Audit Subnet Access

Monitor who's using the subnet router:
1. Go to https://login.tailscale.com/admin/machines
2. Click railway-litellm
3. View "Recent connections"
4. Check logs for unusual traffic patterns

## Advanced Configuration

### Dynamic Route Management

Update routes without redeploying:

```bash
# In Railway shell (railway run bash)
tailscale up --advertise-routes=10.0.0.0/24,192.168.1.0/24
```

Note: This requires manual intervention and routes reset on container restart.

### Multiple Subnet Routers

Run multiple Railway containers with different routes:

```bash
# Railway Container 1
TAILSCALE_ADVERTISE_ROUTES=10.0.0.0/24
TAILSCALE_AUTH_KEY=tskey-auth-...

# Railway Container 2
TAILSCALE_ADVERTISE_ROUTES=192.168.1.0/24
TAILSCALE_AUTH_KEY=tskey-auth-...
```

### Exit Node Mode

Make Railway an exit node for all internet traffic:

```bash
TAILSCALE_ADVERTISE_ROUTES=0.0.0.0/0,::/0
```

Then approve in Tailscale admin and use as exit node from your devices.

## Monitoring

### Check Route Status

```bash
# From your machine
tailscale status --json | jq '.Peer[] | select(.HostName=="railway-litellm")'

# From Railway container
railway run bash
tailscale status
```

### Monitor Traffic

Railway logs will show:
```
Starting Tailscale daemon...
Connecting to Tailscale with subnet routes: 10.0.0.0/24
Tailscale connected successfully!
# [... Tailscale status output ...]
```

### Alerts

Set up monitoring for:
1. Railway container restarts
2. Tailscale connection drops
3. Route approval status changes
4. Unusual traffic patterns

## Cost Implications

- Tailscale: Free for personal use, check pricing for teams
- Railway: Data transfer costs may apply for high traffic
- Network egress: Monitor bandwidth usage through Railway dashboard

## References

- Tailscale Subnet Routers: https://tailscale.com/kb/1019/subnets/
- Railway Networking: https://docs.railway.app/reference/networking
- Tailscale ACLs: https://tailscale.com/kb/1018/acls/
- Tailscale in Docker: https://tailscale.com/kb/1282/docker/
