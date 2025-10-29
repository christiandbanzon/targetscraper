#!/usr/bin/env python3
"""
Clean up project files for GitHub
"""

import os
import shutil
from datetime import datetime

def cleanup_project():
    """Clean up project files"""
    
    print("Cleaning up project files...")
    
    # Files to keep (essential)
    keep_files = [
        'clean_fresh_scraper.py',  # Main scraper
        'working_main.py',         # FastAPI server
        'requirements.txt',        # Dependencies
        'README.md',              # Documentation
        'Dockerfile',             # Docker config
        'docker-compose.yml',     # Docker compose
        '.dockerignore',          # Docker ignore
        'nginx.conf',             # Nginx config
        'docker-run.sh',         # Docker scripts
        'docker-stop.sh',
        'config.py',              # Configuration
        'oxylabs_brand_search.py', # Core scrapers
        'oxylabs_simple.py',
        'oxylabs_fixed_timeout.py',
        'integrate_all_brands.py',
        'create_final_3_csvs.py'
    ]
    
    # Directories to keep
    keep_dirs = [
        'outputs'  # Keep outputs directory
    ]
    
    # Files to remove (test/debug files)
    remove_files = [
        'comprehensive_brand_scraper.py',
        'direct_brand_scraper.py',
        'test_all_brands.py',
        'test_api_brands.py',
        'comprehensive_learning_resources.py',
        'comprehensive_life_extensions.py',
        'deep_life_extensions_search.py',
        'debug_life_extensions.py',
        'extract_all_life_extensions.py',
        'extract_life_extensions_final.py',
        'analyze_life_extensions_html.py',
        'extract_life_extensions.py',
        'demo_api.py',
        'test_api.py',
        'start_api.py',
        'main.py',  # Old broken main
        'async_scrapers.py',  # Broken async scrapers
        'keep_essential_scripts.py',
        'cleanup_project.py'  # This file itself
    ]
    
    # Remove test files
    for file in remove_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"Removed: {file}")
            except Exception as e:
                print(f"Error removing {file}: {e}")
    
    # Clean up outputs directory - keep only the clean CSVs
    if os.path.exists('outputs'):
        for file in os.listdir('outputs'):
            if file.endswith('.csv') and 'CLEAN' not in file:
                try:
                    os.remove(os.path.join('outputs', file))
                    print(f"Removed old output: {file}")
                except Exception as e:
                    print(f"Error removing {file}: {e}")
    
    # Create .gitignore
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Temporary files
*.tmp
*.temp

# Keep only clean outputs
outputs/*.csv
!outputs/*_CLEAN.csv
"""
    
    with open('.gitignore', 'w') as f:
        f.write(gitignore_content)
    
    print("Created .gitignore")
    
    # Create clean README
    readme_content = """# Target Brand Scraper

A comprehensive web scraper for Target.com products by brand, with FastAPI integration and Docker support.

## Features

- **Brand-specific scraping** for Learning Resources, Lavazza, and Life Extensions
- **Fresh live data** from Target.com using Oxylabs API
- **Clean CSV outputs** - one file per brand
- **FastAPI integration** with job tracking and downloads
- **Docker support** for easy deployment
- **Professional data format** ready for analysis

## Quick Start

### Option 1: Direct Scraping
```bash
python clean_fresh_scraper.py
```

### Option 2: FastAPI Server
```bash
python working_main.py
```
Then visit: http://localhost:8000/docs

### Option 3: Docker
```bash
docker-compose up -d
```

## Output Files

- `Learning_Resources_CLEAN.csv` - Learning Resources products
- `Lavazza_CLEAN.csv` - Lavazza coffee products  
- `Life_Extensions_CLEAN.csv` - Life Extensions supplements

## API Endpoints

- `GET /` - API status
- `POST /scrape/brand` - Start brand scraping job
- `GET /jobs/{job_id}` - Check job status
- `GET /download/{job_id}/csv` - Download CSV results
- `GET /brands` - Available brands

## Requirements

- Python 3.12+
- Oxylabs API credentials
- See requirements.txt for dependencies

## License

MIT License
"""
    
    with open('README.md', 'w') as f:
        f.write(readme_content)
    
    print("Created README.md")
    
    print("\nProject cleanup completed!")
    print("Ready for GitHub!")

if __name__ == "__main__":
    cleanup_project()
