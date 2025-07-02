#!/bin/bash

# Generate SSL Certificate Script
# For quick local SSL certificate generation

set -e

DOMAIN=${1:-"localhost"}
EMAIL=${2:-"admin@$DOMAIN"}

echo "🔐 Generating SSL certificate for: $DOMAIN"

# Create ssl directory if it doesn't exist
mkdir -p ssl

# Generate private key
echo "🔑 Generating private key..."
openssl genrsa -out ssl/key.pem 2048

# Generate certificate signing request
echo "📝 Creating certificate signing request..."
openssl req -new -key ssl/key.pem -out ssl/cert.csr -subj "/C=US/ST=State/L=City/O=F1RacePlots/OU=IT/CN=$DOMAIN/emailAddress=$EMAIL"

# Generate self-signed certificate
echo "📜 Generating self-signed certificate..."
openssl x509 -req -in ssl/cert.csr -signkey ssl/key.pem -out ssl/cert.pem -days 365 -extensions v3_req -extfile <(
    echo '[v3_req]'
    echo 'basicConstraints = CA:FALSE'
    echo 'keyUsage = nonRepudiation, digitalSignature, keyEncipherment'
    echo 'subjectAltName = @alt_names'
    echo '[alt_names]'
    echo "DNS.1 = $DOMAIN"
    echo "DNS.2 = www.$DOMAIN"
    echo "DNS.3 = localhost"
    echo "IP.1 = 127.0.0.1"
    echo "IP.2 = 141.147.90.24"
)

# Clean up
rm ssl/cert.csr

# Set proper permissions
chmod 600 ssl/key.pem
chmod 644 ssl/cert.pem

echo "✅ SSL certificate generated successfully!"
echo "📂 Files created:"
echo "   • ssl/cert.pem (Certificate)"
echo "   • ssl/key.pem (Private Key)"
echo ""
echo "⚠️  This is a self-signed certificate for testing only."
echo "🌐 For production, use Let's Encrypt or Cloudflare Origin Certificate."