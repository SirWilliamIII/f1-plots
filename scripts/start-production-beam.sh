#!/bin/bash
#
# Start F1 Telemetry production server with Beam.cloud GPU acceleration
#
# Prerequisites:
#   1. Deploy Beam function: beam deploy deployment/app_beam_ollama.py:generate
#   2. Set BEAM_API_TOKEN environment variable
#
# Usage:
#   ./scripts/start-production-beam.sh
#

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
FLASK_PORT="${PORT:-5151}"
PROXY_PORT="11435"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  F1 Telemetry - Beam.cloud GPU Production"
echo "=============================================="
echo

# Check for BEAM_API_TOKEN
if [ -z "$BEAM_API_TOKEN" ]; then
    echo -e "${RED}ERROR: BEAM_API_TOKEN is not set${NC}"
    echo
    echo "To fix:"
    echo "  1. Get your API token from https://platform.beam.cloud"
    echo "  2. Add to your environment:"
    echo "     export BEAM_API_TOKEN=your_token_here"
    echo "  3. Or add to ~/.bashrc for persistence"
    echo
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Kill existing processes
echo "Stopping any existing processes..."
pkill -f "ollama_beam_proxy.py" 2>/dev/null || true
pkill -f "run.py" 2>/dev/null || true
sleep 2

# Change to project directory
cd "$PROJECT_DIR"

# Start Beam proxy
echo -e "${YELLOW}Starting Beam GPU proxy on port $PROXY_PORT...${NC}"
nohup python3 deployment/ollama_beam_proxy.py > "$LOG_DIR/beam-proxy.log" 2>&1 &
PROXY_PID=$!
echo "  PID: $PROXY_PID"

# Wait for proxy to start
sleep 3

# Verify proxy is running
if ! curl -sf http://localhost:$PROXY_PORT/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Beam proxy failed to start${NC}"
    echo "Check logs: tail -f $LOG_DIR/beam-proxy.log"
    exit 1
fi
echo -e "${GREEN}  Beam proxy started successfully${NC}"

# Start Flask app
echo -e "${YELLOW}Starting Flask app on port $FLASK_PORT...${NC}"
export FLASK_ENV=production
export PORT=$FLASK_PORT
export OLLAMA_BASE_URL=http://localhost:$PROXY_PORT

nohup python3 run.py > "$LOG_DIR/flask.log" 2>&1 &
FLASK_PID=$!
echo "  PID: $FLASK_PID"

# Wait for Flask to start
sleep 3

# Verify Flask is running
if ! curl -sf http://localhost:$FLASK_PORT/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Flask app failed to start${NC}"
    echo "Check logs: tail -f $LOG_DIR/flask.log"
    exit 1
fi
echo -e "${GREEN}  Flask app started successfully${NC}"

echo
echo "=============================================="
echo -e "${GREEN}  Production server is running!${NC}"
echo "=============================================="
echo
echo "  Flask:      http://localhost:$FLASK_PORT"
echo "  Beam Proxy: http://localhost:$PROXY_PORT"
echo
echo "  Logs:"
echo "    tail -f $LOG_DIR/flask.log"
echo "    tail -f $LOG_DIR/beam-proxy.log"
echo
echo "  Stop:"
echo "    pkill -f 'run.py|ollama_beam_proxy'"
echo
