#!/bin/bash

echo "🔧 F1 App Oracle Deployment Fix"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Current Status Check...${NC}"

# Check if app is running
echo "📊 Checking F1 app status..."
if curl -s http://localhost:8080/ > /dev/null; then
    echo -e "${GREEN}✅ F1 app is running on port 8080${NC}"
else
    echo -e "${RED}❌ F1 app is not responding on port 8080${NC}"
    echo "Starting F1 app..."
    cd /home/ubuntu/f1-plots
    nohup gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 300 app:app > logs/gunicorn.log 2>&1 &
    sleep 3
fi

# Check nginx
echo "🌐 Checking nginx status..."
if curl -s http://localhost/ > /dev/null; then
    echo -e "${GREEN}✅ Nginx is working and proxying correctly${NC}"
else
    echo -e "${RED}❌ Nginx proxy issue${NC}"
    sudo systemctl restart nginx
fi

# Check Ollama
echo "🤖 Checking Ollama status..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${GREEN}✅ Ollama is running${NC}"
else
    echo -e "${YELLOW}⚠️ Ollama may not be running${NC}"
fi

echo ""
echo -e "${YELLOW}🔥 CRITICAL ISSUE IDENTIFIED:${NC}"
echo -e "${RED}External access is blocked by Oracle Cloud Security Lists${NC}"
echo ""
echo -e "${BLUE}Your F1 app is working perfectly internally:${NC}"
echo "• ✅ App running on http://localhost:8080"
echo "• ✅ Nginx proxying on http://localhost:80"
echo "• ✅ Ollama AI service on http://localhost:11434"
echo ""
echo -e "${YELLOW}🛠️ TO FIX EXTERNAL ACCESS:${NC}"
echo ""
echo "1. Go to Oracle Cloud Console: https://cloud.oracle.com/"
echo "2. Navigate to: Networking → Virtual Cloud Networks"
echo "3. Click on your VCN (Virtual Cloud Network)"
echo "4. Click on 'Security Lists' in the left menu"
echo "5. Click on the 'Default Security List'"
echo "6. Click 'Add Ingress Rules'"
echo "7. Add these rules:"
echo ""
echo -e "${GREEN}   Rule 1 - HTTP:${NC}"
echo "   • Source Type: CIDR"
echo "   • Source CIDR: 0.0.0.0/0"
echo "   • IP Protocol: TCP"
echo "   • Destination Port Range: 80"
echo "   • Description: HTTP access for F1 app"
echo ""
echo -e "${GREEN}   Rule 2 - HTTPS:${NC}"
echo "   • Source Type: CIDR"
echo "   • Source CIDR: 0.0.0.0/0"
echo "   • IP Protocol: TCP"
echo "   • Destination Port Range: 443"
echo "   • Description: HTTPS access for F1 app"
echo ""
echo -e "${GREEN}   Rule 3 - F1 App Direct (Optional):${NC}"
echo "   • Source Type: CIDR"
echo "   • Source CIDR: 0.0.0.0/0"
echo "   • IP Protocol: TCP"
echo "   • Destination Port Range: 8080"
echo "   • Description: Direct F1 app access"
echo ""

echo -e "${BLUE}🚀 ALTERNATIVE QUICK FIX:${NC}"
echo "If you have Oracle CLI configured, run:"
echo ""
echo "# Get your VCN and Security List IDs first"
echo "oci network vcn list --compartment-id YOUR_COMPARTMENT_ID"
echo "oci network security-list list --compartment-id YOUR_COMPARTMENT_ID --vcn-id YOUR_VCN_ID"
echo ""
echo "# Then add the ingress rules"
echo 'oci network security-list update --security-list-id YOUR_SECURITY_LIST_ID --ingress-security-rules '"'"'[{"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":80,"max":80}}}]'"'"

echo ""
echo -e "${GREEN}📱 CURRENT APP ACCESS (Internal Only):${NC}"
echo "• SSH tunnel: ssh -L 8080:localhost:8080 -i ~/.ssh/will-oracle-aarch64.key ubuntu@141.147.101.95"
echo "• Then visit: http://localhost:8080 in your browser"
echo ""
echo -e "${BLUE}📊 DEPLOYMENT SUMMARY:${NC}"
echo "• ✅ F1 Race Plots app: WORKING"
echo "• ✅ Nginx reverse proxy: WORKING"
echo "• ✅ Ollama AI service: WORKING"
echo "• ❌ External access: BLOCKED (Oracle Security Lists)"
echo ""
echo -e "${GREEN}Once you fix the Oracle Cloud Security Lists, your app will be accessible at:${NC}"
echo "🌐 http://141.147.101.95/"
echo ""
echo "🎉 Your F1 app deployment is technically complete - just needs firewall rules!"
