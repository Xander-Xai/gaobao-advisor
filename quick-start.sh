#!/bin/bash
# Quick Start Script - One-click deployment for production
# Usage: ./quick-start.sh <domain> <email>

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
    echo "Usage: $0 <domain> <email>"
    echo "Example: $0 gaokao.example.com admin@example.com"
    exit 1
fi

echo "=========================================="
echo " Gaokao Advisor - Quick Start"
echo "=========================================="
echo ""
echo "Domain: $DOMAIN"
echo "Email:  $EMAIL"
echo ""

# Check prerequisites
echo "[1/6] Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    echo "Install Docker: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "ERROR: Docker Compose plugin is not installed"
    exit 1
fi

echo "✓ Docker and Docker Compose are available"
echo ""

# Setup environment
echo "[2/6] Setting up environment..."
if [[ ! -f .env.production ]]; then
    cp .env.example .env.production
    echo "✓ Created .env.production from template"
    
    # Generate SESSION_SECRET
    SECRET=$(openssl rand -hex 32)
    sed -i "s/^SESSION_SECRET=.*/SESSION_SECRET=$SECRET/" .env.production
    echo "✓ Generated SESSION_SECRET"
else
    echo "✓ .env.production already exists"
fi
echo ""

# Setup SSL
echo "[3/6] Setting up SSL certificate..."
chmod +x scripts/setup_ssl.sh
./scripts/setup_ssl.sh "$DOMAIN" "$EMAIL"
echo ""

# Build and start services
echo "[4/6] Building and starting services..."
docker compose -f docker-compose.prod.yml --profile nginx up -d --build
echo "✓ API and Nginx started"
echo ""

# Deploy monitoring stack
echo "[5/6] Deploying monitoring stack..."
chmod +x scripts/deploy_monitoring.sh
./scripts/deploy_monitoring.sh
echo ""

# Run validation
echo "[6/6] Running validation..."
sleep 10

# Health check
echo "Checking health endpoint..."
if curl -f -k https://$DOMAIN/api/v1/health > /dev/null 2>&1; then
    echo "✓ Health check passed"
else
    echo "⚠ Health check failed (may need DNS propagation)"
    echo "  Try: curl -f http://localhost:8000/api/v1/health"
fi

# Data validation
echo "Validating data..."
docker exec -it gaokao-api-prod python scripts/validate_data.py | head -20
echo ""

# Display summary
echo "=========================================="
echo " Deployment Complete!"
echo "=========================================="
echo ""
echo "Service URLs:"
echo "  API:          https://$DOMAIN/api/v1"
echo "  Grafana:      http://localhost:3000 (admin/admin)"
echo "  Prometheus:   http://localhost:9090"
echo "  Alertmanager: http://localhost:9093"
echo ""
echo "Next Steps:"
echo "  1. Update DNS A record for $DOMAIN"
echo "  2. Login to Grafana and verify dashboards"
echo "  3. Configure Slack webhook in .env.production"
echo "  4. Test chat: curl -X POST https://$DOMAIN/api/v1/chat ..."
echo ""
echo "Documentation:"
echo "  - P1 Issues Resolved: P1-ISSUES-RESOLVED-2026-06-16.md"
echo "  - Deploy Checklist: docs/deploy-checklist-updated.md"
echo "  - Production Report: PRODUCTION-READY-REPORT-2026-06-16.md"
echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Quick start completed!"
