#!/usr/bin/env python3
"""
Performance-optimized async keyword scraper for Target.com products
Uses async HTTP, connection pooling, caching, and concurrent processing
"""

import asyncio
import re
import os
import logging
from typing import List, Dict, Any, Optional, Callable
from bs4 import BeautifulSoup
from datetime import datetime
import httpx
from cachetools import TTLCache
from config import Config
from retry_utils import retry_with_backoff
from rate_limiter import get_rate_limiter, DEFAULT_RATE_LIMITS
from data_validator import DataValidator
from pagination import PaginationHelper

# Setup logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Response cache - 1 hour TTL to avoid duplicate API calls
response_cache = TTLCache(maxsize=1000, ttl=3600)

# Global HTTP client with connection pooling
_http_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    """Get or create async HTTP client with connection pooling"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(Config.API_TIMEOUT, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            http2=True  # HTTP/2 support for better performance
        )
    return _http_client

async def close_http_client():
    """Close HTTP client connection pool"""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None

async def _make_api_request(search_keyword: str, page: int = 1) -> httpx.Response:
    """Make API request with retry logic (internal function for retry)"""
    # Rate limiting
    rate_limiter = get_rate_limiter()
    limits = DEFAULT_RATE_LIMITS.get("keyword_search", {"rate": 2.0, "capacity": 5.0})
    await rate_limiter.limit("keyword_search", **limits)
    
    # Get HTTP client
    client = await get_http_client()
    
    # Prepare API request
    payload = Config.get_search_payload(search_keyword)
    headers = Config.get_headers()
    
    logger.debug(f"Making API request for '{search_keyword}' (page {page})")
    response = await client.post(
        Config.API_BASE_URL,
        auth=(Config.OXYLABS_USERNAME, Config.OXYLABS_PASSWORD),
        json=payload,
        headers=headers
    )
    
    response.raise_for_status()
    return response

async def keyword_scraper_async(
    search_keyword: str, 
    max_pages: int = 5,
    progress_callback: Optional[Callable[[int, int], Any]] = None
) -> Dict[str, Any]:
    """
    Async scrape products for any keyword from Target.com with pagination and retry logic
    
    Args:
        search_keyword: The search term to look for on Target.com
        max_pages: Maximum number of pages to scrape (default: 5)
        progress_callback: Optional callback function(page, total_pages) for progress updates
        
    Returns:
        dict: Result with success status, products list, and filename
    """
    logger.info(f"Starting async keyword search for: '{search_keyword}' (max {max_pages} pages)")
    
    try:
        # Validate input
        if not search_keyword or not search_keyword.strip():
            logger.error("Empty or invalid search keyword provided")
            return {"success": False, "products": [], "filename": None, "error": "Invalid keyword"}
            
        search_keyword = search_keyword.strip()
        
        # Check cache first
        cache_key = f"search:{search_keyword.lower()}:pages:{max_pages}"
        if cache_key in response_cache:
            logger.info(f"Cache hit for: '{search_keyword}'")
            cached_data = response_cache[cache_key]
            return {"success": True, "products": cached_data["products"], "filename": cached_data["filename"]}
        
        all_products = []
        page = 1
        
        # Scrape multiple pages
        while page <= max_pages:
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(page, max_pages)
                else:
                    progress_callback(page, max_pages)
            
            logger.info(f"Scraping page {page}/{max_pages} for '{search_keyword}'")
            
            # Make API request with retry logic
            try:
                response = await retry_with_backoff(
                    _make_api_request,
                    max_retries=Config.API_MAX_RETRIES,
                    initial_delay=1.0,
                    max_delay=60.0,
                    search_keyword=search_keyword,
                    page=page
                )
            except Exception as e:
                logger.error(f"Failed to get page {page} after retries: {e}")
                break
            
            data = response.json()
            if not data.get('results') or not data['results']:
                logger.warning(f"No results returned from Oxylabs for page {page}")
                break
                
            html_content = data['results'][0]['content']
            
            # Parse products from HTML
            page_products = await parse_products_async(html_content, search_keyword)
            all_products.extend(page_products)
            
            logger.info(f"Page {page}: Found {len(page_products)} products (total: {len(all_products)})")
            
            # Check if there are more pages
            if not PaginationHelper.has_more_pages(html_content):
                logger.info(f"No more pages available (stopped at page {page})")
                break
            
            page += 1
        
        # Validate and clean products
        logger.info(f"Validating {len(all_products)} products...")
        validation_result = DataValidator.validate_products(all_products)
        
        # Remove duplicates
        unique_products = DataValidator.remove_duplicates(validation_result["valid_products"])
        
        # Calculate quality score
        quality_score = DataValidator.quality_score(unique_products)
        
        logger.info(f"Validation complete: {len(unique_products)}/{len(all_products)} valid products "
                   f"(quality score: {quality_score:.2%})")
        
        # Save results if products found
        if unique_products:
            filename = _generate_filename(search_keyword)
            await save_products_csv_async(unique_products, filename)
            
            # Cache the results
            response_cache[cache_key] = {"products": unique_products, "filename": filename}
            
            logger.info(f"SUCCESS: {len(unique_products)} products saved to {filename}")
            return {
                "success": True, 
                "products": unique_products, 
                "filename": filename,
                "pages_scraped": page - 1,
                "total_found": len(all_products),
                "valid_products": len(unique_products),
                "quality_score": quality_score,
                "validation": validation_result
            }
        else:
            logger.warning(f"No valid products found for keyword: '{search_keyword}'")
            return {
                "success": False, 
                "products": [], 
                "filename": None, 
                "error": "No valid products found",
                "validation": validation_result
            }
            
    except Exception as e:
        logger.error(f"Unexpected error during scraping '{search_keyword}': {e}")
        return {"success": False, "products": [], "filename": None, "error": str(e)}

async def parse_products_async(html_content: str, search_keyword: str) -> List[Dict[str, str]]:
    """
    Async parse products from HTML content using lxml parser for speed
    
    Args:
        html_content: Raw HTML content from Target.com
        search_keyword: The search keyword used (for logging)
        
    Returns:
        List of product dictionaries
    """
    logger.info(f"Parsing products from HTML for: '{search_keyword}'")
    
    # Use lxml parser for better performance (much faster than html.parser)
    soup = BeautifulSoup(html_content, 'lxml')
    products = []
    
    # Find all product links using optimized selector
    links = soup.find_all('a', href=re.compile(r'/p/'))
    logger.debug(f"Found {len(links)} potential product links")
    
    seen_urls = set()
    
    # Process links synchronously (parsing is fast, no need for async overhead)
    for link in links:
        try:
            product = _extract_product_data(link, href=link.get('href', ''), seen_urls=seen_urls)
            if product:
                products.append(product)
        except Exception as e:
            logger.warning(f"Error processing product link: {e}")
            continue
    
    logger.info(f"Successfully parsed {len(products)} products")
    return products

def _extract_product_data(link, href: str, seen_urls: set) -> Optional[Dict[str, str]]:
    """Extract product data from a link element"""
    try:
        if not href.startswith('/p/'):
            return None
            
        full_url = f"https://www.target.com{href}"
        
        # Skip duplicates
        if full_url in seen_urls:
            return None
        seen_urls.add(full_url)
        
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

async def batch_scrape_keywords(keywords: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Scrape multiple keywords concurrently
    
    Args:
        keywords: List of search keywords
        
    Returns:
        Dictionary mapping keyword to result
    """
    logger.info(f"Starting batch scrape for {len(keywords)} keywords")
    
    # Create tasks for all keywords
    tasks = {keyword: keyword_scraper_async(keyword) for keyword in keywords}
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    
    # Map results back to keywords
    result_dict = {}
    for keyword, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            result_dict[keyword] = {"success": False, "error": str(result), "products": []}
        else:
            result_dict[keyword] = result
    
    logger.info(f"Completed batch scrape: {sum(1 for r in result_dict.values() if r.get('success'))} successful")
    return result_dict

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

async def save_products_csv_async(products: List[Dict[str, str]], filename: str) -> None:
    """
    Async save products to CSV file using aiofiles
    
    Args:
        products: List of product dictionaries
        filename: Output filename
    """
    logger.info(f"Saving {len(products)} products to {filename}")
    
    try:
        import aiofiles
        import csv
        import io
        
        # Prepare CSV content
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=Config.CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(products)
        csv_content = output.getvalue()
        output.close()
        
        # Write asynchronously
        async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
            await f.write(csv_content)
        
        logger.info(f"Successfully saved products to {filename}")
    except Exception as e:
        logger.error(f"Error saving products to {filename}: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) > 1:
            keyword = sys.argv[1]
            result = await keyword_scraper_async(keyword)
            if result["success"]:
                print(f"SUCCESS: Scraping completed for '{keyword}'")
                print(f"Found {len(result['products'])} products")
            else:
                print(f"FAILED: Scraping failed for '{keyword}'")
                print(f"Error: {result.get('error', 'Unknown error')}")
                sys.exit(1)
        else:
            print("Usage: python async_keyword_scraper.py 'search keyword'")
            print("Example: python async_keyword_scraper.py 'Nike Air Max'")
            sys.exit(1)
    
    asyncio.run(main())

