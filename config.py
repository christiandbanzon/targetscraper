#!/usr/bin/env python3
"""
Configuration settings for Target Scraper
"""

import os
from typing import Dict, Any

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, use system environment variables
    pass

class Config:
    """Configuration class for Target Scraper"""
    
    # API Credentials (from environment variables)
    OXYLABS_USERNAME = os.getenv("OXYLABS_USERNAME", "tereo_gmDZq")
    OXYLABS_PASSWORD = os.getenv("OXYLABS_PASSWORD", "7xiek=6GMk4BgLY")
    
    # API Settings
    API_BASE_URL = "https://realtime.oxylabs.io/v1/queries"
    API_TIMEOUT = 120
    API_MAX_RETRIES = 3
    
    # Scraping Settings
    DEFAULT_GEO_LOCATION = "United States"
    DEFAULT_USER_AGENT_TYPE = "desktop"
    
    # File Settings
    OUTPUT_DIR = "outputs"
    CSV_FIELDNAMES = [
        "listing_title", "listings_url", "image_url", "marketplace", "price", "currency",
        "shipping", "units_available", "item_number", "tcin", "upc", "seller_name",
        "seller_url", "seller_business", "seller_address", "seller_email", "seller_phone"
    ]
    
    # Target Store Info
    TARGET_INFO = {
        "name": "Target",
        "url": "https://www.target.com",
        "business": "Target Corporation",
        "address": "1000 Nicollet Mall, Minneapolis, MN 55403",
        "phone": "1-800-440-0680"
    }
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        """Get default HTTP headers"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    @classmethod
    def get_search_payload(cls, query: str) -> Dict[str, Any]:
        """Get standard search payload for Oxylabs API"""
        return {
            "source": "target_search",
            "query": query,
            "geo_location": cls.DEFAULT_GEO_LOCATION,
            "render": "html",
            "user_agent_type": cls.DEFAULT_USER_AGENT_TYPE
        }