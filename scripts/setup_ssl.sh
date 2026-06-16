#!/bin/bash
# Let's Encrypt SSL Certificate Setup and Auto-Renewal
# Usage: ./scripts/setup_ssl.sh <domain> <email>

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
    echo "Usage: $0 <domain> <email>"
    echo "Example: $0 gaokao.example.com admin@example.com"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Setting up SSL certificate for $DOMAIN..."

# Create directories
mkdir -p /var/www/certbot
mkdir -p data/ssl

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    apt-get update && apt-get install -y certbot python3-certbot-nginx
fi

# Stop nginx temporarily to free port 80
docker compose -f docker-compose.prod.yml stop nginx || true

# Obtain certificate using standalone mode
certbot certonly \
    --standalone \
    --preferred-challenges http \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive

# Copy certificates to nginx directory
cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" data/ssl/fullchain.pem
cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" data/ssl/privkey.pem

# Set permissions
chmod 644 data/ssl/fullchain.pem
chmod 600 data/ssl/privkey.pem

# Start nginx
docker compose -f docker-compose.prod.yml --profile nginx up -d nginx

echo "[$(date '+%Y-%m-%d %H:%M:%S')] SSL certificate setup completed!"
echo "Certificate will auto-renew via cron job."

# Setup auto-renewal cron job (runs daily at 3 AM)
CRON_CMD="0 3 * * * root /usr/bin/certbot renew --quiet --post-hook 'docker compose -f /app/docker-compose.prod.yml restart nginx'"
if ! grep -q "certbot renew" /etc/crontab; then
    echo "$CRON_CMD" >> /etc/crontab
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-renewal cron job added."
fi

echo ""
echo "Next steps:"
echo "1. Update your domain DNS A record to point to this server"
echo "2. Test HTTPS: curl -f https://$DOMAIN/api/v1/health"
echo "3. Certificate expires in 90 days, auto-renewal is configured"
