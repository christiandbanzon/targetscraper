#!/usr/bin/env python3
"""
Clean fresh scraper - one CSV per brand with clean data
"""

import requests
import csv
import re
from bs4 import BeautifulSoup
from datetime import datetime

USERNAME = "tereo_gmDZq"
PASSWORD = "7xiek=6GMk4BgLY"

def clean_fresh_scraper():
    """Clean fresh scraper - one CSV per brand"""
    
    print("Clean Fresh Scraper - One CSV Per Brand")
    print("=" * 50)
    
    brands = [
        ("Learning Resources", "learning resources"),
        ("Lavazza", "lavazza"),
        ("Life Extensions", "life extension")
    ]
    
    for brand_name, search_term in brands:
        print(f"\nScraping {brand_name}...")
        
        try:
            # Search for brand
            payload = {
                "source": "target_search",
                "query": search_term,
                "geo_location": "United States",
                "render": "html",
                "user_agent_type": "desktop"
            }
            
            response = requests.post(
                "https://realtime.oxylabs.io/v1/queries",
                auth=(USERNAME, PASSWORD),
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                html_content = data['results'][0]['content']
                
                # Parse products
                products = parse_products(html_content, brand_name)
                
                # Clean and save
                clean_filename = f"outputs/{brand_name.replace(' ', '_')}_CLEAN.csv"
                save_clean_csv(products, clean_filename, brand_name)
                
                print(f"  SUCCESS: {len(products)} products saved to {clean_filename}")
            else:
                print(f"  FAILED: {response.status_code}")
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print(f"\nClean scraping completed!")

def parse_products(html_content, brand_name):
    """Parse products from HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    # Find product links
    if brand_name == "Life Extensions":
        # Special handling for Life Extensions
        links = soup.find_all('a', href=re.compile(r'life-extension', re.I))
    else:
        # For other brands, look for brand-specific links
        brand_pattern = brand_name.lower().replace(' ', '-')
        links = soup.find_all('a', href=re.compile(brand_pattern, re.I))
    
    seen_urls = set()
    
    for link in links:
        href = link.get('href', '')
        if href.startswith('/p/'):
            full_url = f"https://www.target.com{href}"
            
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Extract TCIN
            tcin_match = re.search(r'/A-(\d+)', href)
            tcin = tcin_match.group(1) if tcin_match else ""
            
            # Extract title
            title = link.get_text(strip=True)
            if not title:
                parent = link.find_parent(['h2', 'h3', 'h4', 'div'])
                if parent:
                    title = parent.get_text(strip=True)
            
            if not title:
                title = extract_title_from_url(href)
            
            # Extract price
            price = extract_price_from_link(link)
            
            # Extract image
            image_url = extract_image_from_link(link)
            
            # Clean URL (remove fragments)
            clean_url = full_url.split('#')[0].split('?')[0]
            
            product = {
                'listing_title': title,
                'listings_url': clean_url,
                'image_url': image_url,
                'marketplace': 'Target',
                'price': price,
                'currency': 'USD',
                'shipping': '',
                'units_available': '',
                'item_number': tcin,
                'tcin': tcin,
                'upc': '',
                'seller_name': 'Target',
                'seller_url': 'https://www.target.com',
                'seller_business': 'Target Corporation',
                'seller_address': '1000 Nicollet Mall, Minneapolis, MN 55403',
                'seller_email': '',
                'seller_phone': '1-800-440-0680'
            }
            
            products.append(product)
    
    return products

def extract_title_from_url(url):
    """Extract title from URL"""
    try:
        path = url.split('/p/')[-1].split('/-')[0]
        title = path.replace('-', ' ').replace('_', ' ').title()
        return title
    except:
        return "Product"

def extract_price_from_link(link):
    """Extract price from link"""
    try:
        price_elem = link.find(['span', 'div'], class_=re.compile(r'price|cost|amount'))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            if '$' in price_text:
                return price_text
    except:
        pass
    return ""

def extract_image_from_link(link):
    """Extract image from link"""
    try:
        img = link.find('img')
        if img and img.get('src'):
            return img.get('src')
    except:
        pass
    return ""

def save_clean_csv(products, filename, brand_name):
    """Save clean CSV"""
    fieldnames = [
        'listing_title', 'listings_url', 'image_url', 'marketplace', 'price', 'currency',
        'shipping', 'units_available', 'item_number', 'tcin', 'upc', 'seller_name',
        'seller_url', 'seller_business', 'seller_address', 'seller_email', 'seller_phone'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)

if __name__ == "__main__":
    clean_fresh_scraper()
