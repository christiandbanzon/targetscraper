#!/usr/bin/env python3
"""
Performance-optimized async keyword scraper for Target.com products
Uses async HTTP, connection pooling, caching, and concurrent processing
"""

import asyncio
import re
import os
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
from bs4 import BeautifulSoup
from datetime import datetime
import httpx
from cachetools import TTLCache
from .config import Config
from .retry_utils import retry_with_backoff
from .rate_limiter import get_rate_limiter, DEFAULT_RATE_LIMITS
from .data_validator import DataValidator
from .pagination import PaginationHelper

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
            http2=False  # Disable HTTP/2 to avoid h2 package dependency
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
            csv_filename = _generate_filename(search_keyword)
            json_filename = _generate_json_filename(search_keyword)
            await save_products_csv_async(unique_products, csv_filename)
            await save_products_json_async(unique_products, json_filename)
            
            # Cache the results
            response_cache[cache_key] = {"products": unique_products, "filename": csv_filename}
            
            logger.info(f"SUCCESS: {len(unique_products)} products saved to {csv_filename}")
            return {
                "success": True, 
                "products": unique_products, 
                "filename": csv_filename,
                "json_filename": json_filename,
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
            product = await _extract_product_data(link, href=link.get('href', ''), seen_urls=seen_urls)
            if product:
                products.append(product)
        except Exception as e:
            logger.warning(f"Error processing product link: {e}")
            continue
    
    logger.info(f"Successfully parsed {len(products)} products")
    return products

async def _extract_product_data(link, href: str, seen_urls: set) -> Optional[Dict[str, str]]:
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
        
        # Extract title (clean version without ratings/price)
        title = _extract_title(link, href)
        
        # Extract price and currency from search results
        price, currency = _extract_price_from_link(link)
        if price:
            logger.debug(f"Price extracted from search results: {price} for {full_url}")
        else:
            logger.debug(f"No price found in search results for: {full_url}")
        
        # Extract image
        image_url = _extract_image_from_link(link)
        
        # Clean URL (remove fragments and query params)
        clean_url = full_url.split('#')[0].split('?')[0]
        
        # Fetch UPC and price from product detail page
        # Note: This requires an additional API call per product, so it's slower
        # UPC is required for product identification, and we also fetch price if missing
        upc = ""
        detail_page_price = ""
        try:
            logger.debug(f"Fetching UPC and price from product detail page: {clean_url}")
            upc, detail_page_price = await _fetch_upc_and_price_from_product_page(clean_url)
            
            # Use detail page price if search page didn't have one
            if not price and detail_page_price:
                logger.info(f"Using price from product detail page: {detail_page_price} (search page had none)")
                price = detail_page_price
            elif price and detail_page_price:
                logger.debug(f"Price from search page: {price}, product page: {detail_page_price}")
            
            if upc:
                logger.info(f"UPC extracted successfully: {upc} for {clean_url}")
            else:
                logger.debug(f"UPC not found for: {clean_url}")
        except Exception as e:
            logger.warning(f"Product detail fetch failed for {clean_url}: {e}", exc_info=True)
        
        return {
            'Listing Title*': title,
            'Listings URL*': clean_url,
            'Image URL*': image_url,
            'Marketplace*': Config.TARGET_INFO['name'],
            'Price*': price,
            'Shipping': '',
            'Units Available': '',
            'Item Number': tcin,  # TCIN goes into Item Number column
            'Brand': '',
            'ASIN': '',
            'UPC': upc,  # UPC goes into UPC column
            'Walmart ID': '',
            "Seller's Name*": Config.TARGET_INFO['name'],
            "Seller's URL*": Config.TARGET_INFO['url'],
            "Seller's Business Name": Config.TARGET_INFO['business'],
            "Seller's Address": Config.TARGET_INFO['address'],
            "Seller's Email": '',
            "Seller's Phone Number": Config.TARGET_INFO['phone']
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
    """Extract clean product title from link element, removing ratings, price, etc."""
    try:
        # Target product cards typically have the title in a specific structure
        # Look for data-test attribute or specific class patterns
        title_elem = None
        
        # Try finding title in data-test="product-title" or similar
        title_elem = link.find(attrs={'data-test': re.compile(r'product.*title|title')})
        
        # If not found, try common Target title selectors
        if not title_elem:
            title_elem = link.find(['h2', 'h3', 'h4'], class_=re.compile(r'title|heading|name'))
        
        # If still not found, try getting from link's aria-label
        if not title_elem:
            aria_label = link.get('aria-label', '')
            if aria_label and len(aria_label) > 5:
                return _clean_title(aria_label)
        
        # Try link text but clean it
        if not title_elem:
            title_text = link.get_text(strip=True)
            if title_text:
                return _clean_title(title_text)
        
        # Extract from parent if available
        if not title_elem:
            parent = link.find_parent(['div', 'article', 'section'])
            if parent:
                title_elem = parent.find(['h2', 'h3', 'h4', 'span'], class_=re.compile(r'title|heading|name'))
        
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            return _clean_title(title_text)
        
        # Fallback to URL-based title
        return _extract_title_from_url(href)
    except Exception as e:
        logger.debug(f"Title extraction error: {e}")
        return _extract_title_from_url(href)

def _clean_title(title: str) -> str:
    """Clean title by removing ratings, price, and extra text"""
    if not title:
        return ""
    
    # Remove common patterns:
    # - "Highly rated" prefix
    # - Price patterns like "$8.49($0.71/ounce)"
    # - Star ratings like "4.7 out of 5 stars"
    # - Review counts like "with 262 ratings262 reviews"
    # - "Add to cart" suffix
    
    # Remove "Highly rated" prefix
    title = re.sub(r'^Highly rated\s*', '', title, flags=re.IGNORECASE)
    
    # Remove price patterns: $XX.XX or ($X.XX/unit)
    title = re.sub(r'\$[\d,]+\.?\d*\s*\(?\$?\d*\.?\d*/\w+\)?', '', title)
    
    # Remove star ratings: "4.7 out of 5 stars"
    title = re.sub(r'\d+\.?\d*\s*out\s*of\s*\d+\s*stars?', '', title, flags=re.IGNORECASE)
    
    # Remove review counts: "with 262 ratings" or "262 reviews"
    title = re.sub(r'\d+\s*(ratings?|reviews?)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'with\s+\d+\s*(ratings?|reviews?)', '', title, flags=re.IGNORECASE)
    
    # Remove "Add to cart" and similar buttons
    title = re.sub(r'(add\s+to\s+cart|buy\s+now|shop\s+now)', '', title, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Remove trailing punctuation and extra spaces
    title = title.strip('.,;:!?')
    
    return title if title else "Product"

def _extract_title_from_url(url: str) -> str:
    """Extract title from URL path"""
    try:
        path = url.split('/p/')[-1].split('/-')[0]
        title = path.replace('-', ' ').replace('_', ' ').title()
        return title if title else "Product"
    except Exception:
        return "Product"

def _extract_price_from_link(link) -> Tuple[str, str]:
    """Extract price and currency from link element with comprehensive methods
    
    Returns:
        tuple: (price_string, currency_code)
    """
    extraction_methods = []
    try:
        # Method 1: Look for data-test="product-price" or similar
        price_elem = link.find(attrs={'data-test': re.compile(r'product.*price|price|current.*price')})
        if price_elem:
            extraction_methods.append("data-test attribute")
        
        # Method 2: Look for data attribute containing price value
        if not price_elem:
            for attr in ['data-price', 'data-current-price', 'data-base-price', 'price', 'data-value']:
                price_attr = link.get(attr)
                if price_attr:
                    price_match = re.search(r'\$?[\d,]+\.?\d*', str(price_attr))
                    if price_match:
                        price_val = price_match.group(0)
                        if not price_val.startswith('$'):
                            price_val = f"${price_val}"
                        logger.debug(f"Price found via data attribute '{attr}': {price_val}")
                        return (price_val, 'USD')
        
        # Method 3: Look for span/div with price-related classes (more specific patterns)
        if not price_elem:
            price_elem = link.find(['span', 'div'], class_=re.compile(r'price|cost|amount|dollar|current.*price|product.*price|Price'))
            if price_elem:
                extraction_methods.append("price class selector")
        
        # Method 4: Look for text content with price pattern in all descendants
        if not price_elem:
            all_text_elements = link.find_all(['span', 'div', 'p', 'strong', 'b'], string=re.compile(r'\$[\d,]+\.?\d*'))
            if all_text_elements:
                price_text = all_text_elements[0].get_text(strip=True)
                price_match = re.search(r'\$[\d,]+\.?\d*', price_text)
                if price_match:
                    logger.debug(f"Price found via text content: {price_match.group(0)}")
                    return (price_match.group(0), 'USD')
        
        # Method 5: Look in parent container (check multiple levels up)
        if not price_elem:
            parent = link.find_parent(['div', 'article', 'section', 'li'])
            if parent:
                # Check parent and its siblings
                price_elem = parent.find(['span', 'div'], class_=re.compile(r'price|cost|amount|current.*price|Price'))
                # Also check parent's parent
                if not price_elem:
                    grandparent = parent.find_parent(['div', 'article', 'section'])
                    if grandparent:
                        price_elem = grandparent.find(['span', 'div'], class_=re.compile(r'price|cost|amount|current.*price|Price'))
                if price_elem:
                    extraction_methods.append("parent container")
        
        # Method 6: Search entire link text for price pattern
        if not price_elem:
            link_text = link.get_text(separator=' ', strip=True)
            # Look for price patterns: $XX.XX or $XX or Starting at $XX
            price_patterns = [
                r'\$[\d,]+\.?\d{2}',  # $XX.XX format
                r'\$[\d,]+\.?\d{1}',  # $XX.X format
                r'\$[\d,]+',  # $XX format
                r'(?:starting|from|price|now)[:\s]*\$?[\d,]+\.?\d*',  # "Starting at $XX" format
                r'price[:\s]*\$?[\d,]+\.?\d*',  # "Price: $XX" format
            ]
            for pattern in price_patterns:
                price_match = re.search(pattern, link_text, re.IGNORECASE)
                if price_match:
                    price_text = price_match.group(0)
                    # Extract just the $XX.XX part
                    dollar_match = re.search(r'\$[\d,]+\.?\d*', price_text)
                    if dollar_match:
                        logger.debug(f"Price found via link text pattern: {dollar_match.group(0)}")
                        return (dollar_match.group(0), 'USD')
                    # If no $ sign, add it
                    num_match = re.search(r'[\d,]+\.?\d*', price_text)
                    if num_match:
                        price_val = f"${num_match.group(0)}"
                        logger.debug(f"Price found via link text (no $): {price_val}")
                        return (price_val, 'USD')
        
        # Method 7: Extract from found element
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            
            # Extract price value (remove any extra text)
            price_match = re.search(r'\$[\d,]+\.?\d*', price_text)
            if price_match:
                price_value = price_match.group(0)
                logger.debug(f"Price found via element text: {price_value} (methods: {', '.join(extraction_methods)})")
                return (price_value, 'USD')
            
            # If no $ sign but has numbers, assume USD
            num_match = re.search(r'[\d,]+\.?\d*', price_text)
            if num_match:
                price_val = f"${num_match.group(0)}"
                logger.debug(f"Price found via element numbers: {price_val}")
                return (price_val, 'USD')
        
        # Method 8: Search all text in link and its children (last resort)
        all_text = link.get_text(separator=' ', strip=True)
        price_match = re.search(r'\$[\d,]+\.?\d{2}', all_text)
        if price_match:
            logger.debug(f"Price found via full text search: {price_match.group(0)}")
            return (price_match.group(0), 'USD')
        
        # Method 9: Look for JSON-LD structured data
        json_ld = link.find('script', type='application/ld+json')
        if json_ld:
            try:
                import json
                data = json.loads(json_ld.string)
                if isinstance(data, dict):
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        price = offers.get('price')
                        if price:
                            price_str = f"${price}" if not str(price).startswith('$') else str(price)
                            logger.debug(f"Price found via JSON-LD: {price_str}")
                            return (price_str, 'USD')
            except (json.JSONDecodeError, AttributeError):
                pass
        
        logger.debug("No price found in link element after trying all methods")
        
    except Exception as e:
        logger.warning(f"Price extraction error: {e}", exc_info=True)
    
    return ("", "USD")

async def _fetch_upc_and_price_from_product_page(product_url: str) -> Tuple[str, str]:
    """Fetch both UPC and price from product detail page in one API call
    
    Args:
        product_url: Full URL to the product page
        
    Returns:
        Tuple of (upc_string, price_string) - both may be empty if not found
    """
    try:
        logger.debug(f"Fetching UPC and price from product page: {product_url}")
        rate_limiter = get_rate_limiter()
        limits = DEFAULT_RATE_LIMITS.get("product_detail", {"rate": 2.0, "capacity": 5.0})
        await rate_limiter.limit("product_detail", **limits)
        
        payload = {
            "source": "target",
            "url": product_url,
            "render": "html",
            "geo_location": Config.DEFAULT_GEO_LOCATION,
            "user_agent_type": Config.DEFAULT_USER_AGENT_TYPE
        }
        
        async def fetch_product_detail():
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(45.0, connect=10.0),
                http2=False
            ) as client:
                response = await client.post(
                    Config.API_BASE_URL,
                    auth=(Config.OXYLABS_USERNAME, Config.OXYLABS_PASSWORD),
                    json=payload,
                    headers=Config.get_headers()
                )
                return response
        
        try:
            response = await retry_with_backoff(
                fetch_product_detail,
                max_retries=2,
                initial_delay=1.0,
                max_delay=10.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('results') or not data['results']:
                logger.warning(f"No results returned from API for product page: {product_url}")
                return ("", "")
            
            html_content = data['results'][0]['content']
            if not html_content or len(html_content) < 100:
                logger.warning(f"Received empty or very short HTML content for: {product_url}")
                return ("", "")
            
            logger.debug(f"Successfully fetched HTML content ({len(html_content)} chars) for: {product_url}")
            
            # Extract both UPC and price from the same HTML
            upc = await _extract_upc_from_html(html_content)
            price = await _fetch_price_from_product_page(html_content)
            
            if upc:
                logger.info(f"Successfully extracted UPC '{upc}' from: {product_url}")
            else:
                logger.debug(f"UPC not found for: {product_url}")
            
            if price:
                logger.info(f"Successfully extracted price '{price}' from product page: {product_url}")
            else:
                logger.debug(f"Price not found in product page for: {product_url}")
            
            return (upc, price)
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout fetching product detail page: {product_url} - {e}")
            return ("", "")
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} fetching product detail: {product_url} - {e}")
            return ("", "")
        except httpx.NetworkError as e:
            logger.warning(f"Network error fetching product detail: {product_url} - {e}")
            return ("", "")
        except Exception as e:
            logger.warning(f"Error fetching product detail for {product_url}: {e}", exc_info=True)
            return ("", "")
    except Exception as e:
        logger.error(f"Unexpected error in _fetch_upc_and_price_from_product_page for {product_url}: {e}", exc_info=True)
        return ("", "")

async def _extract_upc_from_html(html_content: str) -> str:
    """Extract UPC from HTML content with comprehensive methods
    
    Args:
        html_content: HTML content of product detail page
        
    Returns:
        UPC string or empty string if not found
    """
    extraction_methods = []
    try:
        if not html_content or len(html_content) < 100:
            logger.debug("HTML content too short for UPC extraction")
            return ""
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Method 1: Find Specifications section
        spec_sections = soup.find_all(['div', 'section', 'dl'], class_=re.compile(r'spec|detail|info|Specification'))
        
        for section in spec_sections:
            text = section.get_text()
            # Look for UPC: pattern (with or without colon)
            upc_match = re.search(r'UPC[:\s]+(\d{8,14})', text, re.IGNORECASE)
            if upc_match:
                upc = upc_match.group(1)
                # Validate UPC length (typically 12 digits)
                if 8 <= len(upc) <= 14:
                    logger.debug(f"UPC found via specifications section: {upc}")
                    return upc
        
        # Method 2: Look for dt/dd pattern (definition list)
        dt_elements = soup.find_all('dt')
        for dt in dt_elements:
            dt_text = dt.get_text().upper()
            if 'UPC' in dt_text or 'UNIVERSAL PRODUCT CODE' in dt_text:
                dd = dt.find_next_sibling('dd')
                if dd:
                    upc_text = dd.get_text(strip=True)
                    upc_match = re.search(r'(\d{8,14})', upc_text)
                    if upc_match:
                        upc = upc_match.group(1)
                        if 8 <= len(upc) <= 14:
                            logger.debug(f"UPC found via dt/dd pattern: {upc}")
                            return upc
        
        # Method 3: Look for meta tags
        meta_tags = soup.find_all('meta', attrs={'property': re.compile(r'product|upc', re.I)})
        for meta in meta_tags:
            content = meta.get('content', '')
            if content:
                upc_match = re.search(r'(\d{8,14})', content)
                if upc_match:
                    upc = upc_match.group(1)
                    if 8 <= len(upc) <= 14:
                        logger.debug(f"UPC found via meta tag: {upc}")
                        return upc
        
        # Method 4: Look for JSON-LD structured data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Check for UPC in various possible locations
                    upc = data.get('gtin') or data.get('gtin12') or data.get('gtin13') or data.get('upc')
                    if upc:
                        upc_str = str(upc).strip()
                        if upc_str.isdigit() and 8 <= len(upc_str) <= 14:
                            logger.debug(f"UPC found via JSON-LD: {upc_str}")
                            return upc_str
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue
        
        # Method 5: Search entire page text for UPC pattern
        page_text = soup.get_text()
        # Look for UPC: followed by 8-14 digits
        upc_patterns = [
            r'UPC[:\s]+(\d{8,14})',
            r'Universal\s+Product\s+Code[:\s]+(\d{8,14})',
            r'GTIN[:\s]+(\d{8,14})',
        ]
        for pattern in upc_patterns:
            upc_match = re.search(pattern, page_text, re.IGNORECASE)
            if upc_match:
                upc = upc_match.group(1)
                if 8 <= len(upc) <= 14:
                    logger.debug(f"UPC found via page text search ({pattern}): {upc}")
                    return upc
        
        # Method 6: Look for data attributes
        elements_with_data = soup.find_all(attrs={'data-upc': True})
        for elem in elements_with_data:
            upc = elem.get('data-upc', '').strip()
            if upc.isdigit() and 8 <= len(upc) <= 14:
                logger.debug(f"UPC found via data-upc attribute: {upc}")
                return upc
        
        logger.debug("UPC not found after trying all extraction methods")
        return ""
    except Exception as e:
        logger.warning(f"UPC extraction from HTML error: {e}", exc_info=True)
        return ""

async def _fetch_price_from_product_page_url(product_url: str) -> str:
    """Fetch price from product detail page by URL
    
    Args:
        product_url: Full URL to the product page
        
    Returns:
        Price string or empty string if not found
    """
    try:
        # Use the same approach as UPC fetching - reuse the HTML if we already fetched it
        # For now, make a separate request (could be optimized later)
        rate_limiter = get_rate_limiter()
        limits = DEFAULT_RATE_LIMITS.get("product_detail", {"rate": 2.0, "capacity": 5.0})
        await rate_limiter.limit("product_detail", **limits)
        
        payload = {
            "source": "target",
            "url": product_url,
            "render": "html",
            "geo_location": Config.DEFAULT_GEO_LOCATION,
            "user_agent_type": Config.DEFAULT_USER_AGENT_TYPE
        }
        
        async def fetch_product_detail():
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                http2=False
            ) as client:
                return await client.post(
                    Config.API_BASE_URL,
                    auth=(Config.OXYLABS_USERNAME, Config.OXYLABS_PASSWORD),
                    json=payload,
                    headers=Config.get_headers()
                )
        
        try:
            response = await retry_with_backoff(
                fetch_product_detail,
                max_retries=1,
                initial_delay=1.0,
                max_delay=5.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('results') or not data['results']:
                return ""
            
            html_content = data['results'][0]['content']
            return await _fetch_price_from_product_page(html_content)
        except Exception as e:
            logger.debug(f"Could not fetch price from product page for {product_url}: {e}")
            return ""
    except Exception as e:
        logger.debug(f"Price fetch from product page URL error: {e}")
        return ""

async def _fetch_price_from_product_page(html_content: str) -> str:
    """Extract price from product detail page HTML
    
    Args:
        html_content: HTML content of product detail page
        
    Returns:
        Price string or empty string if not found
    """
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Method 1: Look for data-test="product-price" or similar
        price_elem = soup.find(attrs={'data-test': re.compile(r'product.*price|price|current.*price')})
        
        # Method 2: Look for price in data attributes
        if not price_elem:
            for attr in ['data-price', 'data-current-price', 'data-base-price']:
                price_elem = soup.find(attrs={attr: re.compile(r'[\d,]+\.?\d*')})
                if price_elem:
                    price_val = price_elem.get(attr)
                    if price_val:
                        price_match = re.search(r'\$?[\d,]+\.?\d*', str(price_val))
                        if price_match:
                            price_str = price_match.group(0)
                            if not price_str.startswith('$'):
                                price_str = f"${price_str}"
                            return price_str
                    break
        
        # Method 3: Look for price in common Target price selectors
        if not price_elem:
            price_selectors = [
                '[data-test*="price"]',
                '[class*="price"]',
                '[class*="Price"]',
                '[id*="price"]',
            ]
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    break
        
        # Method 4: Search for price pattern in text
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'\$[\d,]+\.?\d*', price_text)
            if price_match:
                return price_match.group(0)
        
        # Method 5: Search entire page for price pattern
        page_text = soup.get_text()
        price_match = re.search(r'\$[\d,]+\.?\d{2}', page_text)
        if price_match:
            return price_match.group(0)
        
        return ""
    except Exception as e:
        logger.debug(f"Price extraction from product page error: {e}")
        return ""

async def _fetch_upc_from_product_page(product_url: str) -> str:
    """Fetch UPC from product detail page Specifications section
    
    Args:
        product_url: Full URL to the product page
        
    Returns:
        UPC string or empty string if not found
    """
    try:
        # Rate limiting for product detail requests
        rate_limiter = get_rate_limiter()
        limits = DEFAULT_RATE_LIMITS.get("product_detail", {"rate": 2.0, "capacity": 5.0})
        await rate_limiter.limit("product_detail", **limits)
        
        # Make API request to get product detail page
        # Note: For Oxylabs, use 'target' source with full URL
        payload = {
            "source": "target",
            "url": product_url,
            "render": "html",
            "geo_location": Config.DEFAULT_GEO_LOCATION,
            "user_agent_type": Config.DEFAULT_USER_AGENT_TYPE
        }
        
        # Use retry logic for product detail fetch with shorter timeout
        # UPC is optional, so we use a shorter timeout to avoid blocking
        async def fetch_product_detail():
            # Create a client with shorter timeout for UPC requests
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),  # 30s total, 5s connect
                http2=False
            ) as upc_client:
                return await upc_client.post(
                    Config.API_BASE_URL,
                    auth=(Config.OXYLABS_USERNAME, Config.OXYLABS_PASSWORD),
                    json=payload,
                    headers=Config.get_headers()
                )
        
        try:
            response = await retry_with_backoff(
                fetch_product_detail,
                max_retries=1,  # Only 1 retry for UPC (optional data)
                initial_delay=1.0,
                max_delay=5.0  # Shorter max delay
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('results') or not data['results']:
                return ""
            
            html_content = data['results'][0]['content']
        except (httpx.TimeoutException, httpx.NetworkError, ConnectionError) as e:
            # Network/timeout errors - UPC is optional, just skip
            logger.debug(f"Network error fetching UPC for {product_url}: {e}")
            return ""
        except Exception as e:
            # Any other error - UPC is optional, just skip
            logger.debug(f"Could not fetch UPC for {product_url}: {e}")
            return ""
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Find Specifications section
        # Target typically has UPC in a specifications section
        # Look for "UPC" text followed by the value
        spec_sections = soup.find_all(['div', 'section', 'dl'], class_=re.compile(r'spec|detail|info'))
        
        for section in spec_sections:
            text = section.get_text()
            # Look for "UPC:" pattern
            upc_match = re.search(r'UPC[:\s]+(\d+)', text, re.IGNORECASE)
            if upc_match:
                return upc_match.group(1)
        
        # Alternative: Look for dt/dd pattern (definition list)
        dt_elements = soup.find_all('dt')
        for dt in dt_elements:
            if 'UPC' in dt.get_text().upper():
                dd = dt.find_next_sibling('dd')
                if dd:
                    upc_text = dd.get_text(strip=True)
                    upc_match = re.search(r'(\d+)', upc_text)
                    if upc_match:
                        return upc_match.group(1)
        
        # Alternative: Search entire page for UPC pattern
        page_text = soup.get_text()
        upc_match = re.search(r'UPC[:\s]+(\d{11,13})', page_text, re.IGNORECASE)
        if upc_match:
            return upc_match.group(1)
        
        return ""
    except Exception as e:
        logger.debug(f"UPC fetch error for {product_url}: {e}")
        return ""

def _extract_image_from_link(link) -> str:
    """Extract image URL from link element"""
    try:
        img = link.find('img')
        if img:
            # Try src first
            if img.get('src'):
                return img.get('src')
            # Try data-src (lazy loading)
            if img.get('data-src'):
                return img.get('data-src')
            # Try srcset
            if img.get('srcset'):
                srcset = img.get('srcset')
                # Extract first URL from srcset
                src_match = re.search(r'([^\s,]+)', srcset)
                if src_match:
                    return src_match.group(1)
    except Exception:
        pass
    return ""

def _generate_filename(search_keyword: str) -> str:
    """Generate clean filename for search results (CSV)"""
    # Clean the keyword for filename
    clean_keyword = re.sub(r'[^\w\s-]', '', search_keyword)
    clean_keyword = re.sub(r'[-\s]+', '_', clean_keyword)
    clean_keyword = clean_keyword.strip('_').lower()
    
    # Ensure output directory exists
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    
    return os.path.join(Config.OUTPUT_DIR, f"{clean_keyword}_PRODUCTS.csv")

def _generate_json_filename(search_keyword: str) -> str:
    """Generate clean filename for search results (JSON)"""
    # Clean the keyword for filename
    clean_keyword = re.sub(r'[^\w\s-]', '', search_keyword)
    clean_keyword = re.sub(r'[-\s]+', '_', clean_keyword)
    clean_keyword = clean_keyword.strip('_').lower()
    
    # Ensure output directory exists
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
    
    return os.path.join(Config.OUTPUT_DIR, f"{clean_keyword}_PRODUCTS.json")

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
        async with aiofiles.open(filename, 'w', encoding='utf-8', newline='') as f:
            await f.write(csv_content)
        
        logger.info(f"Successfully saved products to {filename}")
    except Exception as e:
        logger.error(f"Error saving products to {filename}: {e}")
        raise

async def save_products_json_async(products: List[Dict[str, str]], filename: str) -> None:
    """
    Async save products to JSON file using aiofiles
    Ensures field order matches CSV format exactly
    
    Args:
        products: List of product dictionaries
        filename: Output filename
    """
    logger.info(f"Saving {len(products)} products to {filename}")
    
    try:
        import aiofiles
        import json
        from collections import OrderedDict
        
        # Ensure field order matches CSV_FIELDNAMES exactly
        ordered_products = []
        for product in products:
            ordered_product = OrderedDict()
            # Add fields in the exact order of CSV_FIELDNAMES
            for field in Config.CSV_FIELDNAMES:
                ordered_product[field] = product.get(field, '')
            ordered_products.append(ordered_product)
        
        # Prepare JSON content with proper field order
        json_content = json.dumps(ordered_products, indent=2, ensure_ascii=False)
        
        # Write asynchronously
        async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
            await f.write(json_content)
        
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

