#!/usr/bin/env python3
"""
Simple Oxylabs Target Scraper - Quick and reliable
"""

import requests
import re
import csv
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleOxylabsScraper:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.api_url = "https://realtime.oxylabs.io/v1/queries"
        self.products = []
    
    def get_category_products(self, category_name: str, url: str) -> list:
        """Get product URLs from a category page"""
        logger.info(f"🔍 Getting {category_name} products...")
        
        payload = {
            'source': 'target',
            'url': url,
            'render': 'html'
        }
        
        try:
            response = requests.post(
                self.api_url,
                auth=(self.username, self.password),
                json=payload,
                timeout=45
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    content = results[0].get('content', '')
                    if isinstance(content, str):
                        # Find all product URLs with TCINs
                        product_urls = re.findall(r'https://www\.target\.com/p/[^"]*/-/A-(\d+)', content)
                        unique_tcins = list(set(product_urls))
                        
                        logger.info(f"✅ Found {len(unique_tcins)} unique products")
                        
                        # Create product entries
                        products = []
                        for tcin in unique_tcins[:20]:  # Limit to 20 for speed
                            product_url = f"https://www.target.com/p/-/A-{tcin}"
                            products.append({
                                'tcin': tcin,
                                'url': product_url,
                                'category': category_name,
                                'brand': 'Unknown',
                                'title': 'To be extracted',
                                'price': 'To be extracted'
                            })
                        
                        return products
                    else:
                        logger.warning("No HTML content received")
                        return []
                else:
                    logger.warning("No results in response")
                    return []
            else:
                logger.error(f"API request failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting {category_name} products: {e}")
            return []
    
    def run_quick_scrape(self):
        """Run quick scraping for all categories"""
        logger.info("🚀 Starting Simple Oxylabs Target Scraping")
        logger.info("=" * 50)
        
        categories = {
            "Educational Toys": "https://www.target.com/c/educational-toys/-/N-5xt5b",
            "Coffee": "https://www.target.com/c/coffee/-/N-5xszk", 
            "Vitamins": "https://www.target.com/c/vitamins-supplements/-/N-5xu1n"
        }
        
        all_products = []
        
        for category_name, url in categories.items():
            logger.info(f"\n📂 Processing: {category_name}")
            products = self.get_category_products(category_name, url)
            all_products.extend(products)
            
            # Small delay between requests
            time.sleep(2)
        
        self.products = all_products
        logger.info(f"\n🎉 TOTAL PRODUCTS FOUND: {len(all_products)}")
        
        # Count by category
        for category_name in categories.keys():
            count = len([p for p in all_products if p['category'] == category_name])
            logger.info(f"  {category_name}: {count} products")
        
        return all_products
    
    def save_to_csv(self, filename: str = "oxylabs_simple_products.csv"):
        """Save products to CSV"""
        if not self.products:
            logger.warning("No products to save")
            return
        
        fieldnames = ['tcin', 'url', 'category', 'brand', 'title', 'price']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products)
        
        logger.info(f"📁 Results saved to: {filename}")

def main():
    USERNAME = "tereo_gmDZq"
    PASSWORD = "7xiek=6GMk4BgLY"
    
    scraper = SimpleOxylabsScraper(USERNAME, PASSWORD)
    
    try:
        products = scraper.run_quick_scrape()
        
        if products:
            scraper.save_to_csv()
            logger.info("\n✅ SIMPLE OXYLABS SCRAPING COMPLETE!")
        else:
            logger.warning("No products found")
    
    except Exception as e:
        logger.error(f"Scraping failed: {e}")

if __name__ == "__main__":
    main()

