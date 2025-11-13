#!/bin/bash
# Quick update script - sync local changes to Oracle server
# Use this after making code changes

# Configuration - UPDATE THESE
ORACLE_HOST="${ORACLE_HOST:-your-server-ip}"
ORACLE_USER="${ORACLE_USER:-ubuntu}"
REMOTE_DIR="/opt/f1-app"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✓${NC} $1"; }
log_step() { echo -e "${BLUE}→${NC} $1"; }

echo "🔄 Syncing changes to Oracle server..."
echo ""

# Quick config if needed
if [ "$ORACLE_HOST" = "your-server-ip" ]; then
    read -p "Oracle Server IP: " ORACLE_HOST
    read -p "Oracle SSH User (default: ubuntu): " input_user
    ORACLE_USER="${input_user:-ubuntu}"
fi

# Sync files using rsync
log_step "Syncing files..."
rsync -avz --progress \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.venv/' \
    --exclude='venv/' \
    --exclude='fastf1_cache/' \
    --exclude='static/plots/' \
    --exclude='logs/' \
    --exclude='*.log' \
    --exclude='.DS_Store' \
    --exclude='node_modules/' \
    --rsync-path="sudo rsync" \
    ./ $ORACLE_USER@$ORACLE_HOST:$REMOTE_DIR/

log_info "Files synced"

# Restart services
log_step "Restarting services..."
ssh $ORACLE_USER@$ORACLE_HOST "sudo systemctl restart f1-app"

log_info "Services restarted"
echo ""
echo "✅ Update complete!"
echo ""
echo "Check logs:"
echo "  ssh $ORACLE_USER@$ORACLE_HOST"
echo "  cd $REMOTE_DIR"
echo "  ./oracle-manage.sh logs"
echo ""
