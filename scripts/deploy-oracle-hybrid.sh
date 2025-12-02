#!/bin/bash
# Oracle Server Deployment - Hybrid Architecture
# Flask on Oracle + Modal GPU for Ollama inference

set -e

echo "🚀 F1 App Oracle Deployment - Hybrid GPU Architecture"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Configuration
APP_DIR="/opt/f1-app"
APP_USER="www-data"
DOMAIN="${DOMAIN:-f1.yourdomain.com}"
PORT="${PORT:-5151}"
PROXY_PORT="${PROXY_PORT:-11435}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}✓${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (sudo)"
    exit 1
fi

echo ""
echo "Step 1: Installing dependencies..."
apt-get update
apt-get install -y git python3 python3-pip nginx certbot python3-certbot-nginx curl
log_info "Dependencies installed"

echo ""
echo "Step 2: Installing uv package manager..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
UV_BIN="$HOME/.local/bin/uv"
log_info "uv installed"

echo ""
echo "Step 3: Cloning/updating application..."
if [ -d "$APP_DIR" ]; then
    cd "$APP_DIR"
    if [ -d ".git" ]; then
        log_warn "App directory exists, pulling latest changes..."
        git pull
    else
        log_warn "App directory exists (direct transfer), skipping git pull..."
    fi
else
    git clone https://github.com/YOUR_USERNAME/f1-race-plots.git "$APP_DIR"
    cd "$APP_DIR"
fi
log_info "Application code ready"

echo ""
echo "Step 4: Installing Python dependencies..."
$UV_BIN pip install --system -r requirements.txt
log_info "Python dependencies installed"

echo ""
echo "Step 5: Installing Modal CLI..."
$UV_BIN pip install --system modal
log_info "Modal CLI installed"

echo ""
echo "Step 6: Setting up environment..."
cat > "$APP_DIR/.env" <<EOF
FLASK_ENV=production
OLLAMA_BASE_URL=http://localhost:$PROXY_PORT
PORT=$PORT
ENABLE_LEARNING=true
LEARNING_DB_PATH=./local_learning.db
MAX_LEARNING_HISTORY=100

# Flask settings
PYTHONUNBUFFERED=1
MATPLOTLIB_BACKEND=Agg

# Cache and storage
FASTF1_CACHE_DIR=./fastf1_cache
PLOTS_DIR=./static/plots
LOG_DIR=./logs

# Security
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
EOF
chmod 600 "$APP_DIR/.env"
log_info "Environment configured"

echo ""
echo "Step 7: Creating Modal proxy systemd service..."
cat > /etc/systemd/system/f1-modal-proxy.service <<EOF
[Unit]
Description=F1 Ollama Modal GPU Proxy
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/root/.local/bin/uv run python deployment/ollama_modal_proxy.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:$APP_DIR/logs/proxy.log
StandardError=append:$APP_DIR/logs/proxy-error.log

[Install]
WantedBy=multi-user.target
EOF
log_info "Modal proxy service created"

echo ""
echo "Step 8: Creating Flask app systemd service..."
cat > /etc/systemd/system/f1-app.service <<EOF
[Unit]
Description=F1 Telemetry Flask Application
After=network.target f1-modal-proxy.service
Wants=network-online.target
Requires=f1-modal-proxy.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment="PATH=$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/root/.local/bin/uv run python run.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:$APP_DIR/logs/app.log
StandardError=append:$APP_DIR/logs/app-error.log

[Install]
WantedBy=multi-user.target
EOF
log_info "Flask app service created"

echo ""
echo "Step 9: Creating log directory..."
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/fastf1_cache"
mkdir -p "$APP_DIR/static/plots"
chown -R $APP_USER:$APP_USER "$APP_DIR"
log_info "Directories created"

echo ""
echo "Step 10: Configuring Nginx reverse proxy..."
cat > /etc/nginx/sites-available/f1-app <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/f1-app-access.log;
    error_log /var/log/nginx/f1-app-error.log;

    location / {
        proxy_pass http://localhost:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for long-running requests
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # Static files (optional optimization)
    location /static {
        alias $APP_DIR/static;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

ln -sf /etc/nginx/sites-available/f1-app /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
log_info "Nginx configured"

echo ""
echo "Step 11: Enabling and starting services..."
systemctl daemon-reload
systemctl enable f1-modal-proxy
systemctl enable f1-app
systemctl start f1-modal-proxy
sleep 3  # Wait for proxy to start
systemctl start f1-app
log_info "Services started"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure Modal (one-time setup):"
echo "   sudo -u $APP_USER bash"
echo "   cd $APP_DIR"
echo "   modal setup  # Follow authentication prompts"
echo "   modal deploy app_modal_ollama_only.py"
echo "   exit"
echo ""
echo "2. Setup SSL certificate (recommended):"
echo "   certbot --nginx -d $DOMAIN"
echo ""
echo "3. Check service status:"
echo "   systemctl status f1-modal-proxy"
echo "   systemctl status f1-app"
echo ""
echo "4. View logs:"
echo "   journalctl -u f1-modal-proxy -f"
echo "   journalctl -u f1-app -f"
echo "   tail -f $APP_DIR/logs/app.log"
echo ""
echo "5. Test the application:"
echo "   curl http://localhost:$PORT"
echo "   curl http://localhost:$PROXY_PORT/health"
echo ""
echo "Your app will be available at: http://$DOMAIN"
echo ""
