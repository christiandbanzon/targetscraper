#!/bin/bash

# Docker run script for Target Scraper API

echo "🐳 Target Scraper API - Docker Setup"
echo "===================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create outputs directory if it doesn't exist
mkdir -p outputs/jobs

echo "📦 Building Docker image..."
docker-compose build

echo "🚀 Starting Target Scraper API..."
docker-compose up -d

echo ""
echo "✅ Target Scraper API is now running!"
echo ""
echo "🌐 Access points:"
echo "   API Documentation: http://localhost:8000/docs"
echo "   Alternative Docs:  http://localhost:8000/redoc"
echo "   API Root:          http://localhost:8000"
echo ""
echo "📊 Management commands:"
echo "   View logs:         docker-compose logs -f"
echo "   Stop service:      docker-compose down"
echo "   Restart service:   docker-compose restart"
echo "   View status:       docker-compose ps"
echo ""
echo "🔧 With Nginx (optional):"
echo "   docker-compose --profile with-nginx up -d"
echo "   Then access via: http://localhost"
