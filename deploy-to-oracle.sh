#!/bin/bash

# F1 Race Plots - Oracle Cloud Auto Deploy Script
# Run this locally to deploy your main branch to Oracle VM

set -e

# Configuration
ORACLE_HOST="141.147.90.24"
ORACLE_USER="ubuntu"
SSH_KEY="~/.ssh/ssh-key-2025-07-01.key"
DEPLOY_DIR="/opt/f1-app"
LOCAL_PROJECT_DIR="/Users/will/Programming/Python/f1-race-plots"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 F1 Race Plots - Oracle Cloud Deployment${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if we're in the right directory
if [[ ! -f "app.py" ]]; then
    echo -e "${RED}❌ Error: Run this script from your F1 project directory${NC}"
    exit 1
fi

# Check if we have uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}⚠️  Warning: You have uncommitted changes - continuing anyway${NC}"
fi

# Get current branch and commit
CURRENT_BRANCH=$(git branch --show-current)
CURRENT_COMMIT=$(git rev-parse --short HEAD)

echo -e "${BLUE}📋 Deployment Info:${NC}"
echo -e "  Branch: ${GREEN}$CURRENT_BRANCH${NC}"
echo -e "  Commit: ${GREEN}$CURRENT_COMMIT${NC}"
echo -e "  Target: ${GREEN}$ORACLE_USER@$ORACLE_HOST${NC}"
echo ""

# Confirm deployment
echo -e "${GREEN}✅ Proceeding with deployment to Oracle Cloud${NC}"

echo -e "${BLUE}🔄 Starting deployment...${NC}"

# Step 1: Test SSH connection
echo -e "${YELLOW}1/6 Testing SSH connection...${NC}"
if ! ssh -i $SSH_KEY -o ConnectTimeout=10 $ORACLE_USER@$ORACLE_HOST "echo 'SSH OK'" > /dev/null 2>&1; then
    echo -e "${RED}❌ SSH connection failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ SSH connection successful${NC}"

# Step 2: Sync files to Oracle VM
echo -e "${YELLOW}2/6 Syncing project files...${NC}"
rsync -avz --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'fastf1_cache' \
    --exclude 'static/plots' \
    --exclude 'logs' \
    --exclude 'f1_cache.sqlite' \
    --exclude '.DS_Store' \
    --exclude 'node_modules' \
    -e "ssh -i $SSH_KEY" \
    ./ $ORACLE_USER@$ORACLE_HOST:$DEPLOY_DIR/

# Copy the optimized docker-compose file
rsync -avz -e "ssh -i $SSH_KEY" ./docker-compose.production.yml $ORACLE_USER@$ORACLE_HOST:$DEPLOY_DIR/
rsync -avz -e "ssh -i $SSH_KEY" ./fix-ollama.sh $ORACLE_USER@$ORACLE_HOST:$DEPLOY_DIR/
echo -e "${GREEN}✅ Files synced${NC}"

# Step 3: Build new Docker image
echo -e "${YELLOW}3/6 Building Docker image...${NC}"
ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "cd $DEPLOY_DIR && docker builder prune -f && docker build --no-cache -t f1-flask-app:latest ."
echo -e "${GREEN}✅ Docker image built${NC}"

# Step 4: Fix Ollama deployment
echo -e "${YELLOW}4/6 Fixing Ollama configuration...${NC}"
ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "cd $DEPLOY_DIR && chmod +x fix-ollama.sh && ./fix-ollama.sh"
echo -e "${GREEN}✅ Ollama fixed and running${NC}"

# Step 5: Health check
echo -e "${YELLOW}5/5 Running health check...${NC}"
sleep 10  # Give services time to start

# Check Flask app
if ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "timeout 10 curl -sf http://localhost:8080/ > /dev/null"; then
    echo -e "${GREEN}✅ Flask app is running${NC}"
else
    echo -e "${RED}❌ Flask app health check failed${NC}"
fi

# Check Ollama
if ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "timeout 10 curl -sf http://localhost:11434/api/tags > /dev/null"; then
    echo -e "${GREEN}✅ Ollama is running${NC}"
else
    echo -e "${RED}❌ Ollama health check failed${NC}"
fi

# Check Nginx
if ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "timeout 10 curl -sf http://localhost:80/health > /dev/null"; then
    echo -e "${GREEN}✅ Nginx is running${NC}"
else
    echo -e "${YELLOW}⚠️  Nginx health check failed (may be normal)${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo ""
echo -e "${BLUE}🌍 Your app is available at:${NC}"
echo -e "  • ${GREEN}http://$ORACLE_HOST${NC} (Nginx proxy)"
echo -e "  • ${GREEN}http://$ORACLE_HOST:8080${NC} (Direct Flask)"
echo ""
echo -e "${BLUE}🚀 Available AI Models:${NC}"
echo -e "  • ${GREEN}f1expert${NC} (F1 specialized model) - Optimized for telemetry analysis"
echo ""
echo -e "${BLUE}⚡ Performance Optimized:${NC}"
echo -e "  • ${GREEN}26GB RAM${NC} allocated to AI inference"
echo -e "  • ${GREEN}3 CPU cores${NC} dedicated to Ollama"
echo -e "  • ${GREEN}Multi-threading${NC} enabled for faster processing"
echo ""
echo -e "${BLUE}📊 Management commands:${NC}"
echo -e "  • Fix Ollama: ${YELLOW}ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST 'cd $DEPLOY_DIR && ./fix-ollama.sh'${NC}"
echo -e "  • View logs: ${YELLOW}ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST 'cd $DEPLOY_DIR && docker-compose -f docker-compose.production.yml logs -f'${NC}"
echo -e "  • Restart: ${YELLOW}ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST 'cd $DEPLOY_DIR && docker-compose -f docker-compose.production.yml restart'${NC}"
echo ""
echo -e "${GREEN}Happy racing! 🏎️💨${NC}"