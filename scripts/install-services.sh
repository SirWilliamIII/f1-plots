#!/bin/bash
# F1 Telemetry Service Installer
# Installs launchd services for automatic process management on macOS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="/Users/will/Programming/Websites/f1-race-plots"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs/f1-telemetry"

# Detect uv path
UV_PATH=$(which uv 2>/dev/null || echo "/Users/will/.local/bin/uv")
if [ ! -f "$UV_PATH" ]; then
    echo -e "${RED}Error: uv not found. Please install it first.${NC}"
    exit 1
fi

# Detect cloudflared path
CLOUDFLARED_PATH=$(which cloudflared 2>/dev/null || echo "/opt/homebrew/bin/cloudflared")
if [ ! -f "$CLOUDFLARED_PATH" ]; then
    echo -e "${YELLOW}Warning: cloudflared not found. Tunnel service will not be installed.${NC}"
    INSTALL_TUNNEL=false
else
    INSTALL_TUNNEL=true
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   F1 Telemetry Service Installer${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}Done${NC}"
echo ""

# Stop existing services
echo -e "${YELLOW}Stopping existing services...${NC}"
launchctl unload "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-flask.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-ollama-proxy.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-cloudflared.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-health.plist" 2>/dev/null || true

# Also kill any manually started processes
pkill -f "run.py" 2>/dev/null || true
pkill -f "ollama_modal_proxy" 2>/dev/null || true
echo -e "${GREEN}Done${NC}"
echo ""

# Create Flask service
echo -e "${YELLOW}Creating Flask service...${NC}"
cat > "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-flask.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-flask</string>

    <key>ProgramArguments</key>
    <array>
        <string>$UV_PATH</string>
        <string>run</string>
        <string>python</string>
        <string>run.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PORT</key>
        <string>5151</string>
        <key>FLASK_ENV</key>
        <string>production</string>
        <key>OLLAMA_BASE_URL</key>
        <string>http://localhost:11435</string>
        <key>PATH</key>
        <string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/flask.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/flask.error.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
echo -e "${GREEN}Created cc.linux-box.f1-flask.plist${NC}"

# Create Ollama Proxy service
echo -e "${YELLOW}Creating Ollama Proxy service...${NC}"
cat > "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-ollama-proxy.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-ollama-proxy</string>

    <key>ProgramArguments</key>
    <array>
        <string>$UV_PATH</string>
        <string>run</string>
        <string>python</string>
        <string>deployment/ollama_modal_proxy.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/proxy.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/proxy.error.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
echo -e "${GREEN}Created cc.linux-box.f1-ollama-proxy.plist${NC}"

# Create Cloudflare Tunnel service (if cloudflared is installed)
if [ "$INSTALL_TUNNEL" = true ]; then
    echo -e "${YELLOW}Creating Cloudflare Tunnel service...${NC}"
    cat > "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-cloudflared.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-cloudflared</string>

    <key>ProgramArguments</key>
    <array>
        <string>$CLOUDFLARED_PATH</string>
        <string>tunnel</string>
        <string>run</string>
        <string>65a1819f-0187-41c0-b525-9b909f142ff7</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/cloudflared.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/cloudflared.error.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF
    echo -e "${GREEN}Created cc.linux-box.f1-cloudflared.plist${NC}"
fi

# Create Health Check service
echo -e "${YELLOW}Creating Health Check service...${NC}"
chmod +x "$PROJECT_DIR/scripts/health-check.sh"
cat > "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-health.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-health</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/scripts/health-check.sh</string>
    </array>

    <key>StartInterval</key>
    <integer>300</integer>

    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF
echo -e "${GREEN}Created cc.linux-box.f1-health.plist${NC}"
echo ""

# Load services
echo -e "${YELLOW}Loading services...${NC}"

# Load proxy first (Flask depends on it)
launchctl load "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-ollama-proxy.plist"
echo -e "${GREEN}Loaded Ollama Proxy service${NC}"

# Wait for proxy to start
sleep 2

# Load Flask
launchctl load "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-flask.plist"
echo -e "${GREEN}Loaded Flask service${NC}"

# Load Cloudflare (if installed)
if [ "$INSTALL_TUNNEL" = true ]; then
    launchctl load "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-cloudflared.plist"
    echo -e "${GREEN}Loaded Cloudflare Tunnel service${NC}"
fi

# Load health check
launchctl load "$LAUNCH_AGENTS_DIR/cc.linux-box.f1-health.plist"
echo -e "${GREEN}Loaded Health Check service${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Services will now:"
echo "  - Start automatically on login"
echo "  - Restart automatically if they crash"
echo "  - Write logs to $LOG_DIR/"
echo ""
echo "Check status with:"
echo "  ./scripts/status.sh"
echo ""
echo "View logs with:"
echo "  tail -f $LOG_DIR/flask.log"
echo "  tail -f $LOG_DIR/proxy.log"
echo ""
echo "Manual control:"
echo "  launchctl stop cc.linux-box.f1-flask"
echo "  launchctl start cc.linux-box.f1-flask"
echo "  launchctl kickstart -k gui/\$(id -u)/cc.linux-box.f1-flask"
echo ""
