# Docker Guide for Target Scraper API

## 🐳 Docker Setup

This guide shows how to run the Target Scraper API using Docker and Docker Compose.

## Prerequisites

- Docker installed ([Download Docker](https://www.docker.com/get-started))
- Docker Compose installed (usually included with Docker Desktop)

## Quick Start

### 1. Build and Run with Docker Compose
```bash
# Make scripts executable (Linux/Mac)
chmod +x docker-run.sh docker-stop.sh

# Start the API
./docker-run.sh

# Or manually:
docker-compose up -d
```

### 2. Access the API
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **API Root**: http://localhost:8000

### 3. Stop the API
```bash
./docker-stop.sh

# Or manually:
docker-compose down
```

## Docker Commands

### Basic Operations
```bash
# Build the image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View running containers
docker-compose ps
```

### Advanced Operations
```bash
# Rebuild without cache
docker-compose build --no-cache

# Remove all containers and images
docker-compose down --rmi all --volumes

# Run in foreground (for debugging)
docker-compose up

# Execute commands in running container
docker-compose exec target-scraper-api bash
```

## With Nginx (Optional)

### Start with Nginx Reverse Proxy
```bash
docker-compose --profile with-nginx up -d
```

This will:
- Start the API on port 8000 (internal)
- Start Nginx on port 80 (external)
- Route all requests through Nginx to the API

Access via: http://localhost

## File Structure

```
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore           # Files to ignore in Docker build
├── nginx.conf              # Nginx configuration
├── docker-run.sh           # Start script
├── docker-stop.sh          # Stop script
└── DOCKER_GUIDE.md         # This guide
```

## Volume Mounts

The Docker setup includes volume mounts for:
- `./outputs:/app/outputs` - Scraped data and job results
- `./config.py:/app/config.py` - Configuration file

This ensures:
- Data persists between container restarts
- You can access scraped files from the host
- Configuration changes are reflected immediately

## Environment Variables

You can set environment variables in `docker-compose.yml`:

```yaml
environment:
  - PYTHONPATH=/app
  - PYTHONUNBUFFERED=1
  - LOG_LEVEL=info
  - MAX_JOBS=100
```

## Health Checks

The container includes health checks:
- **Interval**: Every 30 seconds
- **Timeout**: 30 seconds
- **Retries**: 3 attempts
- **Start Period**: 5 seconds

Check health status:
```bash
docker-compose ps
```

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs target-scraper-api

# Check if port is in use
netstat -tulpn | grep :8000

# Rebuild image
docker-compose build --no-cache
```

### Permission Issues
```bash
# Fix output directory permissions
sudo chown -R $USER:$USER outputs/

# Or run with different user
docker-compose exec target-scraper-api chown -R app:app /app/outputs
```

### Memory Issues
```bash
# Check container resource usage
docker stats

# Limit memory usage in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
```

## Production Deployment

### 1. Environment Configuration
Create `.env` file:
```env
PYTHONPATH=/app
LOG_LEVEL=info
MAX_JOBS=1000
CLEANUP_INTERVAL=24
```

### 2. Update docker-compose.yml
```yaml
services:
  target-scraper-api:
    # ... existing config ...
    env_file:
      - .env
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

### 3. Deploy
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Monitoring

### View Real-time Logs
```bash
docker-compose logs -f target-scraper-api
```

### Monitor Resource Usage
```bash
docker stats target-scraper-api
```

### Check API Health
```bash
curl http://localhost:8000/
```

## Backup and Restore

### Backup Data
```bash
# Backup outputs directory
tar -czf backup-$(date +%Y%m%d).tar.gz outputs/

# Or copy from container
docker cp target-scraper-api:/app/outputs ./backup-outputs
```

### Restore Data
```bash
# Extract backup
tar -xzf backup-20241029.tar.gz

# Or copy to container
docker cp ./backup-outputs target-scraper-api:/app/outputs
```

## Security Considerations

1. **Network Security**: The API is exposed on port 8000
2. **File Permissions**: Ensure proper permissions on mounted volumes
3. **Resource Limits**: Set appropriate memory and CPU limits
4. **Logging**: Monitor logs for suspicious activity
5. **Updates**: Regularly update base images and dependencies

## Support

If you encounter issues:
1. Check the logs: `docker-compose logs -f`
2. Verify Docker is running: `docker --version`
3. Check port availability: `netstat -tulpn | grep :8000`
4. Rebuild the image: `docker-compose build --no-cache`
