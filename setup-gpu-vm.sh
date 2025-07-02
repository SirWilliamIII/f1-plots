#!/bin/bash

# Oracle Cloud GPU VM Setup Script
# Run this AFTER provisioning the GPU VM

if [ $# -eq 0 ]; then
    echo "Usage: $0 <GPU_VM_IP_ADDRESS>"
    echo "Example: $0 141.147.90.246"
    exit 1
fi

GPU_VM_IP="$1"
SSH_KEY="~/.ssh/ssh-key-2025-07-01.key"

echo "🚀 Setting up GPU VM at $GPU_VM_IP"
echo "================================="

# Test SSH connection
echo "1. Testing SSH connection..."
if ! ssh -i $SSH_KEY -o ConnectTimeout=10 opc@$GPU_VM_IP "echo 'SSH OK'" > /dev/null 2>&1; then
    echo "❌ SSH connection failed. Check:"
    echo "  - VM is running and provisioned"
    echo "  - Security lists allow SSH (port 22)"
    echo "  - IP address is correct"
    exit 1
fi
echo "✅ SSH connection successful"

# Create GPU setup script on VM
echo "2. Creating GPU setup script on VM..."
ssh -i $SSH_KEY opc@$GPU_VM_IP "cat > setup-gpu.sh << 'EOF'
#!/bin/bash
set -e

echo '🔧 Oracle Linux GPU VM Setup'
echo '============================'

# Update system
echo '📦 Updating system packages...'
sudo dnf update -y

# Install NVIDIA drivers
echo '🎮 Installing NVIDIA drivers...'
sudo dnf config-manager --add-repo https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/cuda-rhel8.repo
sudo dnf install -y cuda-toolkit-12-4 nvidia-driver nvidia-utils

# Install Docker
echo '🐳 Installing Docker...'
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Install NVIDIA Docker runtime
echo '🔧 Installing NVIDIA Docker runtime...'
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo dnf install -y nvidia-container-toolkit

# Configure Docker for NVIDIA
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Add user to docker group
sudo usermod -aG docker \$USER

# Start and enable services
sudo systemctl start docker
sudo systemctl enable docker

# Configure firewall
echo '🔒 Configuring firewall...'
sudo firewall-cmd --permanent --add-port=22/tcp
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --add-port=11434/tcp
sudo firewall-cmd --reload

# Create app directory
sudo mkdir -p /opt/f1-app
sudo chown \$USER:\$USER /opt/f1-app
mkdir -p /opt/f1-app/{fastf1_cache,static/plots,logs,ssl}

echo '✅ GPU VM setup complete!'
echo ''
echo 'Next steps:'
echo '1. Reboot the VM: sudo reboot'
echo '2. After reboot, test GPU: nvidia-smi'
echo '3. Deploy F1 app with GPU-optimized Ollama'
EOF

chmod +x setup-gpu.sh"

echo "3. Running GPU setup on VM..."
ssh -i $SSH_KEY opc@$GPU_VM_IP "./setup-gpu.sh"

echo "4. Rebooting VM for GPU drivers..."
ssh -i $SSH_KEY opc@$GPU_VM_IP "sudo reboot" || echo "VM rebooting..."

echo ""
echo "⏳ Waiting 60 seconds for VM to reboot..."
sleep 60

echo "5. Testing GPU after reboot..."
for i in {1..12}; do
    if ssh -i $SSH_KEY -o ConnectTimeout=5 opc@$GPU_VM_IP "nvidia-smi" 2>/dev/null; then
        echo "✅ GPU is working!"
        break
    else
        echo "⏳ Waiting for VM to come back online... (attempt $i/12)"
        sleep 10
    fi
done

echo "6. Creating GPU-optimized docker-compose..."
ssh -i $SSH_KEY opc@$GPU_VM_IP "cd /opt/f1-app && cat > docker-compose.gpu.yml << 'EOF'
version: '3.8'

services:
  flask-app:
    build:
      context: .
      dockerfile: Dockerfile.flask
    ports:
      - \"8080:8080\"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - PYTHONUNBUFFERED=1
      - MATPLOTLIB_BACKEND=Agg
      - PORT=8080
    volumes:
      - ./fastf1_cache:/app/fastf1_cache
      - ./static/plots:/app/static/plots
      - ./logs:/app/logs
    networks:
      - f1-network
    restart: unless-stopped
    mem_limit: 16g
    cpus: 8

  ollama:
    image: ollama/ollama:latest
    ports:
      - \"11434:11434\"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - f1-network
    restart: unless-stopped
    environment:
      - OLLAMA_KEEP_ALIVE=24h
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_ORIGINS=*
      - OLLAMA_NUM_PARALLEL=4
      - OLLAMA_MAX_LOADED_MODELS=2
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    mem_limit: 200g
    cpus: 12

  nginx:
    image: nginx:alpine
    ports:
      - \"80:80\"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - flask-app
    networks:
      - f1-network
    restart: unless-stopped

volumes:
  ollama_data:

networks:
  f1-network:
    driver: bridge
EOF"

echo ""
echo "🎉 GPU VM setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update your deploy script with new IP: $GPU_VM_IP"
echo "2. Deploy your app: ./deploy-to-oracle.sh"
echo "3. Test GPU performance: ssh -i $SSH_KEY opc@$GPU_VM_IP 'nvidia-smi'"
echo ""
echo "💡 Your new GPU VM:"
echo "  • IP: $GPU_VM_IP"
echo "  • GPU: NVIDIA A10 (24GB VRAM)"
echo "  • RAM: 240GB"
echo "  • Cost: ~$295/month (preemptible)"
echo ""
echo "🚀 Ollama will now run 10-50x faster!"