#!/bin/bash

# Fix Ollama Connection Issues on 48GB VM
# Run this script on your Oracle VM to diagnose and fix Ollama connectivity

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 F1 Ollama Connection Fix${NC}"
echo -e "${BLUE}=============================${NC}"
echo ""

# Function to check service health
check_service() {
    local service=$1
    local url=$2
    echo -n "Checking $service... "
    if curl -sf "$url" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Running${NC}"
        return 0
    else
        echo -e "${RED}❌ Down${NC}"
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local service=$1
    local url=$2
    local max_attempts=$3
    
    echo -e "${YELLOW}⏳ Waiting for $service to be ready...${NC}"
    for i in $(seq 1 $max_attempts); do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $service is ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 5
    done
    echo -e "${RED}❌ $service failed to start after $((max_attempts * 5)) seconds${NC}"
    return 1
}

echo -e "${BLUE}📊 System Resources:${NC}"
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
echo "Load: $(uptime | awk -F'load average:' '{print $2}')"
echo ""

echo -e "${BLUE}🔍 Current Docker Status:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

echo -e "${BLUE}📋 Step 1: Stopping all services${NC}"
cd /opt/f1-app
docker-compose -f docker-compose.production.yml down --remove-orphans || true

echo -e "${BLUE}🧹 Step 2: Cleaning up Docker resources${NC}"
docker system prune -f
docker volume prune -f

echo -e "${BLUE}📦 Step 3: Pulling latest images${NC}"
docker pull ollama/ollama:latest

echo -e "${BLUE}🚀 Step 4: Starting Ollama first${NC}"
docker-compose -f docker-compose.production.yml up -d ollama

# Wait for Ollama to be healthy
if wait_for_service "Ollama" "http://localhost:11434/api/tags" 60; then
    echo -e "${GREEN}✅ Ollama is running${NC}"
else
    echo -e "${RED}❌ Ollama failed to start. Checking logs...${NC}"
    docker-compose -f docker-compose.production.yml logs ollama
    exit 1
fi

echo -e "${BLUE}🤖 Step 5: Setting up F1 Expert model${NC}"
# Check if f1expert model exists
if docker exec $(docker-compose -f docker-compose.production.yml ps -q ollama) ollama list | grep -q "f1expert"; then
    echo -e "${GREEN}✅ f1expert model already exists${NC}"
else
    echo -e "${YELLOW}⏳ Creating f1expert model...${NC}"
    docker exec $(docker-compose -f docker-compose.production.yml ps -q ollama) ollama create f1expert -f /tmp/f1expert.modelfile
    echo -e "${GREEN}✅ f1expert model created${NC}"
fi

echo -e "${BLUE}🌐 Step 6: Starting Flask app${NC}"
docker-compose -f docker-compose.production.yml up -d flask-app

# Wait for Flask to be healthy
if wait_for_service "Flask" "http://localhost:8080/" 30; then
    echo -e "${GREEN}✅ Flask is running${NC}"
else
    echo -e "${RED}❌ Flask failed to start. Checking logs...${NC}"
    docker-compose -f docker-compose.production.yml logs flask-app
    exit 1
fi

echo -e "${BLUE}🏥 Step 7: Starting health monitor${NC}"
docker-compose -f docker-compose.production.yml up -d health-monitor

echo -e "${BLUE}🔬 Step 8: Testing Ollama connection from Flask${NC}"
# Test the connection that Flask would make
OLLAMA_TEST=$(docker exec $(docker-compose -f docker-compose.production.yml ps -q flask-app) curl -sf http://ollama:11434/api/tags 2>/dev/null || echo "FAILED")

if [ "$OLLAMA_TEST" = "FAILED" ]; then
    echo -e "${RED}❌ Flask cannot reach Ollama${NC}"
    echo "Debugging network connectivity..."
    docker exec $(docker-compose -f docker-compose.production.yml ps -q flask-app) nslookup ollama || true
    docker exec $(docker-compose -f docker-compose.production.yml ps -q flask-app) ping -c 3 ollama || true
else
    echo -e "${GREEN}✅ Flask can reach Ollama${NC}"
fi

echo -e "${BLUE}🧪 Step 9: Testing F1 Expert model${NC}"
MODEL_TEST=$(docker exec $(docker-compose -f docker-compose.production.yml ps -q ollama) ollama run f1expert "Test" 2>/dev/null || echo "FAILED")

if [ "$MODEL_TEST" = "FAILED" ]; then
    echo -e "${RED}❌ F1 Expert model test failed${NC}"
    echo "Available models:"
    docker exec $(docker-compose -f docker-compose.production.yml ps -q ollama) ollama list
else
    echo -e "${GREEN}✅ F1 Expert model is working${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Ollama Fix Complete!${NC}"
echo ""
echo -e "${BLUE}📊 Final Status:${NC}"
check_service "Flask App" "http://localhost:8080/"
check_service "Ollama API" "http://localhost:11434/api/tags"
echo ""

echo -e "${BLUE}🛠️ Troubleshooting Commands:${NC}"
echo -e "  View logs: ${YELLOW}docker-compose -f docker-compose.production.yml logs -f${NC}"
echo -e "  Restart Ollama: ${YELLOW}docker-compose -f docker-compose.production.yml restart ollama${NC}"
echo -e "  Check models: ${YELLOW}docker exec \$(docker-compose -f docker-compose.production.yml ps -q ollama) ollama list${NC}"
echo -e "  Test connection: ${YELLOW}curl http://localhost:11434/api/tags${NC}"
echo ""

echo -e "${BLUE}📈 Performance Tips:${NC}"
echo -e "  • Monitor with: ${YELLOW}docker stats${NC}"
echo -e "  • Check memory: ${YELLOW}free -h${NC}"
echo -e "  • View processes: ${YELLOW}htop${NC}"
echo ""

echo -e "${GREEN}Your F1 app should now be working with Ollama! 🏎️${NC}"