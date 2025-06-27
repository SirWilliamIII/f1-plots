#!/bin/bash

# Oracle Cloud F1 Race Plots + Ollama Deployment Script
# Run this on your Oracle Cloud Ubuntu instance

set -e

echo "🚀 Starting F1 Race Plots + Ollama deployment on Oracle Cloud..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
echo "🐳 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
echo "🔧 Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Oracle Cloud CLI (optional)
echo "☁️ Installing Oracle Cloud CLI..."
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" -- --accept-all-defaults

# Install useful tools
echo "🛠️ Installing additional tools..."
sudo apt install -y htop curl wget git ufw

# Configure firewall (Oracle Cloud uses iptables + Security Lists)
echo "🔒 Configuring local firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# Create app directory
echo "📁 Creating application directory..."
mkdir -p ~/f1-app
cd ~/f1-app

# Create SSL directory
mkdir -p ssl
echo "⚠️  Don't forget to add your SSL certificates to ~/f1-app/ssl/"

# Create Oracle-optimized docker-compose file
echo "🔧 Creating Oracle Cloud docker-compose configuration..."
cat > docker-compose.oracle.yml << 'EOF'
version: '3.8'

services:
  flask-app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - PYTHONUNBUFFERED=1
      - MATPLOTLIB_BACKEND=Agg
      - PORT=8080
      - FLASK_ENV=production
    volumes:
      - ./fastf1_cache:/app/fastf1_cache
      - ./static/plots:/app/static/plots
      - ./logs:/app/logs
    depends_on:
      ollama:
        condition: service_healthy
    networks:
      - f1-network
    restart: unless-stopped
    # Oracle Cloud optimized limits (24GB total RAM)
    mem_limit: 8g
    cpus: 2
    deploy:
      resources:
        limits:
          memory: 8g
        reservations:
          memory: 3g

  ollama:
    build:
      context: .
      dockerfile: Dockerfile.ollama.fixed
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
    # Oracle Cloud optimized limits (24GB total RAM)
    mem_limit: 16g
    cpus: 4
    deploy:
      resources:
        limits:
          memory: 16g
        reservations:
          memory: 6g

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

# Create systemd service for auto-start
echo "🔄 Creating systemd service..."
sudo tee /etc/systemd/system/f1-app.service > /dev/null <<EOF
[Unit]
Description=F1 Race Plots Application
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/$USER/f1-app
ExecStart=/usr/local/bin/docker-compose -f docker-compose.oracle.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.oracle.yml down
TimeoutStartSec=0
User=$USER
Group=docker

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable f1-app.service

# Setup log rotation
echo "📊 Setting up log rotation..."
sudo tee /etc/logrotate.d/f1-app > /dev/null <<EOF
/home/$USER/f1-app/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}
EOF

# Create Oracle Cloud monitoring script
echo "📈 Creating Oracle Cloud monitoring script..."
tee ~/monitor.sh > /dev/null <<'EOF'
#!/bin/bash
echo "=== F1 App Status ==="
docker-compose -f ~/f1-app/docker-compose.oracle.yml ps
echo ""

echo "=== Oracle Cloud Instance Info ==="
curl -s -H "Authorization: Bearer Oracle" http://169.254.169.254/opc/v1/instance/ | jq '.' 2>/dev/null || echo "OCI metadata not available"
echo ""

echo "=== System Resources ==="
free -h
echo ""
df -h
echo ""

echo "=== Network ==="
ss -tuln | grep -E ':(80|443|8080|11434)'
echo ""

echo "=== Docker Stats ==="
docker stats --no-stream
EOF
chmod +x ~/monitor.sh

# Create backup script with Oracle Object Storage support
echo "💾 Creating backup script..."
tee ~/backup.sh > /dev/null <<'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="f1-app-backup-$DATE.tar.gz"

echo "Creating backup: $BACKUP_FILE"
cd ~/f1-app
tar -czf "../$BACKUP_FILE" fastf1_cache/ static/plots/ logs/ *.yml *.conf

echo "Backup created: ../$BACKUP_FILE"
echo "To upload to Oracle Object Storage:"
echo "oci os object put --bucket-name your-bucket --file ../$BACKUP_FILE"
EOF
chmod +x ~/backup.sh

# Create health check script
echo "🏥 Creating health check script..."
tee ~/health-check.sh > /dev/null <<'EOF'
#!/bin/bash
echo "=== F1 App Health Check ==="
echo -n "Flask App: "
curl -s -f http://localhost:8080/ > /dev/null && echo "✅ Running" || echo "❌ Down"

echo -n "Ollama: "
curl -s -f http://localhost:11434/api/tags > /dev/null && echo "✅ Running" || echo "❌ Down"

echo -n "Nginx: "
curl -s -f http://localhost:80/ > /dev/null && echo "✅ Running" || echo "❌ Down"

echo ""
echo "=== Resource Usage ==="
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
echo "Load: $(uptime | awk -F'load average:' '{print $2}')"
EOF
chmod +x ~/health-check.sh

# Check if this is an ARM instance
ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" ]]; then
    echo "🎯 Detected ARM64 architecture - optimizing for Oracle Always Free Tier"
    echo "This instance is eligible for Always Free Tier!"
else
    echo "🖥️ Detected x86_64 architecture"
fi

echo ""
echo "🎉 Oracle Cloud deployment setup complete!"
echo ""
echo "Next steps:"
echo "1. Upload your F1 app code to ~/f1-app/"
echo "2. Add SSL certificates to ~/f1-app/ssl/ (cert.pem and key.pem)"
echo "3. Configure Oracle Cloud Security Lists to allow ports 80, 443"
echo "4. Run: cd ~/f1-app && docker-compose -f docker-compose.oracle.yml up -d"
echo "5. Monitor with: ~/monitor.sh"
echo "6. Health check: ~/health-check.sh"
echo "7. Backup: ~/backup.sh"
echo ""
echo "💰 Oracle Cloud Benefits:"
if [[ "$ARCH" == "aarch64" ]]; then
    echo "   - Always Free Tier: $0/month (up to 4 OCPU, 24GB RAM)"
else
    echo "   - VM.Standard.E4.Flex: ~$10-15/month"
fi
echo "   - Built-in monitoring and logging"
echo "   - Global regions available"
echo ""
echo "🌍 Your app will be available at: http://$(curl -s ifconfig.me)"
echo "📖 See ORACLE-DEPLOYMENT.md for detailed instructions"
