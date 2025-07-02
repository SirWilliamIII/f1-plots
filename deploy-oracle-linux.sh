#!/bin/bash

# F1 Race Plots - Oracle Linux Deployment Script
# Optimized for Oracle Linux (OL) instead of Ubuntu

set -e

echo "🚀 Starting F1 Race Plots deployment on Oracle Linux..."

# Detect Oracle Linux version
if [[ -f /etc/oracle-release ]]; then
    echo "✅ Detected Oracle Linux"
    OS_VERSION=$(cat /etc/oracle-release)
    echo "OS: $OS_VERSION"
else
    echo "⚠️ Warning: Not Oracle Linux, proceeding anyway..."
fi

# Update system using dnf/yum
echo "📦 Updating system packages..."
if command -v dnf &> /dev/null; then
    sudo dnf update -y
    PACKAGE_MANAGER="dnf"
else
    sudo yum update -y
    PACKAGE_MANAGER="yum"
fi

# Install required packages
echo "🛠️ Installing required packages..."
sudo $PACKAGE_MANAGER install -y curl wget git htop unzip

# Install Docker for Oracle Linux
echo "🐳 Installing Docker for Oracle Linux..."
if ! command -v docker &> /dev/null; then
    # Add Docker repository for Oracle Linux
    sudo $PACKAGE_MANAGER install -y yum-utils
    sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    
    # Install Docker CE
    sudo $PACKAGE_MANAGER install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start and enable Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    echo "✅ Docker installed successfully"
else
    echo "✅ Docker already installed"
fi

# Install Docker Compose (standalone)
echo "🔧 Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

# Configure firewall (Oracle Linux uses firewalld)
echo "🔒 Configuring firewall..."
if systemctl is-active --quiet firewalld; then
    echo "Configuring firewalld..."
    sudo firewall-cmd --permanent --add-port=22/tcp
    sudo firewall-cmd --permanent --add-port=80/tcp
    sudo firewall-cmd --permanent --add-port=443/tcp
    sudo firewall-cmd --permanent --add-port=8080/tcp
    sudo firewall-cmd --reload
    echo "✅ Firewall configured"
else
    echo "⚠️ firewalld not active, enabling..."
    sudo systemctl enable firewalld
    sudo systemctl start firewalld
    sudo firewall-cmd --permanent --add-port=22/tcp
    sudo firewall-cmd --permanent --add-port=80/tcp
    sudo firewall-cmd --permanent --add-port=443/tcp
    sudo firewall-cmd --permanent --add-port=8080/tcp
    sudo firewall-cmd --reload
fi

# Create app directory
echo "📁 Setting up application directory..."
sudo mkdir -p /opt/f1-app
sudo chown $USER:$USER /opt/f1-app
cd /opt/f1-app

# Create required directories
mkdir -p {fastf1_cache,static/plots,logs,ssl}

# Copy files from deployment directory
echo "📋 Copying application files..."
if [[ -d "/tmp/f1-deploy" ]]; then
    cp -r /tmp/f1-deploy/* /opt/f1-app/
    echo "✅ Application files copied"
else
    echo "⚠️ No deployment files found in /tmp/f1-deploy"
fi

# Create Oracle Linux optimized docker-compose file
echo "🔧 Creating Oracle Linux docker-compose configuration..."
cat > docker-compose.oracle-linux.yml << 'EOF'
version: '3.8'

services:
  flask-app:
    image: python:3.12-slim
    ports:
      - "8080:8080"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - PYTHONUNBUFFERED=1
      - MATPLOTLIB_BACKEND=Agg
      - PORT=8080
      - FLASK_ENV=production
    volumes:
      - ./:/app
      - ./fastf1_cache:/app/fastf1_cache
      - ./static/plots:/app/static/plots
      - ./logs:/app/logs
    working_dir: /app
    command: >
      bash -c "
        pip install --no-cache-dir -r requirements.txt &&
        python app.py
      "
    depends_on:
      ollama:
        condition: service_healthy
    networks:
      - f1-network
    restart: unless-stopped
    mem_limit: 8g
    cpus: 2

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - f1-network
    restart: unless-stopped
    environment:
      - OLLAMA_KEEP_ALIVE=24h
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_ORIGINS=*
      - OLLAMA_NUM_PARALLEL=2
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 180s
    mem_limit: 12g
    cpus: 4

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - flask-app
    networks:
      - f1-network
    restart: unless-stopped
    mem_limit: 512m

volumes:
  ollama_data:

networks:
  f1-network:
    driver: bridge
EOF

# Create systemd service for Oracle Linux
echo "🔄 Creating systemd service..."
sudo tee /etc/systemd/system/f1-app.service > /dev/null <<EOF
[Unit]
Description=F1 Race Plots Application
After=docker.service network.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/f1-app
ExecStart=/usr/local/bin/docker-compose -f docker-compose.oracle-linux.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.oracle-linux.yml down
ExecReload=/usr/local/bin/docker-compose -f docker-compose.oracle-linux.yml restart
TimeoutStartSec=300
User=$USER
Group=docker
Environment=PATH=/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
sudo systemctl daemon-reload
sudo systemctl enable f1-app.service

# Create management scripts
echo "📊 Creating management scripts..."

# Health check script
tee ~/f1-health.sh > /dev/null <<'EOF'
#!/bin/bash
echo "=== F1 App Health Check $(date) ==="
echo ""

# Check services
echo "🐳 Docker Services:"
cd /opt/f1-app && docker-compose -f docker-compose.oracle-linux.yml ps

echo ""
echo "🌐 Service Health:"
echo -n "Flask App (port 8080): "
timeout 5 curl -s -f http://localhost:8080/ > /dev/null && echo "✅ Running" || echo "❌ Down"

echo -n "Ollama (port 11434): "
timeout 5 curl -s -f http://localhost:11434/api/tags > /dev/null && echo "✅ Running" || echo "❌ Down"

echo -n "Nginx (port 80): "
timeout 5 curl -s -f http://localhost:80/health > /dev/null && echo "✅ Running" || echo "❌ Down"

echo ""
echo "💻 System Resources:"
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2 " (" int($3/$2*100) "%)"}')"
echo "Disk: $(df -h /opt/f1-app | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
echo "Load: $(uptime | awk -F'load average:' '{print $2}' | sed 's/^[ \t]*//')"

echo ""
echo "📈 Recent Logs (last 10 lines):"
cd /opt/f1-app && docker-compose -f docker-compose.oracle-linux.yml logs --tail=10 flask-app
EOF
chmod +x ~/f1-health.sh

# Management script
tee ~/f1-manage.sh > /dev/null <<'EOF'
#!/bin/bash
cd /opt/f1-app

case "$1" in
    start)
        echo "🚀 Starting F1 App..."
        docker-compose -f docker-compose.oracle-linux.yml up -d
        ;;
    stop)
        echo "🛑 Stopping F1 App..."
        docker-compose -f docker-compose.oracle-linux.yml down
        ;;
    restart)
        echo "🔄 Restarting F1 App..."
        docker-compose -f docker-compose.oracle-linux.yml restart
        ;;
    logs)
        echo "📋 Showing logs..."
        docker-compose -f docker-compose.oracle-linux.yml logs -f ${2:-flask-app}
        ;;
    pull)
        echo "🔄 Pulling latest images..."
        docker-compose -f docker-compose.oracle-linux.yml pull
        ;;
    build)
        echo "🔨 Building images..."
        docker-compose -f docker-compose.oracle-linux.yml build --no-cache
        ;;
    status)
        ~/f1-health.sh
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|pull|build|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start all services"
        echo "  stop    - Stop all services"  
        echo "  restart - Restart all services"
        echo "  logs    - Show logs (add service name for specific service)"
        echo "  pull    - Pull latest Docker images"
        echo "  build   - Build Docker images"
        echo "  status  - Show health status"
        ;;
esac
EOF
chmod +x ~/f1-manage.sh

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "Unable to detect")

echo ""
echo "🎉 Oracle Linux deployment setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Start the application: ~/f1-manage.sh start"
echo "2. Check status: ~/f1-manage.sh status"
echo "3. View logs: ~/f1-manage.sh logs"
echo ""
echo "🌍 Your public IP: $PUBLIC_IP"
echo "🔗 App will be available at: http://$PUBLIC_IP"
echo ""
echo "⚡ Quick commands:"
echo "  - Health check: ~/f1-health.sh"
echo "  - Manage app: ~/f1-manage.sh {start|stop|restart|status|logs}"
echo "  - System service: sudo systemctl {start|stop|restart|status} f1-app"
echo ""
echo "🔧 Note: After first boot, you may need to logout/login for docker group to take effect"
echo "Or run: newgrp docker"