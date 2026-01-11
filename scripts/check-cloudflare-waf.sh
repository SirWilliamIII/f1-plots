#!/bin/bash
#
# Check existing Cloudflare WAF Rules
# Usage: ./check-cloudflare-waf.sh YOUR_API_TOKEN
#

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <CLOUDFLARE_API_TOKEN>"
    exit 1
fi

API_TOKEN="$1"
DOMAIN="linux-box.cc"

echo "Fetching WAF rules for $DOMAIN..."
echo ""

# Get Zone ID
ZONE_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones?name=$DOMAIN" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" | jq -r '.result[0].id')

if [ -z "$ZONE_ID" ] || [ "$ZONE_ID" = "null" ]; then
    echo "❌ Error: Could not find zone for $DOMAIN"
    exit 1
fi

echo "Zone ID: $ZONE_ID"
echo ""

# List rate limiting rules
echo "Rate Limiting Rules:"
echo "===================="
curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rate_limits" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" | jq -r '.result[] | "ID: \(.id)\nDescription: \(.description)\nURL Match: \(.match.request.url)\nThreshold: \(.threshold) requests per \(.period) seconds\nAction: \(.action.mode) for \(.action.timeout) seconds\nBypasses: \(.bypass // [])\n"'

echo ""
echo "To delete a rule: curl -X DELETE 'https://api.cloudflare.com/client/v4/zones/$ZONE_ID/rate_limits/RULE_ID' -H 'Authorization: Bearer $API_TOKEN'"
