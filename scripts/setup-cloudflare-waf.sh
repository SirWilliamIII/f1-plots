#!/bin/bash
#
# Setup Cloudflare WAF Rules for F1 App Protection
# Usage: ./setup-cloudflare-waf.sh YOUR_API_TOKEN
#

set -e

# Check for API token
if [ -z "$1" ]; then
    echo "Usage: $0 <CLOUDFLARE_API_TOKEN>"
    echo ""
    echo "Get your API token from: https://dash.cloudflare.com/profile/api-tokens"
    echo "Required permissions: Zone.WAF (Edit)"
    exit 1
fi

API_TOKEN="$1"
ACCOUNT_ID="82c901187cd8fac15cdb43fbfe36e6dc"
DOMAIN="linux-box.cc"
YOUR_IP_CIDR="145.241.230.0/24"

echo "============================================================"
echo "  Cloudflare WAF Configuration for F1 App"
echo "============================================================"
echo ""
echo "Domain: $DOMAIN"
echo "Whitelisted CIDR: $YOUR_IP_CIDR"
echo ""

# Step 1: Get Zone ID
echo "[1/3] Getting Zone ID for $DOMAIN..."
ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" | jq -r '.result[0].id')

if [ -z "$ZONE_ID" ] || [ "$ZONE_ID" = "null" ]; then
    echo "❌ Error: Could not find zone for $DOMAIN"
    echo "Check your API token has the correct permissions"
    exit 1
fi

echo "✅ Zone ID: $ZONE_ID"
echo ""

# Step 2: Create Rate Limiting Rule for GPU Endpoint
echo "[2/3] Creating rate limit rule for GPU endpoint..."

RULE_1=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rate_limits" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{
    "description": "Protect expensive GPU inference endpoint",
    "match": {
      "request": {
        "url": "*ollama_proxy/generate*"
      }
    },
    "bypass": [
      {
        "name": "ip",
        "value": "'"$YOUR_IP_CIDR"'"
      }
    ],
    "threshold": 10,
    "period": 60,
    "action": {
      "mode": "ban",
      "timeout": 600,
      "response": {
        "content_type": "application/json",
        "body": "{\"error\": \"Rate limit exceeded. GPU endpoints are expensive - please slow down.\"}"
      }
    }
  }')

RULE_1_ID=$(echo "$RULE_1" | jq -r '.result.id')
if [ "$RULE_1_ID" = "null" ]; then
    echo "❌ Error creating rule:"
    echo "$RULE_1" | jq -r '.errors'
else
    echo "✅ GPU endpoint protection: Rule $RULE_1_ID created"
    echo "   Limit: 10 requests/minute, ban for 10 minutes"
    echo "   Bypassed for: $YOUR_IP_CIDR"
fi
echo ""

# Step 3: Create Rate Limiting Rule for All API Endpoints
echo "[3/3] Creating rate limit rule for all API endpoints..."

RULE_2=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rate_limits" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{
    "description": "General API endpoint protection",
    "match": {
      "request": {
        "url": "*ollama_proxy/*"
      }
    },
    "bypass": [
      {
        "name": "ip",
        "value": "'"$YOUR_IP_CIDR"'"
      }
    ],
    "threshold": 30,
    "period": 60,
    "action": {
      "mode": "ban",
      "timeout": 300,
      "response": {
        "content_type": "application/json",
        "body": "{\"error\": \"Rate limit exceeded. Please try again later.\"}"
      }
    }
  }')

RULE_2_ID=$(echo "$RULE_2" | jq -r '.result.id')
if [ "$RULE_2_ID" = "null" ]; then
    echo "❌ Error creating rule:"
    echo "$RULE_2" | jq -r '.errors'
else
    echo "✅ API endpoint protection: Rule $RULE_2_ID created"
    echo "   Limit: 30 requests/minute, ban for 5 minutes"
    echo "   Bypassed for: $YOUR_IP_CIDR"
fi
echo ""

echo "============================================================"
echo "✅ Cloudflare WAF Configuration Complete!"
echo "============================================================"
echo ""
echo "Rate Limits Applied:"
echo "  • /ollama_proxy/generate - 10 req/min (ban 10min)"
echo "  • /ollama_proxy/* - 30 req/min (ban 5min)"
echo ""
echo "Your IP range whitelisted: $YOUR_IP_CIDR"
echo ""
echo "View rules at: https://dash.cloudflare.com/$ACCOUNT_ID/$DOMAIN/security/waf/rate-limiting-rules"
echo ""
