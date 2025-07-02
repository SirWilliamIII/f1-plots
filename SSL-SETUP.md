# 🔐 SSL Setup Guide for F1 Race Plots

This guide helps you set up SSL certificates and HTTPS for your F1 Race Plots application with Cloudflare DNS.

## 🚀 Quick Start

### Option 1: Self-Signed Certificate (Testing)
```bash
./generate-ssl-cert.sh localhost
docker-compose -f docker-compose.ssl.yml up -d
```
Access: `https://localhost` (accept security warning)

### Option 2: Custom Domain with Cloudflare (Recommended)
```bash
./setup-ssl-cloudflare.sh yourdomain.com 3
./deploy-ssl-to-oracle.sh yourdomain.com
```

## 📋 SSL Options Explained

### 1. Self-Signed Certificate
- **Use case**: Local development, testing
- **Setup time**: 30 seconds
- **Security**: Browser warnings, but encrypted
- **Command**: `./generate-ssl-cert.sh localhost`

### 2. Let's Encrypt
- **Use case**: Public domains, automatic renewal
- **Setup time**: 5 minutes
- **Security**: Trusted by all browsers
- **Requirements**: Domain must point to your server
- **Command**: `./setup-ssl-cloudflare.sh yourdomain.com 2`

### 3. Cloudflare Origin Certificate (Recommended)
- **Use case**: Production with Cloudflare
- **Setup time**: 2 minutes
- **Security**: End-to-end encryption
- **Benefits**: DDoS protection, CDN, analytics
- **Command**: `./setup-ssl-cloudflare.sh yourdomain.com 3`

## 🌐 Cloudflare Setup Steps

### 1. DNS Configuration
Point your domain to your Oracle VM:
```
A Record: yourdomain.com → 141.147.90.24 (Proxied ✅)
A Record: www.yourdomain.com → 141.147.90.24 (Proxied ✅)
```

### 2. SSL/TLS Settings
In Cloudflare Dashboard → SSL/TLS:
- **Encryption Mode**: Full (Strict)
- **Always Use HTTPS**: On
- **Auto HTTPS Rewrites**: On
- **Minimum TLS Version**: 1.2

### 3. Origin Certificate
1. Go to SSL/TLS → Origin Server
2. Click "Create Certificate"
3. Hostnames: `yourdomain.com, *.yourdomain.com`
4. Key type: RSA, Validity: 15 years
5. Save certificate as `ssl/cert.pem`
6. Save private key as `ssl/key.pem`

### 4. Security Features (Optional)
- **HSTS**: Enable for maximum security
- **Security Level**: Medium or High
- **Bot Fight Mode**: On
- **Rate Limiting**: Configure as needed

## 🔧 Deployment Commands

### Deploy with SSL
```bash
# For custom domain
./deploy-ssl-to-oracle.sh yourdomain.com

# For IP-only (self-signed)
./deploy-ssl-to-oracle.sh
```

### Manual SSL Setup
```bash
# Generate certificates
./setup-ssl-cloudflare.sh yourdomain.com 3

# Deploy services
docker-compose -f docker-compose.ssl.yml up -d
```

### Check SSL Status
```bash
# Test HTTPS connection
curl -I https://yourdomain.com

# Check certificate details
openssl x509 -in ssl/cert.pem -text -noout | head -20

# View nginx logs
docker-compose -f docker-compose.ssl.yml logs nginx
```

## 🏎️ Performance Features

### Nginx Optimizations
- **Gzip compression**: Reduces bandwidth by 70%
- **Browser caching**: Static files cached for 1 year
- **Rate limiting**: Prevents abuse (30 req/s web, 10 req/s API)
- **HTTP/2**: Faster loading with multiplexing

### Cloudflare Benefits
- **Global CDN**: Faster loading worldwide
- **DDoS protection**: Automatic threat mitigation
- **Analytics**: Traffic insights and performance metrics
- **Edge caching**: Reduced server load

### Security Headers
- **XSS Protection**: Prevents cross-site scripting
- **Content Security Policy**: Blocks malicious content
- **HSTS**: Forces HTTPS connections
- **Real IP Detection**: Shows actual visitor IPs

## 🚨 Troubleshooting

### Common Issues

**SSL Certificate Errors**
```bash
# Check certificate validity
openssl x509 -in ssl/cert.pem -text -noout

# Verify private key matches
openssl rsa -in ssl/key.pem -check
```

**Nginx Won't Start**
```bash
# Check configuration
docker run --rm -v $(pwd)/nginx-cloudflare-ssl.conf:/etc/nginx/nginx.conf:ro nginx:alpine nginx -t

# View nginx logs
docker-compose -f docker-compose.ssl.yml logs nginx
```

**Cloudflare Proxy Issues**
- Ensure DNS records are "Proxied" (orange cloud)
- Check SSL/TLS mode is "Full (Strict)"
- Verify origin certificate is valid

**Let's Encrypt Failures**
```bash
# Check domain points to server
dig yourdomain.com

# Verify firewall allows port 80
sudo ufw status

# Manual certificate generation
docker-compose -f docker-compose.ssl.yml --profile ssl-setup run --rm certbot certonly --webroot --webroot-path=/var/www/certbot --email admin@yourdomain.com --agree-tos --no-eff-email -d yourdomain.com
```

## 📊 Monitoring

### Health Checks
```bash
# Service status
docker-compose -f docker-compose.ssl.yml ps

# SSL certificate expiry
echo | openssl s_client -servername yourdomain.com -connect yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates

# Performance test
curl -w "@curl-format.txt" -o /dev/null -s https://yourdomain.com
```

### Log Monitoring
```bash
# All services
docker-compose -f docker-compose.ssl.yml logs -f

# Nginx access logs
docker-compose -f docker-compose.ssl.yml exec nginx tail -f /var/log/nginx/access.log

# SSL handshake errors
docker-compose -f docker-compose.ssl.yml exec nginx tail -f /var/log/nginx/error.log | grep SSL
```

## 🏁 Production Checklist

- [ ] Domain points to server IP
- [ ] SSL certificate installed and valid
- [ ] HTTPS redirect working
- [ ] Cloudflare proxy enabled
- [ ] Security headers configured
- [ ] Rate limiting active
- [ ] Health monitoring setup
- [ ] Log rotation configured
- [ ] Backup strategy implemented
- [ ] Certificate renewal automated

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review service logs: `docker-compose -f docker-compose.ssl.yml logs`
3. Test individual components: `curl -I https://yourdomain.com`
4. Verify Cloudflare settings match the guide

Your F1 telemetry analysis platform is now secure and production-ready! 🏎️💨🔐