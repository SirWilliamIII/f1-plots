#!/bin/bash
#
# F1 Telemetry App - Quick Modal Deployment Script
#
# This script deploys the OPTIMIZED Modal configuration with:
# - Increased timeouts (600s for Flask, 900s for Ollama)
# - Concurrent request handling (10 requests)
# - Container warming (keeps 1 container ready)
# - Persistent Ollama model volume
#

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}F1 Telemetry - Modal Deployment (Optimized)${NC}"
echo ""

# Change to project root
cd "$(dirname "$0")/.."

# Check if modal is installed
if ! command -v modal &> /dev/null; then
    echo "Installing Modal CLI..."
    pip install modal
fi

# Deploy
echo -e "${BLUE}Deploying to Modal...${NC}"
modal deploy deployment/app_modal.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Deployment successful!${NC}"
    echo ""
    echo "Your app is live at:"
    echo "  https://sirwilliamiii--f1-telemetry-web.modal.run"
    echo ""
    echo "View logs:"
    echo "  modal app logs f1-telemetry"
    echo ""
    echo "Monitor costs:"
    echo "  https://modal.com/usage"
    echo ""
else
    echo "❌ Deployment failed"
    exit 1
fi
