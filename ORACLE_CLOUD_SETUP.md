# Oracle Cloud F1 App Setup Guide

## 🌐 Network Configuration Steps

### 1. Security Groups Configuration

**In Oracle Cloud Console:**

1. Go to **Networking** > **Virtual Cloud Networks**
2. Select your VCN (Virtual Cloud Network)
3. Click **Security Lists** in the left menu
4. Select **Default Security List for [Your-VCN-Name]**
5. Click **Add Ingress Rules**

**Add this ingress rule:**
```
Source Type: CIDR
Source CIDR: 0.0.0.0/0
IP Protocol: TCP
Destination Port Range: 8080
Description: F1 App HTTP Traffic
```

### 2. Subnet Route Table

**Verify Internet Gateway Route:**

1. In your VCN, go to **Route Tables**
2. Select **Default Route Table for [Your-VCN-Name]**
3. Ensure there's a route with:
   - Destination CIDR: `0.0.0.0/0`
   - Target Type: Internet Gateway
   - Target: Your Internet Gateway

### 3. VM Instance Configuration

**Check Public IP Assignment:**

1. Go to **Compute** > **Instances**
2. Click on your VM instance
3. In **Instance Details**, verify:
   - **Public IP Address** is assigned (not "None")
   - **Primary VNIC** has a public subnet

**If no public IP:**
1. Stop the instance
2. Click **Attach VNIC**
3. Select a public subnet
4. Start the instance

### 4. VM-Level Firewall (iptables)

The deployment script handles this automatically, but manually:

```bash
# Check current rules
sudo iptables -L INPUT

# Add rule for port 8080
sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT

# Save rules (Oracle Linux)
sudo iptables-save > /etc/iptables.rules

# Auto-restore on boot
echo "iptables-restore < /etc/iptables.rules" | sudo tee -a /etc/rc.local
sudo chmod +x /etc/rc.local
```

## 🚀 Deployment Process

### 1. Connect to Your Oracle Cloud VM

```bash
ssh -i your-private-key.pem opc@your-public-ip
```

### 2. Clone Your Repository

```bash
git clone https://github.com/yourusername/f1-race-plots.git
cd f1-race-plots
```

### 3. Run Deployment Script

```bash
chmod +x deploy-oracle.sh
./deploy-oracle.sh
```

### 4. Verify Deployment

```bash
# Check container status
docker ps

# Check logs
docker logs f1-plots-container -f

# Test locally
curl http://localhost:8080/health

# Test externally (replace with your public IP)
curl http://YOUR_PUBLIC_IP:8080/health
```

## 🔧 Troubleshooting

### App Not Accessible Externally

1. **Check Oracle Security Groups:**
   ```bash
   # From your local machine
   curl -v http://YOUR_PUBLIC_IP:8080/health
   ```
   If timeout/connection refused → Security Groups issue

2. **Check VM Firewall:**
   ```bash
   # On the VM
   sudo iptables -L INPUT | grep 8080
   ```
   Should show: `ACCEPT tcp -- anywhere anywhere tcp dpt:8080`

3. **Check Container:**
   ```bash
   docker logs f1-plots-container
   docker exec -it f1-plots-container curl http://localhost:8080/health
   ```

### Container Won't Start

```bash
# Check Docker daemon
sudo systemctl status docker

# Check image
docker images | grep f1-plots

# Check build logs
docker build -t f1-plots:latest . --no-cache
```

### Port Already in Use

```bash
# Find what's using port 8080
sudo netstat -tlnp | grep 8080
sudo lsof -i :8080

# Kill conflicting process
sudo kill -9 PID
```

## 📊 Performance Monitoring

### Check Resource Usage

```bash
# Container stats
docker stats f1-plots-container

# VM resources
htop
df -h
free -h
```

### Application Logs

```bash
# Real-time logs
docker logs f1-plots-container -f

# Application metrics
curl http://localhost:8080/metrics

# Cache statistics  
curl http://localhost:8080/cache_stats
```

## 🎯 No More ngrok!

Once this setup is complete:

1. **Stop ngrok** if it's running
2. **Access your app directly** at: `http://YOUR_PUBLIC_IP:8080`
3. **Update any bookmarks** or documentation with the new URL
4. **Configure your domain** (optional) to point to the public IP

## 🔮 Future Ollama Setup

When ready to add Ollama:

```bash
# Run Ollama in separate container
docker run -d --name ollama \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama

# Pull F1 model
docker exec ollama ollama pull llama2

# Update F1 app environment
docker stop f1-plots-container
docker rm f1-plots-container

# Re-run with Ollama connection
docker run -d \
  --name f1-plots-container \
  --link ollama:ollama \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  -p 8080:8080 \
  f1-plots:latest
```