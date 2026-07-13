#!/bin/bash
# Monitoring Stack Deployment Script
# Deploys Prometheus, Grafana, Loki, and Alertmanager

set -euo pipefail

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deploying monitoring stack..."

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "ERROR: Docker Compose plugin is not installed"
    exit 1
fi

# Create necessary directories
mkdir -p monitoring/rules
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/datasources
mkdir -p logs

# Set environment variables for alerting
export SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
export SMTP_PASSWORD="${SMTP_PASSWORD:-}"
export GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-}"

if [[ -z "$GRAFANA_ADMIN_PASSWORD" ]]; then
    echo "ERROR: GRAFANA_ADMIN_PASSWORD must be set; default admin passwords are not allowed"
    exit 1
fi

# Validate Slack webhook URL if provided
if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
    if [[ ! "$SLACK_WEBHOOK_URL" =~ ^https://hooks\.slack\.com/ ]]; then
        echo "WARNING: Invalid Slack webhook URL format"
        echo "Expected format: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        read -p "Continue without Slack notifications? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        unset SLACK_WEBHOOK_URL
    fi
fi

# Start monitoring stack
echo "Starting monitoring services..."
docker compose -f docker-compose.prod.yml \
    -f docker-compose.monitoring.yml \
    --profile monitoring \
    up -d

# Wait for services to be healthy
echo "Waiting for services to become healthy..."
sleep 10

# Check service status
echo ""
echo "Service Status:"
echo "==============="
docker compose -f docker-compose.prod.yml \
    -f docker-compose.monitoring.yml \
    --profile monitoring \
    ps

# Display access information
echo ""
echo "Monitoring Stack Access:"
echo "========================"
echo "Grafana:      http://localhost:3000 (admin/$GRAFANA_ADMIN_PASSWORD)"
echo "Prometheus:   http://localhost:9090"
echo "Alertmanager: http://localhost:9093"
echo "Loki:         http://localhost:3100"
echo ""
echo "Next Steps:"
echo "1. Login to Grafana and verify dashboards"
echo "2. Configure Slack webhook in .env.production if needed"
echo "3. Set up email alerts by configuring SMTP settings"
echo "4. Import additional dashboards from Grafana marketplace"
echo ""
echo "Documentation:"
echo "- Prometheus: https://prometheus.io/docs/"
echo "- Grafana:    https://grafana.com/docs/"
echo "- Loki:       https://grafana.com/docs/loki/"
echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Monitoring stack deployment completed!"
