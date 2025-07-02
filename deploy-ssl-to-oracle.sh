#!/bin/bash

# F1 Race Plots - SSL-Enabled Oracle Cloud Deployment Script
# Run this locally to deploy with SSL support to Oracle VM

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

echo -e "${BLUE}🔐 F1 Race Plots - SSL-Enabled Oracle Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if we're in the right directory
if [[ ! -f "app.py" ]]; then
    echo -e "${RED}❌ Error: Run this script from your F1 project directory${NC}"
    exit 1
fi

# Check if domain is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}⚠️  No domain provided. Using IP-based deployment.${NC}"
    echo -e "${YELLOW}   For custom domain: $0 yourdomain.com${NC}"
    DOMAIN=""
else
    DOMAIN=$1
    echo -e "${GREEN}🌐 Setting up SSL for domain: $DOMAIN${NC}"
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
if [ -n "$DOMAIN" ]; then
    echo -e "  Domain: ${GREEN}$DOMAIN${NC}"
fi
echo ""

# Confirm deployment
echo -e "${GREEN}✅ Proceeding with SSL-enabled deployment to Oracle Cloud${NC}"

echo -e "${BLUE}🔄 Starting SSL deployment...${NC}"

# Step 1: Test SSH connection
echo -e "${YELLOW}1/7 Testing SSH connection...${NC}"
if ! ssh -i $SSH_KEY -o ConnectTimeout=10 $ORACLE_USER@$ORACLE_HOST "echo 'SSH OK'" > /dev/null 2>&1; then
    echo -e "${RED}❌ SSH connection failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ SSH connection successful${NC}"

# Step 2: Sync files to Oracle VM
echo -e "${YELLOW}2/7 Syncing project files with SSL configs...${NC}"
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

echo -e "${GREEN}✅ Files synced${NC}"

# Step 3: Set up SSL certificates on remote server
echo -e "${YELLOW}3/7 Setting up SSL certificates...${NC}"
if [ -n "$DOMAIN" ]; then
    ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "cd $DEPLOY_DIR && chmod +x setup-ssl-cloudflare.sh && ./setup-ssl-cloudflare.sh $DOMAIN 3"
else
    # Create self-signed certificate for IP-based access
    ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "cd $DEPLOY_DIR && chmod +x setup-ssl-cloudflare.sh && ./setup-ssl-cloudflare.sh localhost 1"
fi
echo -e "${GREEN}✅ SSL certificates configured${NC}"

# Step 4: Build Docker image
echo -e "${YELLOW}4/7 Building Docker image...${NC}"
ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "cd $DEPLOY_DIR && docker builder prune -f && docker build --no-cache -t f1-flask-app:latest ."
echo -e "${GREEN}✅ Docker image built${NC}"

# Step 5: Deploy with SSL
echo -e "${YELLOW}5/7 Deploying with SSL configuration...${NC}"
ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "cd $DEPLOY_DIR && docker-compose -f docker-compose.ssl.yml down --remove-orphans && docker-compose -f docker-compose.ssl.yml up -d"
echo -e "${GREEN}✅ SSL deployment complete${NC}"

# Step 6: Set up F1 models
echo -e "${YELLOW}6/7 Setting up F1 Expert model...${NC}"
ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "cd $DEPLOY_DIR && sleep 30 && docker exec \$(docker-compose -f docker-compose.ssl.yml ps -q ollama) ollama list | grep -q 'f1expert' || docker exec \$(docker-compose -f docker-compose.ssl.yml ps -q ollama) ollama create f1expert -f /tmp/f1expert.modelfile"
echo -e "${GREEN}✅ F1 Expert model ready${NC}"

# Step 7: Health check
echo -e "${YELLOW}7/7 Running SSL health check...${NC}"
sleep 20  # Give services more time to start with SSL

# Check HTTP redirect
echo -n "HTTP to HTTPS redirect: "
if ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "timeout 10 curl -sI http://localhost:80/ | grep -q '301\\|302'"; then
    echo -e "${GREEN}✅ Working${NC}"
else
    echo -e "${YELLOW}⚠️  Not configured${NC}"
fi

# Check HTTPS
echo -n "HTTPS access: "
if ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "timeout 10 curl -sfk https://localhost:443/ > /dev/null"; then
    echo -e "${GREEN}✅ Working${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
fi

# Check Flask app via Nginx
echo -n "Flask app via Nginx: "
if ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "timeout 10 curl -sf http://localhost:80/health > /dev/null"; then
    echo -e "${GREEN}✅ Working${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
fi

# Check Ollama via proxy
echo -n "Ollama API proxy: "
if ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST "timeout 10 curl -sf http://localhost:80/ollama_proxy/tags > /dev/null"; then
    echo -e "${GREEN}✅ Working${NC}"
else
    echo -e "${RED}❌ Failed${NC}"
fi

echo ""
echo -e "${GREEN}🎉 SSL Deployment completed!${NC}"
echo ""
echo -e "${BLUE}🌍 Your F1 app is available at:${NC}"
if [ -n "$DOMAIN" ]; then
    echo -e "  • ${GREEN}https://$DOMAIN${NC} (Primary - with SSL)"
    echo -e "  • ${GREEN}https://www.$DOMAIN${NC} (Alias - with SSL)"
    echo -e "  • ${GREEN}http://$DOMAIN${NC} (Redirects to HTTPS)"
    echo ""
    echo -e "${BLUE}🔐 SSL Certificate Status:${NC}"
    echo -e "  • ${GREEN}Cloudflare Origin Certificate${NC} (End-to-end encryption)"
    echo -e "  • ${GREEN}HTTP to HTTPS redirect${NC} (Automatic)"
    echo -e "  • ${GREEN}Security headers${NC} (XSS, CSRF protection)"
else
    echo -e "  • ${GREEN}https://$ORACLE_HOST${NC} (Self-signed certificate)"
    echo -e "  • ${GREEN}http://$ORACLE_HOST${NC} (Redirects to HTTPS)"
    echo ""
    echo -e "${YELLOW}⚠️  Using self-signed certificate. Set up custom domain for production.${NC}"
fi

echo ""
echo -e "${BLUE}🚀 Performance Features:${NC}"
echo -e "  • ${GREEN}Nginx reverse proxy${NC} with caching"
echo -e "  • ${GREEN}Gzip compression${NC} enabled"
echo -e "  • ${GREEN}Rate limiting${NC} (30 req/s web, 10 req/s API)"
echo -e "  • ${GREEN}Cloudflare integration${NC} (real IP detection)"
echo -e "  • ${GREEN}Security headers${NC} and protection"

echo ""
echo -e "${BLUE}🏎️ F1 AI Features:${NC}"
echo -e "  • ${GREEN}F1 Expert AI${NC} with specialized telemetry analysis"
echo -e "  • ${GREEN}5-channel telemetry plots${NC} (including gear changes)"
echo -e "  • ${GREEN}Real-time driver comparisons${NC}"
echo -e "  • ${GREEN}38GB RAM${NC} allocated for AI inference"

echo ""
echo -e "${BLUE}📊 Management commands:${NC}"
echo -e "  • View logs: ${YELLOW}ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST 'cd $DEPLOY_DIR && docker-compose -f docker-compose.ssl.yml logs -f'${NC}"
echo -e "  • Restart: ${YELLOW}ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST 'cd $DEPLOY_DIR && docker-compose -f docker-compose.ssl.yml restart'${NC}"
echo -e "  • SSL status: ${YELLOW}ssh -i $SSH_KEY $ORACLE_USER@$ORACLE_HOST 'cd $DEPLOY_DIR && openssl x509 -in ssl/cert.pem -text -noout | head -20'${NC}"

if [ -n "$DOMAIN" ]; then
    echo ""
    echo -e "${BLUE}☁️ Don't forget to configure Cloudflare:${NC}"
    echo -e "  1. Point A records to: ${GREEN}$ORACLE_HOST${NC}"
    echo -e "  2. Set SSL/TLS mode to: ${GREEN}Full (Strict)${NC}"
    echo -e "  3. Enable: ${GREEN}Always Use HTTPS${NC}"
    echo -e "  4. Enable: ${GREEN}Auto HTTPS Rewrites${NC}"
    echo -e "  5. Set proxy status: ${GREEN}Proxied (Orange Cloud)${NC}"
fi

echo ""
echo -e "${GREEN}Happy racing with secure F1 telemetry analysis! 🏎️💨🔐${NC}"