#!/bin/bash
# Deploy F1 App to Oracle Server - Direct Transfer Method
# No GitHub cloning required - transfers files directly from your laptop

set -e

# Configuration - UPDATE THESE
ORACLE_HOST="${ORACLE_HOST:-your-server-ip}"
ORACLE_USER="${ORACLE_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-}"
REMOTE_DIR="/opt/f1-app"

# Build SSH command with optional key
SSH_CMD="ssh"
SCP_CMD="scp"
if [ -n "$SSH_KEY" ]; then
    SSH_CMD="ssh -i $SSH_KEY"
    SCP_CMD="scp -i $SSH_KEY"
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✓${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_step() { echo -e "${BLUE}→${NC} $1"; }

echo "🚀 F1 App Oracle Deployment - Direct Transfer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if we have required info
if [ "$ORACLE_HOST" = "your-server-ip" ]; then
    echo "Please set your Oracle server details:"
    read -p "Oracle Server IP: " ORACLE_HOST
    read -p "Oracle SSH User (default: ubuntu): " input_user
    ORACLE_USER="${input_user:-ubuntu}"
    echo ""
fi

echo "Configuration:"
echo "  Server: $ORACLE_USER@$ORACLE_HOST"
echo "  Remote directory: $REMOTE_DIR"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Check SSH connection
log_step "Testing SSH connection..."
if ! $SSH_CMD -o ConnectTimeout=5 $ORACLE_USER@$ORACLE_HOST "echo 'Connected successfully'" > /dev/null 2>&1; then
    log_error "Cannot connect to $ORACLE_USER@$ORACLE_HOST"
    echo ""
    echo "Make sure:"
    echo "  1. Your SSH key is loaded or specified via SSH_KEY"
    echo "  2. You can connect: $SSH_CMD $ORACLE_USER@$ORACLE_HOST"
    exit 1
fi
log_info "SSH connection successful"

# Create deployment package
log_step "Creating deployment package..."
TEMP_DIR=$(mktemp -d)
PACKAGE_NAME="f1-app-$(date +%Y%m%d-%H%M%S).tar.gz"

# Exclude files we don't want to transfer
tar -czf "$TEMP_DIR/$PACKAGE_NAME" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='fastf1_cache/*' \
    --exclude='static/plots/*' \
    --exclude='logs/*' \
    --exclude='*.log' \
    --exclude='.DS_Store' \
    --exclude='node_modules' \
    .

log_info "Package created: $PACKAGE_NAME"

# Transfer package
log_step "Transferring files to Oracle server..."
$SCP_CMD "$TEMP_DIR/$PACKAGE_NAME" $ORACLE_USER@$ORACLE_HOST:/tmp/
log_info "Files transferred"

# Extract and setup on server
log_step "Setting up on Oracle server..."
$SSH_CMD $ORACLE_USER@$ORACLE_HOST << 'ENDSSH'
set -e

# Create directory
sudo mkdir -p /opt/f1-app
cd /opt/f1-app

# Extract files
echo "Extracting files..."
sudo tar -xzf /tmp/f1-app-*.tar.gz
sudo rm /tmp/f1-app-*.tar.gz

# Set permissions
sudo chown -R www-data:www-data /opt/f1-app

# Create necessary directories
sudo -u www-data mkdir -p /opt/f1-app/logs
sudo -u www-data mkdir -p /opt/f1-app/fastf1_cache
sudo -u www-data mkdir -p /opt/f1-app/static/plots

echo "✓ Files extracted and permissions set"
ENDSSH

log_info "Setup complete on server"

# Run deployment script on server
log_step "Running deployment script..."
$SSH_CMD $ORACLE_USER@$ORACLE_HOST << 'ENDSSH'
cd /opt/f1-app
if [ -f deploy-oracle-hybrid.sh ]; then
    sudo chmod +x deploy-oracle-hybrid.sh
    sudo ./deploy-oracle-hybrid.sh
else
    echo "Warning: deploy-oracle-hybrid.sh not found"
    echo "You'll need to run the setup manually"
fi
ENDSSH

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps - SSH into your server:"
echo "  ssh $ORACLE_USER@$ORACLE_HOST"
echo ""
echo "Then configure Modal (one-time):"
echo "  sudo -u www-data bash"
echo "  cd /opt/f1-app"
echo "  modal setup  # Opens browser for authentication"
echo "  modal deploy deployment/app_modal_ollama_only.py"
echo "  exit"
echo ""
echo "Check status:"
echo "  cd /opt/f1-app"
echo "  ./oracle-manage.sh status"
echo ""
echo "Your app should be running at:"
echo "  http://$ORACLE_HOST"
echo ""
