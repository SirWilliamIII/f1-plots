#!/bin/bash

if ! [ -x "$(command -v docker-compose)" ]; then
  echo 'Error: docker-compose is not installed.' >&2
  exit 1
fi

# Default domain and email
domains=(your-domain.com www.your-domain.com)
email="your-email@example.com" # Adding a valid email is recommended for renewal and security notices
staging=0 # Set to 1 if you're testing your setup to avoid hitting request limits

# Create required directories
mkdir -p ./certbot/conf ./certbot/data

# Ask for domain and email if not provided
read -p "Enter your domain (default: ${domains[0]}): " input_domain
if [ ! -z "$input_domain" ]; then
  domains=("$input_domain" "www.$input_domain")
fi

read -p "Enter your email (default: $email): " input_email
if [ ! -z "$input_email" ]; then
  email="$input_email"
fi

read -p "Use staging environment? (0 for production, 1 for staging) (default: $staging): " input_staging
if [ ! -z "$input_staging" ]; then
  staging="$input_staging"
fi

echo "### Creating dummy certificate for ${domains[0]} ..."
path="/etc/letsencrypt/live/${domains[0]}"
mkdir -p ./certbot/conf/live/${domains[0]}
docker-compose -f docker-compose.ssl.yml run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:4096 -days 1\
    -keyout '$path/privkey.pem' \
    -out '$path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

echo "### Starting nginx ..."
docker-compose -f docker-compose.ssl.yml up --force-recreate -d nginx

echo "### Deleting dummy certificate for ${domains[0]} ..."
docker-compose -f docker-compose.ssl.yml run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/${domains[0]} && \
  rm -Rf /etc/letsencrypt/archive/${domains[0]} && \
  rm -Rf /etc/letsencrypt/renewal/${domains[0]}.conf" certbot

echo "### Requesting Let's Encrypt certificate for ${domains[@]} ..."
domain_args=""
for domain in "${domains[@]}"; do
  domain_args="$domain_args -d $domain"
done

# Select appropriate email arg
case "$email" in
  "") email_arg="--register-unsafely-without-email" ;;
  *) email_arg="--email $email" ;;
esac

# Enable staging mode if needed
if [ $staging != "0" ]; then staging_arg="--staging"; fi

docker-compose -f docker-compose.ssl.yml run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    $email_arg \
    $domain_args \
    --rsa-key-size 4096 \
    --agree-tos \
    --force-renewal" certbot

echo "### Reloading nginx ..."
docker-compose -f docker-compose.ssl.yml exec nginx nginx -s reload

# Update nginx.conf with the correct domain
sed -i.bak "s/your-domain.com/${domains[0]}/g" ./nginx/nginx.conf

echo "### Setup completed! Your site should now be accessible via HTTPS."
echo "### Don't forget to update your Cloudflare DNS settings with A records pointing to your server IP."
