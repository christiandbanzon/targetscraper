#!/usr/bin/env python3
"""
Oxylabs with Fixed Timeout - Proper 60+ second timeouts
"""

import requests
import re
import csv
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OxylabsFixedTimeout:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.api_url = "https://realtime.oxylabs.io/v1/queries"
        self.products = []
    
    def extract_product_with_timeout(self, tcin: str, category: str) -> dict:
        """Extract product with proper 60 second timeout"""
        product_url = f"https://www.target.com/p/-/A-{tcin}"
        
        payload = {
            'source': 'target',
            'url': product_url,
            'render': 'html'
        }
        
        logger.info(f"Processing TCIN {tcin} (60s timeout)...")
        start_time = time.time()
        
        try:
            response = requests.post(
                self.api_url,
                auth=(self.username, self.password),
                json=payload,
                timeout=60  # 60 second timeout
            )
            
            duration = time.time() - start_time
            logger.info(f"API call completed in {duration:.2f} seconds")
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    content = results[0].get('content', '')
                    if isinstance(content, str):
                        return self.parse_product_html(content, tcin, product_url, category)
            
            return None
            
        except requests.exceptions.Timeout:
            duration = time.time() - start_time
            logger.warning(f"TIMEOUT after {duration:.2f} seconds for TCIN {tcin}")
            return None
        except Exception as e:
            duration = time.time() - start_time
            logger.warning(f"Error after {duration:.2f} seconds for TCIN {tcin}: {e}")
            return None
    
    def parse_product_html(self, html: str, tcin: str, url: str, category: str) -> dict:
        """Parse product information from HTML"""
        try:
            # Extract title
            title_patterns = [
                r'<h1[^>]*data-testid="product-title"[^>]*>(.*?)</h1>',
                r'<h1[^>]*>(.*?)</h1>',
                r'<title>(.*?)</title>'
            ]
            
            title = "Unknown Product"
            for pattern in title_patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    title = match.group(1).strip()
                    title = re.sub(r'<[^>]+>', '', title)
                    title = re.sub(r'&amp;', '&', title)
                    title = re.sub(r'\s+', ' ', title).strip()
                    if title and title != "Unknown Product":
                        break
            
            # Extract price
            price_match = re.search(r'\$[\d,]+\.?\d*', html)
            price = price_match.group(0) if price_match else "Price not found"
            
            # Extract image
            img_match = re.search(r'<img[^>]*data-testid="product-image"[^>]*src="([^"]*)"', html)
            image_url = img_match.group(1) if img_match else ""
            
            # Determine brand
            title_lower = title.lower()
            brand = "Other"
            
            if 'learning resources' in title_lower or 'learning' in title_lower:
                brand = "Learning Resources"
            elif 'lavazza' in title_lower:
                brand = "Lavazza"
            elif 'life extension' in title_lower or 'life extensions' in title_lower:
                brand = "Life Extensions"
            
            return {
                'tcin': tcin,
                'url': url,
                'category': category,
                'brand': brand,
                'title': title,
                'price': price,
                'image_url': image_url,
                'marketplace': 'Target',
                'currency': 'USD'
            }
            
        except Exception as e:
            logger.debug(f"Error parsing HTML for TCIN {tcin}: {e}")
            return None
    
    def process_limited_products(self, max_products: int = 5):
        """Process limited number of products with proper timeouts"""
        logger.info(f"🚀 Processing {max_products} products with 60s timeouts")
        logger.info("=" * 60)
        
        # Read TCINs from CSV
        tcins = []
        try:
            with open('oxylabs_simple_products.csv', 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= max_products:
                        break
                    tcins.append({
                        'tcin': row['tcin'],
                        'category': row['category']
                    })
        except FileNotFoundError:
            logger.error("CSV file not found")
            return []
        
        results = []
        target_brand_count = 0
        
        for i, item in enumerate(tcins):
            logger.info(f"\n📦 {i+1}/{len(tcins)}: TCIN {item['tcin']} ({item['category']})")
            
            product = self.extract_product_with_timeout(item['tcin'], item['category'])
            
            if product:
                results.append(product)
                if product['brand'] != "Other":
                    target_brand_count += 1
                    logger.info(f"  ✅ TARGET BRAND: {product['brand']} - {product['title'][:60]}... - {product['price']}")
                else:
                    logger.info(f"  ℹ️  Other: {product['title'][:60]}... - {product['price']}")
            else:
                logger.warning(f"  ❌ Failed to extract details")
            
            # Small delay between requests
            time.sleep(1)
        
        self.products = results
        
        logger.info(f"\n🎉 PROCESSING COMPLETE!")
        logger.info("=" * 60)
        logger.info(f"Total products processed: {len(results)}")
        logger.info(f"Target brand products: {target_brand_count}")
        
        return results
    
    def save_results(self, filename: str = "oxylabs_fixed_results.csv"):
        """Save results to CSV"""
        if not self.products:
            logger.warning("No products to save")
            return
        
        fieldnames = ['tcin', 'url', 'category', 'brand', 'title', 'price', 'image_url', 'marketplace', 'currency']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products)
        
        logger.info(f"📁 Results saved to: {filename}")

def main():
    USERNAME = "tereo_gmDZq"
    PASSWORD = "7xiek=6GMk4BgLY"
    
    extractor = OxylabsFixedTimeout(USERNAME, PASSWORD)
    
    try:
        # Process just 3 products to test
        products = extractor.process_limited_products(max_products=3)
        
        if products:
            extractor.save_results()
            logger.info("\n✅ FIXED TIMEOUT VERSION COMPLETE!")
        else:
            logger.warning("No products processed")
    
    except Exception as e:
        logger.error(f"Processing failed: {e}")

if __name__ == "__main__":
    main()

