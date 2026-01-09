#!/bin/bash
# F1 Telemetry Status Dashboard
# Quick overview of all services and their health

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   F1 Telemetry Application Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check launchd services
echo -e "${YELLOW}Services (launchd):${NC}"
for service in f1-flask f1-ollama-proxy f1-cloudflared f1-health; do
    status=$(launchctl list 2>/dev/null | grep "cc.linux-box.$service" || true)
    if [ -n "$status" ]; then
        pid=$(echo "$status" | awk '{print $1}')
        if [ "$pid" = "-" ]; then
            echo -e "  ${RED}[STOPPED]${NC} $service"
        else
            echo -e "  ${GREEN}[RUNNING]${NC} $service (PID: $pid)"
        fi
    else
        echo -e "  ${YELLOW}[NOT INSTALLED]${NC} $service"
    fi
done

# Check processes directly if launchd not configured
echo ""
echo -e "${YELLOW}Processes (direct):${NC}"
if pgrep -f "run.py" > /dev/null 2>&1; then
    pid=$(pgrep -f "run.py" | head -1)
    echo -e "  ${GREEN}[RUNNING]${NC} Flask App (PID: $pid)"
else
    echo -e "  ${RED}[STOPPED]${NC} Flask App"
fi

if pgrep -f "ollama_modal_proxy" > /dev/null 2>&1; then
    pid=$(pgrep -f "ollama_modal_proxy" | head -1)
    echo -e "  ${GREEN}[RUNNING]${NC} Ollama Proxy (PID: $pid)"
else
    echo -e "  ${RED}[STOPPED]${NC} Ollama Proxy"
fi

if pgrep -f "cloudflared tunnel" > /dev/null 2>&1; then
    pid=$(pgrep -f "cloudflared tunnel" | head -1)
    echo -e "  ${GREEN}[RUNNING]${NC} Cloudflare Tunnel (PID: $pid)"
else
    echo -e "  ${RED}[STOPPED]${NC} Cloudflare Tunnel"
fi

# Health checks
echo ""
echo -e "${YELLOW}Health Checks:${NC}"

if curl -sf http://localhost:5151/ > /dev/null 2>&1; then
    echo -e "  ${GREEN}[OK]${NC} Flask App (http://localhost:5151)"
else
    echo -e "  ${RED}[FAIL]${NC} Flask App (http://localhost:5151)"
fi

if curl -sf http://localhost:11435/health > /dev/null 2>&1; then
    backend=$(curl -sf http://localhost:11435/health 2>/dev/null | grep -o '"backend":"[^"]*"' | cut -d'"' -f4)
    echo -e "  ${GREEN}[OK]${NC} Ollama Proxy (http://localhost:11435) - Backend: $backend"
else
    echo -e "  ${RED}[FAIL]${NC} Ollama Proxy (http://localhost:11435)"
fi

if curl -sf --max-time 5 https://f1.linux-box.cc/ > /dev/null 2>&1; then
    echo -e "  ${GREEN}[OK]${NC} Public URL (https://f1.linux-box.cc)"
else
    echo -e "  ${YELLOW}[WARN]${NC} Public URL (https://f1.linux-box.cc) - May be slow or tunnel down"
fi

# Recent health log entries
echo ""
echo -e "${YELLOW}Recent Health Log:${NC}"
if [ -f "$HOME/Library/Logs/f1-telemetry/health.log" ]; then
    tail -5 "$HOME/Library/Logs/f1-telemetry/health.log" 2>/dev/null | while read line; do
        if echo "$line" | grep -q "ERROR"; then
            echo -e "  ${RED}$line${NC}"
        elif echo "$line" | grep -q "OK"; then
            echo -e "  ${GREEN}$line${NC}"
        else
            echo "  $line"
        fi
    done
else
    echo "  No health log found yet"
fi

# Quick commands
echo ""
echo -e "${YELLOW}Quick Commands:${NC}"
echo "  Start all:    ./scripts/start-production-gpu.sh"
echo "  View logs:    tail -f ~/Library/Logs/f1-telemetry/flask.log"
echo "  Restart:      launchctl kickstart -k gui/\$(id -u)/cc.linux-box.f1-flask"
echo "  Modal logs:   modal app logs f1-ollama-gpu"
echo ""
