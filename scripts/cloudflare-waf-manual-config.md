# Cloudflare WAF Manual Configuration

Since API access has permission issues, here's the exact configuration to set up manually in the Cloudflare dashboard.

## Access Dashboard

1. Go to: https://dash.cloudflare.com/82c901187cd8fac15cdb43fbfe36e6dc
2. Select domain: **linux-box.cc**
3. Navigate to: **Security → WAF**

---

## Rate Limiting Rules to Create

### Rule 1: Protect GPU Endpoint (CRITICAL)

**Navigate to:** Security → WAF → Rate limiting rules → Create rule

```
Rule name: GPU Endpoint Protection
Description: Prevent abuse of expensive Beam A10G GPU inference

When incoming requests match:
  Request URL Path contains: /ollama_proxy/generate

Then:
  Threshold: 10 requests
  Period: 60 seconds (1 minute)
  Mitigation action: Block
  Mitigation timeout: 600 seconds (10 minutes)
  Response:
    Status code: 429
    Content-Type: application/json
    Body: {"error": "Rate limit exceeded. GPU inference is expensive - please slow down."}

Bypass:
  Expression Builder:
    Field: IP Source Address
    Operator: is in
    Value: 145.241.230.0/24
```

**Why:** GPU cold starts cost ~$0.40 each (4 min × $0.001/sec). 10 req/min = max $4/min exposure.

---

### Rule 2: General API Protection

**Create rule:**

```
Rule name: API Endpoint Protection
Description: Prevent API abuse and DoS attempts

When incoming requests match:
  Request URL Path contains: /ollama_proxy/

Then:
  Threshold: 30 requests
  Period: 60 seconds (1 minute)
  Mitigation action: Block
  Mitigation timeout: 300 seconds (5 minutes)
  Response:
    Status code: 429
    Content-Type: application/json
    Body: {"error": "Rate limit exceeded. Please try again later."}

Bypass:
  Expression Builder:
    Field: IP Source Address
    Operator: is in
    Value: 145.241.230.0/24
```

**Why:** Prevents API scraping while allowing legitimate F1 data queries.

---

## Optional: WAF Custom Rules

**Navigate to:** Security → WAF → Custom rules → Create rule

### Rule 3: Block Obvious Bots

```
Rule name: Block Bot User Agents
Description: Block automated scrapers

When incoming requests match:
  (http.user_agent contains "bot") or
  (http.user_agent contains "crawler") or
  (http.user_agent contains "scraper") or
  (http.user_agent eq "")

And:
  URI Path contains: /ollama_proxy/

Then:
  Action: Block
```

---

## Enable Bot Fight Mode

**Navigate to:** Security → Bots

1. Enable **"Bot Fight Mode"** (Free plan)
   - Automatically challenges suspected bots
   - Blocks verified bad bots

OR

2. Enable **"Super Bot Fight Mode"** (Paid plans)
   - More aggressive detection
   - Machine learning-based

---

## Verify Configuration

After setup, test from a different IP:

```bash
# Should work (your IP is whitelisted)
curl https://f1.linux-box.cc/ollama_proxy/tags

# Should get rate limited after 10 requests
for i in {1..15}; do
  curl https://f1.linux-box.cc/ollama_proxy/generate \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen2.5-coder:7b","prompt":"test","stream":false}'
  sleep 1
done
```

---

## Your Whitelisted CIDR

```
145.241.230.0/24
```

**Coverage:** 256 IP addresses
**Range:** 145.241.230.0 - 145.241.230.255
**Your current IP:** 145.241.230.198

This covers you even if your ISP changes your IP within the same /24 subnet.

---

## Security Summary

| Layer | Rule | Limit | Action |
|-------|------|-------|--------|
| Cloudflare | GPU endpoint | 10/min | Block 10min |
| Cloudflare | API endpoints | 30/min | Block 5min |
| Cloudflare | Bot Fight | Auto | Challenge/Block |
| Flask | GPU endpoint | 5/min + 20/hr | 429 error |
| Flask | All endpoints | 50/min + 200/hr | 429 error |
| Flask | Bot middleware | Production | 403 error |

**Defense in depth:** Multiple layers protect against different attack vectors!

---

## Monitoring

**Check blocked requests:**
1. Navigate to: **Security → Events**
2. Filter by: **Action = Block**
3. Review: Make sure legitimate users aren't blocked

**Adjust if needed:**
- Increase thresholds if false positives
- Decrease if abuse continues
- Add more IP ranges to bypass list

---

## Estimated Cost Protection

Without rate limiting:
- Malicious bot: 100 requests/min
- Cold start each: 4 minutes GPU time
- Cost: 100 × 4min × $0.001/sec × 60sec/min = **$24/min = $1,440/hr**

With 10 req/min limit:
- Max exposure: 10 × 4min × $0.001/sec × 60sec/min = **$2.40/min = $144/hr**
- Then blocked for 10 minutes = **effective $14.40/hr max**

**ROI: Prevents $1,400+/hr in potential abuse!** 🔒💰
