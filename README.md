# Target Product Scraper

A professional, production-ready web scraper for Target.com products with FastAPI integration.

## Features

- 🔍 **Keyword-based scraping** - Search for any product on Target.com
- 🚀 **FastAPI REST API** - Async job processing with background tasks
- ⚡ **High Performance** - Async HTTP, connection pooling, caching, concurrent batch processing
- 🔄 **Retry Logic** - Exponential backoff for resilient error handling
- 🛡️ **Rate Limiting** - Token bucket algorithm to prevent API abuse
- 📄 **Pagination Support** - Automatically scrape multiple pages
- ✅ **Data Validation** - Quality checks, duplicate removal, completeness scoring
- 🔁 **Error Recovery** - Automatic retry with dead letter queue
- 📡 **Real-time Updates** - WebSocket and SSE support for live progress tracking
- 🐳 **Docker Support** - Containerized deployment with docker-compose
- 📊 **Professional Logging** - Comprehensive error handling and logging
- 🔒 **Secure Configuration** - Environment-based credential management

## Quick Start

### Prerequisites

- Python 3.8+
- Oxylabs API credentials

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd target-scraper

# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp env.example .env

# Edit .env with your credentials
# OXYLABS_USERNAME=your_username
# OXYLABS_PASSWORD=your_password
```

### Running the API

```bash
# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000

# Or use Docker
docker-compose up -d
```

### API Documentation

Once running, visit:
- Interactive API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Usage

### Start a Scraping Job

```bash
curl -X POST "http://localhost:8000/scrape/keyword" \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "Nike Air Max",
    "max_pages": 5
  }'
```

### Check Job Status

```bash
curl "http://localhost:8000/jobs/{job_id}"
```

### Real-time Progress Updates

**WebSocket:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/jobs/{job_id}');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress}% - ${data.message}`);
};
```

**Server-Sent Events:**
```javascript
const eventSource = new EventSource('/events/jobs/{job_id}');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress}%`);
};
```

### Batch Scraping

```bash
curl -X POST "http://localhost:8000/scrape/keywords/batch" \
  -H "Content-Type: application/json" \
  -d '["Nike Air Max", "iPhone 15", "Samsung Galaxy"]'
```

### Download Results

```bash
# Download CSV
curl "http://localhost:8000/download/{job_id}/csv" -o results.csv

# Download JSON
curl "http://localhost:8000/download/{job_id}/json" -o results.json
```

### View Dead Letter Queue

```bash
curl "http://localhost:8000/dead-letter-queue"
```

## Project Structure

```
target-scraper/
├── main.py                 # FastAPI application (entry point)
├── async_keyword_scraper.py # Core scraper with async operations
├── config.py               # Configuration management
├── retry_utils.py          # Retry logic with exponential backoff
├── rate_limiter.py         # Rate limiting implementation
├── data_validator.py       # Data validation and quality checks
├── pagination.py           # Pagination detection and handling
├── error_recovery.py       # Error recovery and dead letter queue
├── setup.py                # Setup script
├── test_keyword_api.py     # API test script
├── requirements.txt        # Python dependencies
├── env.example             # Environment variables template
├── Dockerfile              # Docker configuration
├── docker-compose.yml      # Docker Compose setup
├── nginx.conf              # Nginx reverse proxy config
├── README.md               # This file
└── .gitignore              # Git ignore rules
```

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OXYLABS_USERNAME` | Oxylabs API username | ✅ Yes | - |
| `OXYLABS_PASSWORD` | Oxylabs API password | ✅ Yes | - |
| `API_TIMEOUT` | API request timeout (seconds) | No | 120 |
| `API_MAX_RETRIES` | Maximum retry attempts | No | 3 |
| `LOG_LEVEL` | Logging level | No | INFO |
| `OUTPUT_DIR` | Output directory | No | outputs |

### Example .env File

```bash
OXYLABS_USERNAME=your_username_here
OXYLABS_PASSWORD=your_password_here
API_TIMEOUT=120
API_MAX_RETRIES=3
LOG_LEVEL=INFO
OUTPUT_DIR=outputs
```

## Docker Deployment

### Build and Run

```bash
# Build the image
docker build -t target-scraper .

# Run the container
docker run -p 8000:8000 --env-file .env target-scraper
```

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Features Deep Dive

### Retry Logic

Automatic retry with exponential backoff (1s → 2s → 4s → 8s... up to 60s max).
Retries on transient errors (timeouts, 429, 500-503).

### Rate Limiting

Token bucket algorithm with per-endpoint limits:
- API requests: 5/sec, burst 10
- Keyword search: 2/sec, burst 5
- Batch search: 1/sec, burst 3

### Pagination

Automatically detects and scrapes multiple pages. Configurable max pages (default: 5, max: 20).

### Data Validation

- Required field validation (title, URL, TCIN)
- URL and TCIN format validation
- Duplicate removal (by TCIN or URL)
- Data quality scoring (0.0-1.0)
- Completeness scoring

### Error Recovery

Automatic retry for failed jobs with exponential backoff (1min → 5min → 15min).
Persistent failures are moved to dead letter queue.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| POST | `/scrape/keyword` | Start keyword scraping job |
| POST | `/scrape/keywords/batch` | Start batch scraping job |
| GET | `/jobs/{job_id}` | Get job status |
| GET | `/jobs` | List all jobs |
| GET | `/download/{job_id}/csv` | Download results as CSV |
| GET | `/download/{job_id}/json` | Download results as JSON |
| GET | `/dead-letter-queue` | View failed jobs |
| WebSocket | `/ws/jobs/{job_id}` | Real-time progress updates |
| GET | `/events/jobs/{job_id}` | Server-Sent Events for progress |

## Development

### Code Quality

The project follows professional Python standards:
- ✅ Type hints throughout
- ✅ Comprehensive error handling
- ✅ Professional logging
- ✅ Input validation
- ✅ Modular architecture
- ✅ Environment-based configuration

### Testing

```bash
# Test API (when server running)
python test_keyword_api.py

# Run with uvicorn reload for development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Troubleshooting

### Common Issues

1. **"OXYLABS_USERNAME and OXYLABS_PASSWORD must be set"**
   - Create a `.env` file with your credentials
   - See `env.example` for template

2. **"Connection refused"**
   - Check if API server is running
   - Verify port 8000 is available

3. **"No products found"**
   - Check Oxylabs credentials
   - Verify search keyword is valid
   - Check API timeout settings

4. **"Rate limit exceeded"**
   - Reduce request frequency
   - Adjust rate limits in `rate_limiter.py`

## Security Notes

- ⚠️ **Never commit `.env` file** - Contains sensitive credentials
- ✅ Credentials are loaded from environment variables only
- ✅ `.gitignore` excludes sensitive files
- ✅ No hardcoded credentials in code

## License

[Your License Here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions, please open an issue on GitHub.
