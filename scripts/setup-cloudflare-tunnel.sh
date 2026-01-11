#!/bin/bash
#
# Set up Cloudflare Tunnel on Oracle Ubuntu Server
#
# This script:
#   1. Installs cloudflared
#   2. Authenticates with Cloudflare
#   3. Creates a tunnel
#   4. Configures DNS routing
#   5. Sets up systemd service
#
# Prerequisites:
#   - Cloudflare account with a domain
#   - SSH access to Oracle server
#
# Usage:
#   ./scripts/setup-cloudflare-tunnel.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TUNNEL_NAME="${TUNNEL_NAME:-f1-telemetry}"
DOMAIN="${CF_DOMAIN:-}"  # e.g., f1.yourdomain.com

echo "=============================================="
echo "  Cloudflare Tunnel Setup for F1 Telemetry"
echo "=============================================="
echo

# Step 1: Install cloudflared
echo -e "${BLUE}Step 1: Installing cloudflared...${NC}"
if ! command -v cloudflared &> /dev/null; then
    # Add Cloudflare GPG key
    sudo mkdir -p --mode=0755 /usr/share/keyrings
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

    # Add repository
    echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared jammy main' | sudo tee /etc/apt/sources.list.d/cloudflared.list

    # Install
    sudo apt-get update
    sudo apt-get install -y cloudflared

    echo -e "${GREEN}cloudflared installed successfully${NC}"
else
    echo -e "${GREEN}cloudflared already installed${NC}"
fi

# Step 2: Authenticate with Cloudflare
echo
echo -e "${BLUE}Step 2: Authenticating with Cloudflare...${NC}"
if [ ! -f ~/.cloudflared/cert.pem ]; then
    echo "Opening browser for Cloudflare authentication..."
    echo "If no browser opens, copy the URL shown and open it manually."
    echo
    cloudflared tunnel login
    echo -e "${GREEN}Authentication successful${NC}"
else
    echo -e "${GREEN}Already authenticated${NC}"
fi

# Step 3: Create tunnel
echo
echo -e "${BLUE}Step 3: Creating tunnel '${TUNNEL_NAME}'...${NC}"
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo -e "${GREEN}Tunnel '$TUNNEL_NAME' already exists${NC}"
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
else
    cloudflared tunnel create "$TUNNEL_NAME"
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    echo -e "${GREEN}Tunnel created with ID: $TUNNEL_ID${NC}"
fi

# Step 4: Create config file
echo
echo -e "${BLUE}Step 4: Creating tunnel configuration...${NC}"
mkdir -p ~/.cloudflared

cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: /home/$(whoami)/.cloudflared/${TUNNEL_ID}.json

ingress:
  # F1 Telemetry Flask app
  - hostname: ${DOMAIN:-"*"}
    service: http://localhost:5151
  # Catch-all (required)
  - service: http_status:404
EOF

echo -e "${GREEN}Config created at ~/.cloudflared/config.yml${NC}"

# Step 5: Set up DNS (if domain provided)
if [ -n "$DOMAIN" ]; then
    echo
    echo -e "${BLUE}Step 5: Setting up DNS for $DOMAIN...${NC}"
    cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" || true
    echo -e "${GREEN}DNS configured: $DOMAIN -> tunnel${NC}"
else
    echo
    echo -e "${YELLOW}Step 5: Skipping DNS setup (no domain provided)${NC}"
    echo "To set up DNS later, run:"
    echo "  cloudflared tunnel route dns $TUNNEL_NAME yourdomain.com"
fi

# Step 6: Install systemd service
echo
echo -e "${BLUE}Step 6: Installing systemd service...${NC}"
if [ "$EUID" -eq 0 ] || sudo -n true 2>/dev/null; then
    # Update service file with current user
    CURRENT_USER=$(whoami)
    sed "s|User=ubuntu|User=$CURRENT_USER|g" deployment/systemd/cloudflared.service | \
        sudo tee /etc/systemd/system/cloudflared.service > /dev/null

    sudo systemctl daemon-reload
    sudo systemctl enable cloudflared
    echo -e "${GREEN}Systemd service installed${NC}"
else
    echo -e "${YELLOW}Skipping systemd installation (not root)${NC}"
    echo "Run with sudo to install service"
fi

# Summary
echo
echo "=============================================="
echo -e "${GREEN}  Cloudflare Tunnel Setup Complete!${NC}"
echo "=============================================="
echo
echo "Tunnel ID: $TUNNEL_ID"
echo "Config:    ~/.cloudflared/config.yml"
if [ -n "$DOMAIN" ]; then
    echo "Domain:    https://$DOMAIN"
fi
echo
echo "Commands:"
echo "  # Start tunnel manually"
echo "  cloudflared tunnel run $TUNNEL_NAME"
echo
echo "  # Start via systemd"
echo "  sudo systemctl start cloudflared"
echo "  sudo systemctl status cloudflared"
echo
echo "  # View logs"
echo "  journalctl -u cloudflared -f"
echo
echo "  # Add DNS route"
echo "  cloudflared tunnel route dns $TUNNEL_NAME your.domain.com"
echo
