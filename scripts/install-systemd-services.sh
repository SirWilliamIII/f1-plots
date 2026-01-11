#!/bin/bash
#
# Install F1 App Systemd Services
# This sets up auto-restart and boot-on-startup for Flask and Beam proxy
#

set -e

echo "============================================================"
echo "  Installing F1 App Systemd Services"
echo "============================================================"
echo ""

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run with sudo:"
    echo "   sudo ./scripts/install-systemd-services.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
PROJECT_DIR="/home/$ACTUAL_USER/f1-plots"

echo "Installing as user: $ACTUAL_USER"
echo "Project directory: $PROJECT_DIR"
echo ""

# Step 1: Stop currently running services
echo "[1/6] Stopping currently running services..."
pkill -f "run.py" || true
pkill -f "ollama_beam_proxy" || true
sleep 2
echo "✅ Services stopped"
echo ""

# Step 2: Create log directory
echo "[2/6] Creating log directory..."
mkdir -p "$PROJECT_DIR/logs"
chown -R $ACTUAL_USER:$ACTUAL_USER "$PROJECT_DIR/logs"
echo "✅ Log directory ready"
echo ""

# Step 3: Copy service files to systemd
echo "[3/6] Installing service files..."
cp "$PROJECT_DIR/deployment/systemd/f1-beam-proxy.service" /etc/systemd/system/
cp "$PROJECT_DIR/deployment/systemd/f1-flask.service" /etc/systemd/system/
echo "✅ Service files copied to /etc/systemd/system/"
echo ""

# Step 4: Reload systemd daemon
echo "[4/6] Reloading systemd daemon..."
systemctl daemon-reload
echo "✅ Systemd daemon reloaded"
echo ""

# Step 5: Enable services (start on boot)
echo "[5/6] Enabling services to start on boot..."
systemctl enable f1-beam-proxy.service
systemctl enable f1-flask.service
echo "✅ Services enabled"
echo ""

# Step 6: Start services
echo "[6/6] Starting services..."
systemctl start f1-beam-proxy.service
sleep 3
systemctl start f1-flask.service
sleep 3
echo "✅ Services started"
echo ""

echo "============================================================"
echo "✅ Installation Complete!"
echo "============================================================"
echo ""
echo "Service Status:"
echo "---------------"
systemctl status f1-beam-proxy.service --no-pager -l | head -10
echo ""
systemctl status f1-flask.service --no-pager -l | head -10
echo ""
echo "Commands:"
echo "---------"
echo "  Status:  sudo systemctl status f1-flask.service"
echo "  Logs:    sudo journalctl -u f1-flask.service -f"
echo "  Restart: sudo systemctl restart f1-flask.service"
echo "  Stop:    sudo systemctl stop f1-flask.service"
echo ""
echo "Services will now:"
echo "  • Start automatically on boot"
echo "  • Auto-restart on failure (10 second delay)"
echo "  • Log to: $PROJECT_DIR/logs/"
echo ""
