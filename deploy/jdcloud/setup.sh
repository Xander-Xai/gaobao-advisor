#!/bin/bash
set -e

echo "=========================================="
echo "  Gaobao Advisor - JD Cloud Deployment"
echo "=========================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
   echo -e "${RED}Please run as root (sudo)${NC}"
   exit 1
fi

echo -e "${YELLOW}[1/8] Updating system packages...${NC}"
apt-get update -qq
apt-get upgrade -y -qq

echo -e "${YELLOW}[2/8] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "Docker already installed"
fi

echo -e "${YELLOW}[3/8] Installing Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    apt-get install -y docker-compose-plugin
fi

echo -e "${YELLOW}[4/8] Setting up project...${NC}"
PROJECT_DIR="/opt/gaobao-advisor"
if [ -d "$PROJECT_DIR" ]; then
    echo "Project exists, pulling latest..."
    cd "$PROJECT_DIR"
    git pull
else
    echo "Cloning project..."
    git clone https://github.com/yourname/gaobao-advisor.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

echo -e "${YELLOW}[5/8] Building frontend...${NC}"
cd "$PROJECT_DIR/frontend"
npm install
npm run build

echo -e "${YELLOW}[6/8] Setting up environment...${NC}"
cd "$PROJECT_DIR"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${RED}Please edit .env with your API keys before starting${NC}"
fi
mkdir -p data/reports

echo -e "${YELLOW}[7/8] Starting services...${NC}"
cd "$PROJECT_DIR/deploy/jdcloud"
docker-compose down 2>/dev/null || true
docker-compose up -d --build

echo -e "${YELLOW}[8/8] Health check...${NC}"
sleep 5
if curl -sf http://localhost/api/v1/health > /dev/null; then
    echo -e "${GREEN}✓ Deployment successful!${NC}"
    echo -e "${GREEN}  API: http://$(curl -s ifconfig.me)/api/v1/health${NC}"
    echo -e "${GREEN}  App: http://$(curl -s ifconfig.me)/${NC}"
else
    echo -e "${RED}✗ Health check failed. Check logs: docker-compose logs${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "Useful commands:"
echo "  docker-compose logs -f    # View logs"
echo "  docker-compose ps       # Check status"
echo "  docker-compose restart   # Restart services"