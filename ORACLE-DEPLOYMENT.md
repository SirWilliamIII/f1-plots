# F1 Race Plots - Oracle Cloud Deployment

Deploy your F1 telemetry analysis app with Ollama AI on Oracle Cloud Infrastructure for **~$5-15/month**.

## 🚀 Quick Start

### 1. Create Oracle Cloud Compute Instance
- Go to [Oracle Cloud Console](https://cloud.oracle.com/)
- Navigate to Compute > Instances
- Create new instance:
  - **Shape:** VM.Standard.E4.Flex (2 OCPU, 16GB RAM) or VM.Standard.A1.Flex (ARM)
  - **Image:** Ubuntu 22.04
  - **Network:** Default VCN with public subnet
  - **SSH Keys:** Add your public key
  - **Boot Volume:** 100GB

### 2. Configure Security Rules
```bash
# In OCI Console: Networking > Virtual Cloud Networks > Default VCN > Security Lists
# Add Ingress Rules:
# - Port 80 (HTTP): 0.0.0.0/0
# - Port 443 (HTTPS): 0.0.0.0/0
# - Port 22 (SSH): Your IP/32
```

### 3. Initial Server Setup
```bash
# SSH into your instance
ssh ubuntu@YOUR_INSTANCE_IP

# Run the Oracle deployment script
curl -fsSL https://raw.githubusercontent.com/your-repo/deploy-oracle.sh | bash

# Reboot to ensure all changes take effect
sudo reboot
```

### 4. Deploy Your App
```bash
# SSH back in after reboot
ssh ubuntu@YOUR_INSTANCE_IP

# Navigate to app directory
cd ~/f1-app

# Clone or upload your app files
git clone https://github.com/your-repo/f1-race-plots.git .

# Start the application
docker-compose -f docker-compose.oracle.yml up -d
```

## 📋 Oracle-Specific Configuration

### Resource Allocation
- **VM.Standard.E4.Flex (2 OCPU, 16GB):** ~$10-15/month
  - Flask App: 4GB RAM, 1 CPU
  - Ollama: 8GB RAM, 1 CPU
  - System: 4GB RAM reserved

- **VM.Standard.A1.Flex (ARM, Always Free Tier):** $0/month
  - 4 OCPU, 24GB RAM (always free eligible)
  - Flask App: 6GB RAM, 2 CPU
  - Ollama: 12GB RAM, 2 CPU

### Network Security Groups
Oracle Cloud uses Network Security Groups (NSGs) instead of traditional security groups:

```bash
# Create NSG rules via OCI CLI (optional)
oci network nsg-rule create \
  --nsg-id YOUR_NSG_ID \
  --direction INGRESS \
  --protocol TCP \
  --source "0.0.0.0/0" \
  --destination-port-range '{"min": 80, "max": 80}'
```

## 🔧 Oracle Cloud Features

### Always Free Tier Benefits
- 2 VM instances (VM.Standard.A1.Flex)
- Up to 4 OCPU and 24GB RAM total
- 200GB block storage
- Perfect for F1 app deployment

### Object Storage Integration
```bash
# Optional: Use Oracle Object Storage for F1 cache backups
oci os object put \
  --bucket-name f1-cache-backup \
  --file ~/f1-app/fastf1_cache.tar.gz
```

### Load Balancer (Optional)
For high availability, add an Oracle Load Balancer:
- Navigate to Networking > Load Balancers
- Create Load Balancer with backend set pointing to your instance

## 📊 Monitoring with Oracle Cloud

### Instance Metrics
Oracle Cloud provides built-in monitoring:
- CPU utilization
- Memory usage
- Network I/O
- Custom metrics via monitoring agent

### Logging
```bash
# View application logs
docker-compose -f docker-compose.oracle.yml logs -f flask-app

# Oracle Cloud Logging (optional)
# Configure log forwarding to OCI Logging service
```

## 🛠️ Maintenance Scripts

### Health Check
```bash
# Create health check script
cat > ~/health-check.sh << 'EOF'
#!/bin/bash
echo "=== F1 App Health Check ==="
curl -f http://localhost:8080/ > /dev/null && echo "✅ App is running" || echo "❌ App is down"
curl -f http://localhost:11434/api/tags > /dev/null && echo "✅ Ollama is running" || echo "❌ Ollama is down"
echo ""
echo "=== System Resources ==="
free -h
df -h /
EOF
chmod +x ~/health-check.sh
```

### Backup Script
```bash
# Create backup script for Oracle Object Storage
cat > ~/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="f1-app-backup-$DATE.tar.gz"

cd ~/f1-app
tar -czf "$BACKUP_FILE" fastf1_cache/ static/plots/ logs/

# Optional: Upload to Object Storage
# oci os object put --bucket-name f1-backups --file "$BACKUP_FILE"

echo "Backup created: $BACKUP_FILE"
EOF
chmod +x ~/backup.sh
```

## 💰 Cost Comparison

**Oracle Cloud Options:**

1. **Always Free Tier (ARM):** $0/month
   - VM.Standard.A1.Flex (4 OCPU, 24GB RAM)
   - Perfect for F1 app + Ollama
   - 200GB storage included

2. **VM.Standard.E4.Flex:** ~$10-15/month
   - x86 architecture
   - 2 OCPU, 16GB RAM
   - More predictable performance

**vs Other Providers:**
- AWS t3.large: ~$60/month
- GCP e2-standard-4: ~$120/month
- Azure Standard_D4s_v3: ~$140/month

## 🚨 Troubleshooting

### Common Issues

**Instance won't start:**
```bash
# Check instance status in OCI Console
# Verify security list rules allow SSH (port 22)
```

**Can't access app:**
```bash
# Verify security list allows ports 80/443
# Check if services are running:
docker-compose -f docker-compose.oracle.yml ps
```

**ARM compatibility:**
```bash
# Some Docker images may need ARM versions
# Modify docker-compose.oracle.yml to use ARM-compatible images
```

### Performance Optimization

**For ARM instances:**
```bash
# Use ARM-optimized Python base image in Dockerfile
FROM python:3.12-slim-bullseye
# Or use ARM-specific tags when available
FROM --platform=linux/arm64 python:3.12-slim
```

**Memory optimization:**
```bash
# Adjust memory limits in docker-compose.oracle.yml
# Monitor with: docker stats
```

## 🎯 Oracle Cloud Advantages

1. **Always Free Tier:** Perfect for personal projects
2. **ARM processors:** Excellent performance/cost ratio
3. **Global regions:** Choose closest to your users
4. **Enterprise features:** Built-in monitoring, logging, security
5. **Predictable pricing:** No surprise bills

Your F1 analysis app can run completely free on Oracle's Always Free Tier! 🏎️
