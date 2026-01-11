# Cloudflare WAF Setup via CLI

Scripts to configure Cloudflare WAF rules for protecting F1 app GPU endpoints.

## Quick Start

### 1. Get Your Cloudflare API Token

1. Visit: https://dash.cloudflare.com/profile/api-tokens
2. Click **"Create Token"**
3. Use template: **"Edit zone WAF"**
4. Permissions: `Zone.WAF = Edit`
5. Zone Resources: `linux-box.cc`
6. Create and **copy the token**

### 2. Run Setup Script

```bash
cd /home/will/f1-plots/scripts
./setup-cloudflare-waf.sh YOUR_API_TOKEN_HERE
```

This will create:
- **GPU endpoint protection**: 10 requests/min, ban 10 minutes
- **General API protection**: 30 requests/min, ban 5 minutes
- **Your IP whitelisted**: `145.241.230.0/24` bypasses all limits

### 3. Verify Rules

```bash
./check-cloudflare-waf.sh YOUR_API_TOKEN_HERE
```

## What Gets Configured

### Rule 1: GPU Endpoint Protection
- **Path:** `*ollama_proxy/generate*`
- **Limit:** 10 requests per minute
- **Action:** Ban for 10 minutes
- **Bypass:** Your IP (`145.241.230.0/24`)
- **Why:** GPU inference is expensive (~$0.001/sec on A10G)

### Rule 2: General API Protection
- **Path:** `*ollama_proxy/*`
- **Limit:** 30 requests per minute
- **Action:** Ban for 5 minutes
- **Bypass:** Your IP (`145.241.230.0/24`)
- **Why:** Prevent API abuse and DoS

## Your Whitelisted CIDR

```
145.241.230.0/24
```

This covers 256 IPs (145.241.230.0 - 145.241.230.255), which includes your current IP and handles dynamic IP changes within your subnet.

## Manual Configuration

If you prefer the dashboard:

1. Go to: https://dash.cloudflare.com/
2. Select: **linux-box.cc** domain
3. Navigate: **Security → WAF → Rate limiting rules**
4. Create rules as shown in the scripts

## Troubleshooting

### "Error: Could not find zone"
- Check your API token has correct permissions
- Verify token includes `Zone.WAF = Edit`
- Ensure zone resource is set to `linux-box.cc`

### "Rate limit already exists"
- Run check script to see existing rules
- Delete duplicate rules via dashboard or:
  ```bash
  # Get rule ID from check script
  curl -X DELETE 'https://api.cloudflare.com/client/v4/zones/ZONE_ID/rate_limits/RULE_ID' \
    -H 'Authorization: Bearer YOUR_TOKEN'
  ```

### Testing Rate Limits

```bash
# Test from non-whitelisted IP (will get blocked after 10 requests)
for i in {1..15}; do
  curl https://f1.linux-box.cc/ollama_proxy/tags
  sleep 1
done

# Test from your IP (should bypass)
# Your IP: 145.241.230.0/24 range
```

## Security Notes

- **Never commit API tokens** to git
- Tokens expire - rotate them regularly
- Use minimal permissions (Zone.WAF only)
- Monitor Security → Events for false positives
- Adjust CIDR range if you get new IP ranges

## Additional Protection Layers

These scripts configure Cloudflare layer. Flask app also has:
- Flask-Limiter: 5 req/min for `/ollama_proxy/generate`
- Bot detection middleware
- Referrer validation in production

Combined: Defense in depth! 🔒
