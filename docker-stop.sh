#!/bin/bash

# Docker stop script for Target Scraper API

echo "🛑 Stopping Target Scraper API"
echo "=============================="

# Stop and remove containers
docker-compose down

echo "✅ Target Scraper API stopped!"

# Optional: Remove images (uncomment if you want to clean up)
# echo "🧹 Cleaning up Docker images..."
# docker-compose down --rmi all

echo ""
echo "📊 To start again, run: ./docker-run.sh"
echo "🧹 To clean up everything, run: docker-compose down --rmi all --volumes"
