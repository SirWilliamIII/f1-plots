#!/bin/bash
#
# Deploy F1 Telemetry to Oracle Ubuntu Server with Beam.cloud GPU
#
# Run this script ON the Oracle server after cloning the repo
#
# Prerequisites:
#   1. Ubuntu server with Python 3.10+
#   2. Beam.cloud account with API token
#   3. Domain pointed to server (optional, for Cloudflare tunnel)
#
# Usage:
#   export BEAM_API_TOKEN=your_token_here
#   ./scripts/deploy-oracle-beam.sh
#

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=============================================="
echo "  F1 Telemetry - Oracle Server Deployment"
echo "  Using Beam.cloud GPU for AI Inference"
echo "=============================================="
echo

# Check for BEAM_API_TOKEN
if [ -z "$BEAM_API_TOKEN" ]; then
    echo -e "${RED}ERROR: BEAM_API_TOKEN is not set${NC}"
    echo
    echo "Get your token from https://platform.beam.cloud"
    echo "Then run: export BEAM_API_TOKEN=your_token_here"
    exit 1
fi

# Check if running as root for systemd setup
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}Note: Run with sudo for systemd service installation${NC}"
    echo "      Or install services manually later"
    echo
    INSTALL_SYSTEMD=false
else
    INSTALL_SYSTEMD=true
fi

cd "$PROJECT_DIR"

# Step 1: Install system dependencies
echo -e "${BLUE}Step 1: Installing system dependencies...${NC}"
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv curl
fi

# Step 2: Install uv if not present
echo -e "${BLUE}Step 2: Installing uv package manager...${NC}"
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Step 3: Install Python dependencies
echo -e "${BLUE}Step 3: Installing Python dependencies...${NC}"
uv pip install -r requirements.txt

# Step 4: Install Beam client
echo -e "${BLUE}Step 4: Installing Beam client...${NC}"
pip install beam-client

# Step 5: Create log directory
echo -e "${BLUE}Step 5: Creating log directory...${NC}"
mkdir -p logs

# Step 6: Note about Beam function
echo -e "${BLUE}Step 6: Beam GPU function...${NC}"
echo -e "${YELLOW}NOTE: Deploy the Beam function from your LOCAL machine (not this server):${NC}"
echo "  pip install beam-client"
echo "  beam config create"
echo "  beam deploy deployment/app_beam_ollama.py:generate"
echo
echo "The Oracle server only needs BEAM_API_TOKEN to call the deployed function."

# Step 7: Install systemd services (if root)
if [ "$INSTALL_SYSTEMD" = true ]; then
    echo -e "${BLUE}Step 7: Installing systemd services...${NC}"

    # Update service files with correct paths
    CURRENT_USER=$(logname 2>/dev/null || echo $SUDO_USER || echo $USER)
    HOME_DIR=$(eval echo ~$CURRENT_USER)

    # Copy and configure beam proxy service
    sed "s|/home/ubuntu|$HOME_DIR|g" deployment/systemd/f1-beam-proxy.service | \
    sed "s|User=ubuntu|User=$CURRENT_USER|g" | \
    sed "s|YOUR_TOKEN_HERE|$BEAM_API_TOKEN|g" > /tmp/f1-beam-proxy.service
    sudo mv /tmp/f1-beam-proxy.service $SYSTEMD_DIR/

    # Copy and configure flask service
    sed "s|/home/ubuntu|$HOME_DIR|g" deployment/systemd/f1-flask.service | \
    sed "s|User=ubuntu|User=$CURRENT_USER|g" > /tmp/f1-flask.service
    sudo mv /tmp/f1-flask.service $SYSTEMD_DIR/

    # Reload and enable services
    sudo systemctl daemon-reload
    sudo systemctl enable f1-beam-proxy
    sudo systemctl enable f1-flask

    echo -e "${GREEN}Systemd services installed!${NC}"
    echo
    echo "Start services with:"
    echo "  sudo systemctl start f1-beam-proxy"
    echo "  sudo systemctl start f1-flask"
else
    echo -e "${BLUE}Step 7: Skipping systemd installation (not root)${NC}"
    echo "To install services later, run:"
    echo "  sudo ./scripts/deploy-oracle-beam.sh"
fi

echo
echo "=============================================="
echo -e "${GREEN}  Deployment Complete!${NC}"
echo "=============================================="
echo
echo "Next steps:"
echo
echo "  1. Start the services:"
echo "     sudo systemctl start f1-beam-proxy f1-flask"
echo "     # OR"
echo "     ./scripts/start-production-beam.sh"
echo
echo "  2. Test the application:"
echo "     curl http://localhost:5151/health"
echo
echo "  3. Set up Cloudflare tunnel for public access:"
echo "     export CF_DOMAIN=f1.yourdomain.com"
echo "     ./scripts/setup-cloudflare-tunnel.sh"
echo "     sudo systemctl start cloudflared"
echo
echo "  4. View logs:"
echo "     tail -f logs/flask.log"
echo "     tail -f logs/beam-proxy.log"
echo "     journalctl -u cloudflared -f"
echo
