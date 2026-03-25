#!/bin/bash
# DevOps Monitor - Production Deployment Script
# Usage: ./deploy.sh

set -e

echo "🚀 DevOps Monitor - Production Deployment"
echo "=========================================="

# Check if running on Linux
if [[ ! "$OSTYPE" == "linux-gnu"* ]]; then
    echo "❌ This script must run on Linux. Detected: $OSTYPE"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env and set SECRET_KEY"
    echo "   Run: nano .env"
    exit 1
fi

# Check if SECRET_KEY is set
if ! grep -q "SECRET_KEY=" .env || grep "SECRET_KEY=your-very-long" .env > /dev/null; then
    echo "❌ SECRET_KEY is not set in .env!"
    echo "📝 Please edit .env and set a secure SECRET_KEY"
    echo "   Run: nano .env"
    exit 1
fi

echo "✅ .env file is configured"

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# Build and start services
echo "🏗️  Building Docker image..."
docker-compose -f docker-compose.prod.yml build

echo "🚀 Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
echo "🔍 Verifying services..."
if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    echo "✅ Services are running!"
else
    echo "❌ Services failed to start"
    docker-compose -f docker-compose.prod.yml logs
    exit 1
fi

# Display status
echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "🌐 Your site is available at:"
echo "   https://trevorvaughan.dev"
echo ""
echo "📋 Useful commands:"
echo "   View logs:    docker-compose -f docker-compose.prod.yml logs -f web"
echo "   Status:       docker-compose -f docker-compose.prod.yml ps"
echo "   Restart:      docker-compose -f docker-compose.prod.yml restart"
echo "   Stop:         docker-compose -f docker-compose.prod.yml down"
echo ""
echo "🔒 SSL Certificate:"
echo "   Get cert:     sudo certbot certonly --standalone -d trevorvaughan.dev"
echo "   View certs:   sudo certbot certificates"
echo ""
echo "Happy monitoring! 🚀"
