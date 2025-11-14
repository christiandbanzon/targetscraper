#!/usr/bin/env python3
"""
Configuration settings for Target Scraper

All sensitive credentials should be provided via environment variables.
Never commit credentials to version control.
"""

import os
from typing import Dict, Any
from pathlib import Path

# Load environment variables from .env file
# Look for .env in project root (parent of app/ directory)
try:
    from dotenv import load_dotenv
    # Get project root (parent of app directory)
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, use system environment variables
    pass


class Config:
    """
    Configuration class for Target Scraper
    
    All configuration values can be overridden via environment variables.
    Sensitive credentials MUST be provided via environment variables.
    """
    
    # API Credentials (MUST be provided via environment variables)
    OXYLABS_USERNAME = os.getenv("OXYLABS_USERNAME")
    OXYLABS_PASSWORD = os.getenv("OXYLABS_PASSWORD")
    
    # Validate required credentials
    if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
        raise ValueError(
            "OXYLABS_USERNAME and OXYLABS_PASSWORD must be set via environment variables. "
            "Create a .env file or set them as environment variables."
        )
    
    # API Settings
    API_BASE_URL = "https://realtime.oxylabs.io/v1/queries"
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "120"))
    API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
    
    # Scraping Settings
    DEFAULT_GEO_LOCATION = os.getenv("DEFAULT_GEO_LOCATION", "United States")
    DEFAULT_USER_AGENT_TYPE = os.getenv("DEFAULT_USER_AGENT_TYPE", "desktop")
    
    # File Settings
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")
    CSV_FIELDNAMES = [
        "Listing Title*", "Listings URL*", "Image URL*", "Marketplace*", "Price*", "Shipping",
        "Units Available", "Item Number", "Brand", "ASIN", "UPC", "Walmart ID",
        "Seller's Name*", "Seller's URL*", "Seller's Business Name", "Seller's Address",
        "Seller's Email", "Seller's Phone Number"
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
        """
        Get default HTTP headers for API requests
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    @classmethod
    def get_search_payload(cls, query: str) -> Dict[str, Any]:
        """
        Get standard search payload for Oxylabs API
        
        Args:
            query: Search query string
            
        Returns:
            Dictionary payload for API request
        """
        return {
            "source": "target_search",
            "query": query,
            "geo_location": cls.DEFAULT_GEO_LOCATION,
            "render": "html",
            "user_agent_type": cls.DEFAULT_USER_AGENT_TYPE
        }