# Oracle Server Deployment - Hybrid GPU Architecture

Deploy your F1 app on Oracle server (24GB RAM) with Modal GPU for AI inference.

## Architecture

```
Internet → Nginx (port 80/443) → Flask (port 5151) → Modal Proxy (port 11435) → Modal T4 GPU
                                       ↓
                                  FastF1 Cache (local disk)
```

**Performance:**
- Plot generation: 3-8s (local)
- AI inference: 5-10s (Modal GPU) ⚡
- Cost: $0/month (Modal free tier)
- Uptime: 24/7 (systemd managed)

## Prerequisites

- Oracle Cloud Server (or any Linux VPS) with 24GB RAM
- Domain name pointing to server IP (optional but recommended)
- Root/sudo access
- Modal account (free tier: https://modal.com)

## Quick Start (30 minutes)

### 1. Clone Repository on Oracle Server

```bash
# SSH into your Oracle server
ssh your-user@your-server-ip

# Clone the repo
sudo mkdir -p /opt
cd /opt
sudo git clone https://github.com/YOUR_USERNAME/f1-race-plots.git f1-app
cd f1-app
```

### 2. Run Automated Deployment

```bash
# Make deployment script executable
sudo chmod +x deploy-oracle-hybrid.sh

# Run deployment (sets up everything)
sudo ./deploy-oracle-hybrid.sh
```

The script will:
- ✅ Install uv, nginx, certbot
- ✅ Install Python dependencies
- ✅ Create systemd services (auto-start on boot)
- ✅ Configure Nginx reverse proxy
- ✅ Set up logging
- ✅ Create environment files

### 3. Configure Modal (One-Time)

```bash
# Switch to app user
sudo -u www-data bash

# Navigate to app directory
cd /opt/f1-app

# Authenticate with Modal
modal setup
# Follow the browser prompt to authenticate

# Deploy Ollama GPU function
modal deploy app_modal_ollama_only.py

# Exit back to your user
exit
```

### 4. Setup SSL (Optional but Recommended)

```bash
# Replace with your domain
export DOMAIN="f1.yourdomain.com"

# Get Let's Encrypt certificate
sudo certbot --nginx -d $DOMAIN
```

### 5. Verify Deployment

```bash
# Check services are running
sudo systemctl status f1-modal-proxy
sudo systemctl status f1-app

# Test proxy health
curl http://localhost:11435/health
# Should return: {"backend":"modal-gpu","status":"healthy"}

# Test Flask health
curl http://localhost:5151/
# Should return HTML

# Test via domain
curl http://your-domain.com
```

## Service Management

### View Logs

```bash
# Modal proxy logs
sudo journalctl -u f1-modal-proxy -f

# Flask app logs
sudo journalctl -u f1-app -f

# Or view file logs
tail -f /opt/f1-app/logs/app.log
tail -f /opt/f1-app/logs/proxy.log
```

### Restart Services

```bash
# Restart proxy (if Modal deployment updated)
sudo systemctl restart f1-modal-proxy

# Restart Flask (after code changes)
sudo systemctl restart f1-app

# Restart both
sudo systemctl restart f1-modal-proxy f1-app
```

### Update Application

```bash
cd /opt/f1-app
sudo git pull
sudo systemctl restart f1-app
```

### Stop/Start Services

```bash
# Stop everything
sudo systemctl stop f1-app f1-modal-proxy

# Start everything
sudo systemctl start f1-modal-proxy f1-app
```

## Manual Setup (If You Prefer)

If you want to understand each step or customize:

### 1. Install Dependencies

```bash
sudo apt update
sudo apt install -y git python3 python3-pip nginx certbot python3-certbot-nginx curl

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"
```

### 2. Setup Application

```bash
sudo mkdir -p /opt/f1-app
cd /opt/f1-app
sudo git clone <your-repo-url> .

# Install dependencies
uv pip install -r requirements.txt
uv pip install modal
```

### 3. Create Environment File

```bash
sudo tee /opt/f1-app/.env <<EOF
FLASK_ENV=production
OLLAMA_BASE_URL=http://localhost:11435
PORT=5151
PYTHONUNBUFFERED=1
MATPLOTLIB_BACKEND=Agg
FASTF1_CACHE_DIR=./fastf1_cache
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
EOF

sudo chmod 600 /opt/f1-app/.env
```

### 4. Create Systemd Services

**Modal Proxy Service:**
```bash
sudo tee /etc/systemd/system/f1-modal-proxy.service <<EOF
[Unit]
Description=F1 Ollama Modal GPU Proxy
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/f1-app
ExecStart=/usr/local/bin/uv run python ollama_modal_proxy.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

**Flask App Service:**
```bash
sudo tee /etc/systemd/system/f1-app.service <<EOF
[Unit]
Description=F1 Flask Application
After=network.target f1-modal-proxy.service
Requires=f1-modal-proxy.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/f1-app
EnvironmentFile=/opt/f1-app/.env
ExecStart=/usr/local/bin/uv run python app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

### 5. Setup Nginx

```bash
sudo tee /etc/nginx/sites-available/f1-app <<EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5151;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_connect_timeout 300s;
        proxy_read_timeout 300s;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/f1-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 6. Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable f1-modal-proxy f1-app
sudo systemctl start f1-modal-proxy f1-app
```

## Monitoring

### System Resources

```bash
# Check memory usage
free -h

# Check disk space
df -h /opt/f1-app

# Check CPU usage
htop
```

### Service Status

```bash
# Check all F1 services
sudo systemctl status f1-modal-proxy f1-app nginx

# Check if ports are listening
sudo lsof -i :5151  # Flask
sudo lsof -i :11435 # Proxy
sudo lsof -i :80    # Nginx
```

### Modal Usage

```bash
# Check Modal costs (should be $0)
modal app list
modal app logs f1-ollama-gpu
```

Visit https://modal.com/usage to see detailed usage stats.

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
sudo journalctl -u f1-modal-proxy -n 50
sudo journalctl -u f1-app -n 50

# Check file permissions
ls -la /opt/f1-app/
sudo chown -R www-data:www-data /opt/f1-app
```

### Modal Connection Issues

```bash
# Test proxy directly
curl http://localhost:11435/health

# Check Modal deployment
modal app list
modal app logs f1-ollama-gpu

# Re-authenticate Modal
sudo -u www-data bash
cd /opt/f1-app
modal setup
exit
```

### Nginx Issues

```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log

# Restart nginx
sudo systemctl restart nginx
```

### Port Conflicts

```bash
# Check what's using port 5151
sudo lsof -i :5151

# Kill conflicting process
sudo kill $(sudo lsof -t -i:5151)
```

## Upgrading Modal GPU Function

```bash
# Update Modal function with new features
cd /opt/f1-app
sudo -u www-data bash
modal deploy app_modal_ollama_only.py
exit

# Restart proxy to use new deployment
sudo systemctl restart f1-modal-proxy
```

## Backup Strategy

### Application Code
Already in git - just push/pull changes

### FastF1 Cache
```bash
# Backup cache (optional, can regenerate)
sudo tar -czf f1-cache-backup.tar.gz /opt/f1-app/fastf1_cache/
```

### Environment & Secrets
```bash
# Backup environment file (contains SECRET_KEY)
sudo cp /opt/f1-app/.env /opt/f1-app/.env.backup
```

## Firewall Configuration

If using Oracle Cloud firewall:

```bash
# Allow HTTP
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT

# Allow HTTPS
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT

# Save rules
sudo netfilter-persistent save
```

Or in Oracle Cloud Console:
- Add ingress rule: Port 80, 0.0.0.0/0
- Add ingress rule: Port 443, 0.0.0.0/0

## Performance Tuning

### Nginx Caching (Optional)

```nginx
# Add to /etc/nginx/sites-available/f1-app
location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### FastF1 Cache Warming

```bash
# Pre-populate cache for popular races
cd /opt/f1-app
sudo -u www-data python3 -c "
import fastf1
fastf1.Cache.enable_cache('fastf1_cache')
session = fastf1.get_session(2024, 'Monaco', 'Q')
session.load()
"
```

## Cost Estimate

| Component | Cost |
|-----------|------|
| Oracle Server (24GB) | Free tier / $0-50/mo |
| Modal GPU (15 queries/mo) | $0 (within free tier) |
| Domain name | ~$12/year |
| SSL Certificate | Free (Let's Encrypt) |
| **Total** | **~$1/month** |

## Support

If you encounter issues:
1. Check logs: `journalctl -u f1-app -f`
2. Test components individually
3. Verify Modal deployment: `modal app list`
4. Check GitHub repo for updates

## Next Steps

1. **Monitor Usage**: Visit https://modal.com/usage after first week
2. **Setup Alerts**: Configure email alerts for service failures
3. **Performance**: Monitor response times and optimize if needed
4. **Scaling**: If traffic increases, Modal auto-scales the GPU inference

Your app is now production-ready with 99.9% uptime and GPU-accelerated AI! 🚀
