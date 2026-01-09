#!/bin/bash
# F1 Telemetry Quick Start
# Starts all services manually (without launchd)
# Use this for testing or if launchd services are not installed

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="/Users/will/Programming/Websites/f1-race-plots"
LOG_DIR="$HOME/Library/Logs/f1-telemetry"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   F1 Telemetry Quick Start${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create log directory
mkdir -p "$LOG_DIR"

# Stop existing processes
echo -e "${YELLOW}Stopping existing processes...${NC}"
pkill -f "run.py" 2>/dev/null || true
pkill -f "ollama_modal_proxy" 2>/dev/null || true
lsof -ti:5151 | xargs kill -9 2>/dev/null || true
lsof -ti:11435 | xargs kill -9 2>/dev/null || true
sleep 2
echo -e "${GREEN}Done${NC}"
echo ""

cd "$PROJECT_DIR"

# Start Ollama Proxy
echo -e "${YELLOW}Starting Ollama Modal Proxy...${NC}"
uv run python deployment/ollama_modal_proxy.py > "$LOG_DIR/proxy.log" 2>&1 &
PROXY_PID=$!
echo -e "${GREEN}Started (PID: $PROXY_PID)${NC}"
sleep 3

# Verify proxy started
if curl -sf http://localhost:11435/health > /dev/null 2>&1; then
    echo -e "${GREEN}Proxy is healthy${NC}"
else
    echo -e "${YELLOW}Proxy may still be starting...${NC}"
fi
echo ""

# Start Flask App
echo -e "${YELLOW}Starting Flask Application...${NC}"
export PORT=5151
export FLASK_ENV=production
export OLLAMA_BASE_URL=http://localhost:11435
uv run python run.py > "$LOG_DIR/flask.log" 2>&1 &
FLASK_PID=$!
echo -e "${GREEN}Started (PID: $FLASK_PID)${NC}"
sleep 3

# Verify Flask started
if curl -sf http://localhost:5151/ > /dev/null 2>&1; then
    echo -e "${GREEN}Flask is healthy${NC}"
else
    echo -e "${YELLOW}Flask may still be starting...${NC}"
fi
echo ""

# Check Cloudflare tunnel
echo -e "${YELLOW}Checking Cloudflare Tunnel...${NC}"
if pgrep -f "cloudflared tunnel" > /dev/null 2>&1; then
    echo -e "${GREEN}Cloudflare Tunnel is running${NC}"
else
    echo -e "${YELLOW}Cloudflare Tunnel is not running${NC}"
    echo "  Start with: cloudflared tunnel run 65a1819f-0187-41c0-b525-9b909f142ff7"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Services Started!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "  Proxy PID: $PROXY_PID"
echo "  Flask PID: $FLASK_PID"
echo ""
echo "  Local URL:  http://localhost:5151"
echo "  Public URL: https://f1.linux-box.cc"
echo ""
echo "View logs:"
echo "  tail -f $LOG_DIR/flask.log"
echo "  tail -f $LOG_DIR/proxy.log"
echo ""
echo "Stop services:"
echo "  pkill -f 'run.py' && pkill -f 'ollama_modal_proxy'"
echo ""

# Optional: Keep script running to show logs
read -p "Press Enter to view Flask logs (Ctrl+C to exit)..."
tail -f "$LOG_DIR/flask.log"
