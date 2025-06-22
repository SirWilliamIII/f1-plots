#!/bin/bash
set -e  # Exit on any error

# === Oracle Cloud F1 App Deployment Script ===
echo "🏎️  F1 Telemetry App - Oracle Cloud Deployment"
echo "=============================================="

# === CONFIG ===
APP_NAME="f1-plots"
CONTAINER_NAME="f1-plots-container"
IMAGE_TAG="f1-plots:latest"
HOST_PORT="8080"
CONTAINER_PORT="8080"
DATA_DIR="/opt/f1-plots-data"

# === PRE-FLIGHT CHECKS ===
echo -e "\n📋 Pre-flight checks..."

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Installing Docker..."
    sudo yum update -y
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "✅ Docker installed. Please logout and login again, then re-run this script."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon not running. Starting Docker..."
    sudo systemctl start docker
fi

echo "✅ Docker is running"

# === FIREWALL CONFIGURATION ===
echo -e "\n🔥 Configuring firewall..."

# Open port 8080 for HTTP traffic
if ! sudo iptables -L INPUT | grep -q "dpt:8080"; then
    echo "Opening port 8080..."
    sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
    
    # Make iptables rules persistent
    if command -v iptables-save &> /dev/null; then
        sudo iptables-save > /etc/iptables.rules
        echo "iptables-restore < /etc/iptables.rules" | sudo tee /etc/rc.local
        sudo chmod +x /etc/rc.local
    fi
    echo "✅ Port 8080 opened in firewall"
else
    echo "✅ Port 8080 already open"
fi

# === CREATE DATA DIRECTORY ===
echo -e "\n📁 Setting up data directory..."
sudo mkdir -p $DATA_DIR/fastf1_cache
sudo mkdir -p $DATA_DIR/logs
sudo chown -R $USER:$USER $DATA_DIR
echo "✅ Data directory created at $DATA_DIR"

# === STOP EXISTING CONTAINER ===
echo -e "\n🛑 Stopping existing container..."
if docker ps -a --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker stop $CONTAINER_NAME || true
    docker rm $CONTAINER_NAME || true
    echo "✅ Existing container removed"
else
    echo "✅ No existing container to remove"
fi

# === BUILD IMAGE ===
echo -e "\n🔧 Building Docker image..."
docker build -t $IMAGE_TAG . --no-cache
echo "✅ Docker image built: $IMAGE_TAG"

# === RUN CONTAINER ===
echo -e "\n🚀 Starting application container..."
docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -p $HOST_PORT:$CONTAINER_PORT \
    -v $DATA_DIR/fastf1_cache:/app/fastf1_cache \
    -v $DATA_DIR/logs:/app/logs \
    -e PORT=$CONTAINER_PORT \
    -e PYTHONUNBUFFERED=1 \
    -e MATPLOTLIB_BACKEND=Agg \
    $IMAGE_TAG

# Wait a moment for container to start
sleep 5

# === HEALTH CHECK ===
echo -e "\n🏥 Health check..."
if docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -q "^${CONTAINER_NAME}.*Up"; then
    echo "✅ Container is running"
    
    # Test internal connectivity
    if docker exec $CONTAINER_NAME curl -f http://localhost:$CONTAINER_PORT/health &>/dev/null; then
        echo "✅ Internal health check passed"
    else
        echo "⚠️ Internal health check failed (may be normal on first start)"
    fi
    
    # Test external connectivity
    PUBLIC_IP=$(curl -s http://169.254.169.254/opc/v1/instance/metadata/public-ip || echo "unknown")
    if [ "$PUBLIC_IP" != "unknown" ]; then
        echo "🌐 Application should be accessible at: http://$PUBLIC_IP:$HOST_PORT"
        echo "🌐 Try: curl http://$PUBLIC_IP:$HOST_PORT/health"
    fi
    
else
    echo "❌ Container failed to start"
    echo "📋 Container logs:"
    docker logs $CONTAINER_NAME
    exit 1
fi

# === CLEANUP OLD IMAGES ===
echo -e "\n🧹 Cleaning up old images..."
docker image prune -f
echo "✅ Cleanup complete"

# === SUMMARY ===
echo -e "\n🎉 Deployment Summary"
echo "===================="
echo "Container Name: $CONTAINER_NAME"
echo "Image: $IMAGE_TAG"
echo "Port Mapping: $HOST_PORT:$CONTAINER_PORT"
echo "Data Directory: $DATA_DIR"
echo "Public IP: $PUBLIC_IP"
echo ""
echo "📋 Useful Commands:"
echo "  View logs: docker logs $CONTAINER_NAME -f"
echo "  Stop app:  docker stop $CONTAINER_NAME"
echo "  Start app: docker start $CONTAINER_NAME"
echo "  Shell:     docker exec -it $CONTAINER_NAME bash"
echo ""
echo "🔧 Oracle Cloud Network Configuration:"
echo "  1. Go to Oracle Cloud Console > Networking > Virtual Cloud Networks"
echo "  2. Select your VCN > Security Lists > Default Security List"
echo "  3. Add Ingress Rule: Source 0.0.0.0/0, Port 8080, Protocol TCP"
echo "  4. Verify your subnet has route to Internet Gateway"
echo ""
echo "✅ Deployment complete! No more ngrok needed! 🎯"