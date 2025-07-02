#!/bin/bash

# SSL Setup Script for F1 Race Plots with Cloudflare
# This script helps you set up SSL certificates for your domain

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔐 F1 Race Plots - SSL Setup with Cloudflare${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# Check if domain is provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ Usage: $0 <your-domain.com>${NC}"
    echo -e "${YELLOW}Example: $0 f1telemetry.com${NC}"
    exit 1
fi

DOMAIN=$1
EMAIL=${2:-"admin@$DOMAIN"}

echo -e "${BLUE}🌐 Setting up SSL for domain: ${GREEN}$DOMAIN${NC}"
echo -e "${BLUE}📧 Using email: ${GREEN}$EMAIL${NC}"
echo ""

# Create SSL directory structure
echo -e "${YELLOW}📁 Creating SSL directory structure...${NC}"
mkdir -p ssl
mkdir -p ssl/live
mkdir -p ssl/archive

# Function to create self-signed certificates for testing
create_self_signed_cert() {
    echo -e "${YELLOW}🔑 Creating self-signed certificate for testing...${NC}"
    
    # Create private key
    openssl genrsa -out ssl/key.pem 2048
    
    # Create certificate signing request
    openssl req -new -key ssl/key.pem -out ssl/cert.csr -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=$DOMAIN/emailAddress=$EMAIL"
    
    # Create self-signed certificate
    openssl x509 -req -in ssl/cert.csr -signkey ssl/key.pem -out ssl/cert.pem -days 365 -extensions v3_req -extfile <(
        echo '[v3_req]'
        echo 'basicConstraints = CA:FALSE'
        echo 'keyUsage = nonRepudiation, digitalSignature, keyEncipherment'
        echo 'subjectAltName = @alt_names'
        echo '[alt_names]'
        echo "DNS.1 = $DOMAIN"
        echo "DNS.2 = www.$DOMAIN"
    )
    
    # Clean up CSR
    rm ssl/cert.csr
    
    echo -e "${GREEN}✅ Self-signed certificate created${NC}"
    echo -e "${YELLOW}⚠️  This is for testing only. Use Let's Encrypt for production.${NC}"
}

# Function to set up Let's Encrypt with Cloudflare
setup_letsencrypt() {
    echo -e "${YELLOW}🔐 Setting up Let's Encrypt certificate...${NC}"
    
    # Update Nginx config with the domain
    sed -i.bak "s/server_name _;/server_name $DOMAIN www.$DOMAIN;/" nginx-cloudflare-ssl.conf
    
    echo -e "${BLUE}📋 Steps to complete Let's Encrypt setup:${NC}"
    echo ""
    echo -e "${YELLOW}1. First, point your domain to this server:${NC}"
    echo -e "   A Record: $DOMAIN → $(curl -s ifconfig.me)"
    echo -e "   A Record: www.$DOMAIN → $(curl -s ifconfig.me)"
    echo ""
    echo -e "${YELLOW}2. Wait for DNS propagation (5-10 minutes)${NC}"
    echo ""
    echo -e "${YELLOW}3. Then run this command to get SSL certificate:${NC}"
    echo -e "   ${GREEN}docker-compose -f docker-compose.ssl.yml --profile ssl-setup run --rm certbot certonly --webroot --webroot-path=/var/www/certbot --email $EMAIL --agree-tos --no-eff-email -d $DOMAIN -d www.$DOMAIN${NC}"
    echo ""
    echo -e "${YELLOW}4. Copy certificates to the right location:${NC}"
    echo -e "   ${GREEN}cp ssl/live/$DOMAIN/fullchain.pem ssl/cert.pem${NC}"
    echo -e "   ${GREEN}cp ssl/live/$DOMAIN/privkey.pem ssl/key.pem${NC}"
    echo ""
    echo -e "${YELLOW}5. Restart services:${NC}"
    echo -e "   ${GREEN}docker-compose -f docker-compose.ssl.yml restart nginx${NC}"
}

# Function to set up Cloudflare Origin Certificate
setup_cloudflare_origin() {
    echo -e "${YELLOW}☁️ Setting up Cloudflare Origin Certificate...${NC}"
    echo ""
    echo -e "${BLUE}📋 Steps for Cloudflare Origin Certificate:${NC}"
    echo ""
    echo -e "${YELLOW}1. Go to Cloudflare Dashboard → SSL/TLS → Origin Server${NC}"
    echo -e "${YELLOW}2. Click 'Create Certificate'${NC}"
    echo -e "${YELLOW}3. Use these hostnames: $DOMAIN, *.$DOMAIN${NC}"
    echo -e "${YELLOW}4. Choose 'RSA' and '15 years'${NC}"
    echo -e "${YELLOW}5. Copy the certificate and private key${NC}"
    echo ""
    echo -e "${YELLOW}6. Save the certificate as:${NC}"
    echo -e "   ${GREEN}ssl/cert.pem${NC}"
    echo ""
    echo -e "${YELLOW}7. Save the private key as:${NC}"
    echo -e "   ${GREEN}ssl/key.pem${NC}"
    echo ""
    echo -e "${YELLOW}8. Update Cloudflare DNS settings:${NC}"
    echo -e "   A Record: $DOMAIN → $(curl -s ifconfig.me) (Proxied: ✅)"
    echo -e "   A Record: www.$DOMAIN → $(curl -s ifconfig.me) (Proxied: ✅)"
    echo ""
    echo -e "${YELLOW}9. Set SSL/TLS encryption mode to 'Full (Strict)'${NC}"
    echo ""
    echo -e "${GREEN}📖 This provides end-to-end encryption with Cloudflare protection${NC}"
}

# Menu for SSL setup options
echo -e "${BLUE}🔧 Choose SSL setup method:${NC}"
echo ""
echo -e "${YELLOW}1) Self-signed certificate (for testing)${NC}"
echo -e "${YELLOW}2) Let's Encrypt (free, auto-renewal)${NC}"
echo -e "${YELLOW}3) Cloudflare Origin Certificate (recommended)${NC}"
echo ""
read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        create_self_signed_cert
        ;;
    2)
        setup_letsencrypt
        ;;
    3)
        setup_cloudflare_origin
        ;;
    *)
        echo -e "${RED}❌ Invalid choice${NC}"
        exit 1
        ;;
esac

# Update Nginx config with domain
echo -e "${YELLOW}🔧 Updating Nginx configuration...${NC}"
sed -i.bak "s/server_name _;/server_name $DOMAIN www.$DOMAIN;/" nginx-cloudflare-ssl.conf

# Create deployment script
echo -e "${YELLOW}📝 Creating SSL deployment script...${NC}"
cat > deploy-ssl.sh << EOF
#!/bin/bash

# Deploy F1 Race Plots with SSL
# Domain: $DOMAIN

echo "🚀 Deploying F1 Race Plots with SSL..."

# Stop existing services
docker-compose -f docker-compose.ssl.yml down

# Pull latest images
docker-compose -f docker-compose.ssl.yml pull

# Start services
docker-compose -f docker-compose.ssl.yml up -d

# Wait for services
sleep 30

# Check status
echo "📊 Service Status:"
docker-compose -f docker-compose.ssl.yml ps

echo ""
echo "🌐 Your F1 app is available at:"
echo "• https://$DOMAIN"
echo "• https://www.$DOMAIN"
echo ""
echo "🔧 Management commands:"
echo "• View logs: docker-compose -f docker-compose.ssl.yml logs -f"
echo "• Restart: docker-compose -f docker-compose.ssl.yml restart"
echo "• Stop: docker-compose -f docker-compose.ssl.yml down"
EOF

chmod +x deploy-ssl.sh

echo ""
echo -e "${GREEN}🎉 SSL setup configuration complete!${NC}"
echo ""
echo -e "${BLUE}📂 Created files:${NC}"
echo -e "  • ${GREEN}nginx-cloudflare-ssl.conf${NC} - Nginx configuration"
echo -e "  • ${GREEN}docker-compose.ssl.yml${NC} - Docker Compose with SSL"
echo -e "  • ${GREEN}deploy-ssl.sh${NC} - Deployment script"
echo -e "  • ${GREEN}ssl/${NC} - SSL certificates directory"
echo ""
echo -e "${BLUE}🚀 Next steps:${NC}"
echo -e "1. Complete the SSL certificate setup (see instructions above)"
echo -e "2. Run: ${GREEN}./deploy-ssl.sh${NC}"
echo -e "3. Point your domain to: ${GREEN}$(curl -s ifconfig.me)${NC}"
echo ""
echo -e "${BLUE}🔧 Cloudflare Settings:${NC}"
echo -e "• SSL/TLS Mode: ${GREEN}Full (Strict)${NC}"
echo -e "• Always Use HTTPS: ${GREEN}On${NC}"
echo -e "• Auto HTTPS Rewrites: ${GREEN}On${NC}"
echo -e "• Proxy Status: ${GREEN}Proxied (Orange Cloud)${NC}"
echo ""
echo -e "${GREEN}Your F1 telemetry app will be secure and fast with Cloudflare! 🏎️💨${NC}"