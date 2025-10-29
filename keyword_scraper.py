#!/usr/bin/env python3
"""
Keyword-based scraper for Target.com products
Professional implementation with proper error handling and logging
"""

import requests
import csv
import re
import sys
import os
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime
from config import Config

# Setup logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

def keyword_scraper(search_keyword: str) -> bool:
    """
    Scrape products for any keyword from Target.com
    
    Args:
        search_keyword: The search term to look for on Target.com
        
    Returns:
        bool: True if scraping was successful, False otherwise
    """
    logger.info(f"Starting keyword search for: '{search_keyword}'")
    
    try:
        # Validate input
        if not search_keyword or not search_keyword.strip():
            logger.error("Empty or invalid search keyword provided")
            return False
            
        search_keyword = search_keyword.strip()
        
        # Search for keyword using Oxylabs API
        payload = Config.get_search_payload(search_keyword)
        
        logger.info(f"Making API request to Oxylabs for: '{search_keyword}'")
        response = requests.post(
            Config.API_BASE_URL,
            auth=(Config.OXYLABS_USERNAME, Config.OXYLABS_PASSWORD),
            json=payload,
            headers=Config.get_headers(),
            timeout=Config.API_TIMEOUT
        )
        
        response.raise_for_status()
        
        data = response.json()
        if not data.get('results') or not data['results']:
            logger.warning(f"No results returned from Oxylabs for: '{search_keyword}'")
            return False
            
        html_content = data['results'][0]['content']
        
        # Parse products from HTML
        products = parse_products(html_content, search_keyword)
        
        # Save results if products found
        if products:
            filename = _generate_filename(search_keyword)
            save_products_csv(products, filename)
            logger.info(f"SUCCESS: {len(products)} products saved to {filename}")
            return True
        else:
            logger.warning(f"No products found for keyword: '{search_keyword}'")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for '{search_keyword}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during scraping '{search_keyword}': {e}")
        return False

def parse_products(html_content: str, search_keyword: str) -> List[Dict[str, str]]:
    """
    Parse products from HTML content
    
    Args:
        html_content: Raw HTML content from Target.com
        search_keyword: The search keyword used (for logging)
        
    Returns:
        List of product dictionaries
    """
    logger.info(f"Parsing products from HTML for: '{search_keyword}'")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    # Find all product links
    links = soup.find_all('a', href=re.compile(r'/p/'))
    logger.debug(f"Found {len(links)} potential product links")
    
    seen_urls = set()
    
    for link in links:
        try:
            href = link.get('href', '')
            if not href.startswith('/p/'):
                continue
                
            full_url = f"https://www.target.com{href}"
            
            # Skip duplicates
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Extract product data
            product = _extract_product_data(link, href, full_url)
            if product:
                products.append(product)
                
        except Exception as e:
            logger.warning(f"Error parsing product link {href}: {e}")
            continue
    
    logger.info(f"Successfully parsed {len(products)} products")
    return products

def _extract_product_data(link, href: str, full_url: str) -> Optional[Dict[str, str]]:
    """Extract product data from a link element"""
    try:
        # Extract TCIN
        tcin_match = re.search(r'/A-(\d+)', href)
        tcin = tcin_match.group(1) if tcin_match else ""
        
        # Extract title
        title = _extract_title(link, href)
        
        # Extract price and image
        price = _extract_price_from_link(link)
        image_url = _extract_image_from_link(link)
        
        # Clean URL (remove fragments and query params)
        clean_url = full_url.split('#')[0].split('?')[0]
        
        return {
            'listing_title': title,
            'listings_url': clean_url,
            'image_url': image_url,
            'marketplace': Config.TARGET_INFO['name'],
            'price': price,
            'currency': 'USD',
            'shipping': '',
            'units_available': '',
            'item_number': tcin,
            'tcin': tcin,
            'upc': '',
            'seller_name': Config.TARGET_INFO['name'],
            'seller_url': Config.TARGET_INFO['url'],
            'seller_business': Config.TARGET_INFO['business'],
            'seller_address': Config.TARGET_INFO['address'],
            'seller_email': '',
            'seller_phone': Config.TARGET_INFO['phone']
        }
    except Exception as e:
        logger.warning(f"Error extracting product data: {e}")
        return None

def _extract_title(link, href: str) -> str:
    """Extract product title from link element"""
    # Try to get title from link text
    title = link.get_text(strip=True)
    if title and len(title) > 5:  # Valid title
        return title
    
    # Try to get title from parent elements
    parent = link.find_parent(['h2', 'h3', 'h4', 'div'])
    if parent:
        parent_title = parent.get_text(strip=True)
        if parent_title and len(parent_title) > 5:
            return parent_title
    
    # Fallback to URL-based title
    return _extract_title_from_url(href)

def _extract_title_from_url(url: str) -> str:
    """Extract title from URL path"""
    try:
        path = url.split('/p/')[-1].split('/-')[0]
        title = path.replace('-', ' ').replace('_', ' ').title()
        return title if title else "Product"
    except Exception:
        return "Product"

def _extract_price_from_link(link) -> str:
    """Extract price from link element"""
    try:
        price_elem = link.find(['span', 'div'], class_=re.compile(r'price|cost|amount'))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            if '$' in price_text:
                return price_text
    except Exception:
        pass
    return ""

def _extract_image_from_link(link) -> str:
    """Extract image URL from link element"""
    try:
        img = link.find('img')
        if img and img.get('src'):
            return img.get('src')
    except Exception:
        pass
    return ""

def _generate_filename(search_keyword: str) -> str:
    """Generate clean filename for search results"""
    # Clean the keyword for filename
    clean_keyword = re.sub(r'[^\w\s-]', '', search_keyword)
    clean_keyword = re.sub(r'[-\s]+', '_', clean_keyword)
    clean_keyword = clean_keyword.strip('_').lower()
    
    # Ensure output directory exists
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    
    return os.path.join(Config.OUTPUT_DIR, f"{clean_keyword}_PRODUCTS.csv")

def save_products_csv(products: List[Dict[str, str]], filename: str) -> None:
    """
    Save products to CSV file
    
    Args:
        products: List of product dictionaries
        filename: Output filename
    """
    logger.info(f"Saving {len(products)} products to {filename}")
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=Config.CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerows(products)
        logger.info(f"Successfully saved products to {filename}")
    except Exception as e:
        logger.error(f"Error saving products to {filename}: {e}")
        raise

if __name__ == "__main__":
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
        success = keyword_scraper(keyword)
        if success:
            print(f"SUCCESS: Scraping completed for '{keyword}'")
        else:
            print(f"FAILED: Scraping failed for '{keyword}'")
            sys.exit(1)
    else:
        print("Usage: python keyword_scraper.py 'search keyword'")
        print("Example: python keyword_scraper.py 'Nike Air Max'")
        sys.exit(1)
