# Target Product Scraper

A professional, keyword-based web scraper for Target.com products with FastAPI integration.

## Features

- 🔍 **Keyword-based scraping** - Search for any product on Target.com
- 🚀 **FastAPI integration** - RESTful API with async job processing
- 🐳 **Docker support** - Containerized deployment
- 📊 **Professional logging** - Comprehensive error handling and logging
- 🔒 **Environment-based config** - Secure credential management
- 📁 **Clean output** - Standardized CSV/JSON exports

## Quick Start

### 1. Setup Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd target-scraper

# Run setup script
python setup.py
```

### 2. Configure Credentials

Edit the `.env` file with your Oxylabs credentials:

```bash
# Copy the example file
cp env.example .env

# Edit with your credentials
OXYLABS_USERNAME=your_username_here
OXYLABS_PASSWORD=your_password_here
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Scraper

**Direct scraper:**
```bash
python keyword_scraper.py "Nike Air Max"
python keyword_scraper.py "iPhone 15"
python keyword_scraper.py "Samsung Galaxy"
```

**API server:**
```bash
uvicorn working_main:app --host 0.0.0.0 --port 8000
```

## API Usage

### Start a Scraping Job

```bash
curl -X POST "http://localhost:8000/scrape/keyword" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "Nike Air Max"}'
```

### Check Job Status

```bash
curl "http://localhost:8000/jobs/{job_id}"
```

### Download Results

```bash
# Download CSV
curl "http://localhost:8000/download/{job_id}/csv" -o results.csv

# Download JSON
curl "http://localhost:8000/download/{job_id}/json" -o results.json
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

# Stop services
docker-compose down
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OXYLABS_USERNAME` | Oxylabs API username | Required |
| `OXYLABS_PASSWORD` | Oxylabs API password | Required |
| `API_TIMEOUT` | API request timeout (seconds) | 120 |
| `API_MAX_RETRIES` | Maximum retry attempts | 3 |
| `LOG_LEVEL` | Logging level | INFO |
| `OUTPUT_DIR` | Output directory | outputs |

### Example .env File

```bash
# Oxylabs API Credentials
OXYLABS_USERNAME=your_username_here
OXYLABS_PASSWORD=your_password_here

# API Configuration
API_TIMEOUT=120
API_MAX_RETRIES=3

# Logging
LOG_LEVEL=INFO

# Output Directory
OUTPUT_DIR=outputs
```

## Project Structure

```
target-scraper/
├── keyword_scraper.py      # Main scraper script
├── working_main.py         # FastAPI application
├── config.py              # Configuration management
├── setup.py               # Setup script
├── requirements.txt       # Python dependencies
├── env.example           # Environment template
├── .env                  # Environment variables (not in git)
├── .gitignore           # Git ignore rules
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose setup
├── outputs/             # Scraped data (not in git)
└── logs/               # Log files (not in git)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API status and info |
| `/scrape/keyword` | POST | Start keyword scraping job |
| `/scrape/category` | POST | Start category scraping job |
| `/jobs/{job_id}` | GET | Check job status |
| `/download/{job_id}/csv` | GET | Download CSV results |
| `/download/{job_id}/json` | GET | Download JSON results |
| `/jobs` | GET | List all jobs |
| `/search-examples` | GET | Get search examples |
| `/categories` | GET | Get available categories |

## Output Format

The scraper generates CSV files with the following columns:

- `listing_title` - Product name
- `listings_url` - Product URL
- `image_url` - Product image URL
- `marketplace` - Always "Target"
- `price` - Product price
- `currency` - Always "USD"
- `item_number` - Target item number (TCIN)
- `tcin` - Target Catalog Item Number
- `seller_name` - Always "Target"
- `seller_url` - Target website URL
- `seller_business` - Target Corporation
- `seller_address` - Target headquarters address
- `seller_phone` - Target customer service phone

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
# Test direct scraper
python keyword_scraper.py "test keyword"

# Test API (when server running)
python test_keyword_api.py
```

## Troubleshooting

### Common Issues

1. **"No module named 'dotenv'"**
   ```bash
   pip install python-dotenv
   ```

2. **"Connection refused"**
   - Check if API server is running
   - Verify port 8000 is available

3. **"No products found"**
   - Check Oxylabs credentials
   - Verify search keyword is valid
   - Check API timeout settings

### Logs

Check logs for detailed error information:

```bash
# View recent logs
tail -f logs/scraper.log
```

## License

This project is for educational and research purposes. Please respect Target.com's terms of service and robots.txt.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Create an issue in the repository