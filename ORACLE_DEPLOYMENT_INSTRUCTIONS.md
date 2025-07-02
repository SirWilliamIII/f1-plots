# 🚀 F1 Race Plots - Oracle VM Deployment Instructions

## Quick Deployment Steps

Since SSH might be blocked by Oracle Cloud security lists, here's how to deploy your F1 app directly on your Oracle VM:

### 1. Fix Oracle Cloud Security Lists

First, ensure your Oracle Cloud instance allows SSH and HTTP traffic:

**In Oracle Cloud Console:**
1. Go to **Compute** → **Instances** → Click your instance
2. Click **Subnet** → **Security Lists** → **Default Security List**
3. Click **Add Ingress Rules** and add:
   ```
   Source: 0.0.0.0/0, Protocol: TCP, Port: 22 (SSH)
   Source: 0.0.0.0/0, Protocol: TCP, Port: 80 (HTTP)
   Source: 0.0.0.0/0, Protocol: TCP, Port: 443 (HTTPS)
   Source: 0.0.0.0/0, Protocol: TCP, Port: 8080 (Flask App)
   ```

### 2. SSH into your Oracle VM

```bash
ssh ubuntu@141.147.90.245
```

### 3. Run the deployment script directly on the VM

```bash
# Download the deployment script
curl -fsSL https://raw.githubusercontent.com/your-username/f1-race-plots/main/deploy-to-oracle.sh -o deploy-to-oracle.sh

# Or create it manually:
cat > deploy-to-oracle.sh << 'EOF'
# [Copy the entire deploy-to-oracle.sh content here]
EOF

chmod +x deploy-to-oracle.sh
sudo ./deploy-to-oracle.sh
```

### 4. Upload your F1 app files

Since SSH/SCP might be blocked, you have several options:

#### Option A: Clone from Git (Recommended)
```bash
cd /opt/f1-app
git clone https://github.com/your-username/f1-race-plots.git .
# Or if you don't have a git repo, use wget/curl to download files
```

#### Option B: Use Oracle Cloud Console File Upload
1. Go to **Compute** → **Instances** → **Console Connection**
2. Use the browser-based console to upload files

#### Option C: Manual file creation
```bash
cd /opt/f1-app

# Create each file manually using nano/vim
# Copy-paste content from local files

# Key files to create:
nano app.py              # Main Flask application
nano requirements.txt    # Python dependencies
nano session_manager.py  # Session management
nano utils.py            # Utility functions
nano config.py           # Configuration

# Create templates directory
mkdir -p templates
nano templates/index.html
nano templates/result.html
nano templates/error.html

# Create static directory
mkdir -p static/css static/js
nano static/styles.css
nano static/main.js
```

### 5. Start the application

```bash
# Start the services
~/f1-manage.sh start

# Check status
~/f1-health.sh

# View logs
~/f1-manage.sh logs
```

### 6. Set up Ollama model

Once the services are running:

```bash
# Access the Ollama container
docker exec -it f1-app-ollama-1 bash

# Pull and create the F1 expert model
ollama pull llama3.2:3b
ollama create f1expert -f /app/f1expert.modelfile

# Exit the container
exit
```

## 🔧 Troubleshooting

### SSH Connection Issues
```bash
# Check if SSH is allowed in security lists
# In Oracle Cloud Console → Networking → Security Lists
# Ensure port 22 is open from your IP or 0.0.0.0/0

# Alternative: Use Oracle Cloud Console browser terminal
# Go to Compute → Instances → Connect → Cloud Shell Connection
```

### Service Issues
```bash
# Check service status
sudo systemctl status f1-app

# Restart services
~/f1-manage.sh restart

# Check Docker logs
docker logs f1-app-flask-app-1
docker logs f1-app-ollama-1
docker logs f1-app-nginx-1
```

### Memory Issues
```bash
# Check memory usage
free -h
docker stats

# If running out of memory, adjust limits in docker-compose.oracle.yml
# Reduce mem_limit values for services
```

## 📱 Management Commands

```bash
# Health check
~/f1-health.sh

# Start/stop/restart services
~/f1-manage.sh start
~/f1-manage.sh stop
~/f1-manage.sh restart

# View logs
~/f1-manage.sh logs
~/f1-manage.sh logs ollama

# Update application
~/f1-manage.sh update

# System service commands
sudo systemctl start f1-app
sudo systemctl stop f1-app
sudo systemctl status f1-app
```

## 🌍 Access Your App

Once deployed, your F1 Race Plots app will be available at:
- **HTTP:** http://141.147.90.245
- **Direct Flask:** http://141.147.90.245:8080
- **Ollama API:** http://141.147.90.245:11434

## 💡 Next Steps

1. **SSL Certificate:** Add SSL certificates to `/opt/f1-app/ssl/` for HTTPS
2. **Domain:** Point a domain to 141.147.90.245 for easier access
3. **Monitoring:** Set up log monitoring and alerts
4. **Backup:** Configure automated backups of F1 cache data

## 🆘 Support

If you encounter issues:
1. Check `/opt/f1-app/logs/` for application logs
2. Run `~/f1-health.sh` for system status
3. Check `docker logs [container_name]` for container-specific issues
4. Verify Oracle Cloud security lists allow required ports

Your beast Oracle VM is ready to serve F1 telemetry data! 🏎️💨