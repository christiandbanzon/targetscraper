#!/usr/bin/env python3
"""
Oxylabs Brand Search - Direct search for specific brands
"""

import requests
import re
import csv
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OxylabsBrandSearch:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.api_url = "https://realtime.oxylabs.io/v1/queries"
        self.products = []
    
    def search_brand(self, brand_name: str) -> list:
        """Search for a specific brand using different search terms"""
        logger.info(f"🔍 Searching for: {brand_name}")
        
        # Try different search approaches
        search_terms = [
            brand_name,
            f'"{brand_name}"',  # Quoted search
            brand_name.replace(' ', '+'),  # URL encoded
        ]
        
        all_products = []
        
        for search_term in search_terms:
            logger.info(f"  Trying search term: {search_term}")
            
            # Try target_search source
            payload = {
                'source': 'target_search',
                'query': search_term,
                'parse': True,
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
                        content = results[0].get('content', {})
                        organic_results = content.get('results', {}).get('organic', [])
                        
                        logger.info(f"    Found {len(organic_results)} organic results")
                        
                        for result in organic_results:
                            if result.get('title') and brand_name.lower() in result.get('title', '').lower():
                                product = {
                                    'tcin': self.extract_tcin(result.get('url', '')),
                                    'url': result.get('url', ''),
                                    'title': result.get('title', ''),
                                    'price': result.get('price', ''),
                                    'brand': brand_name,
                                    'category': 'Search Result'
                                }
                                all_products.append(product)
                                logger.info(f"    ✅ Found: {result.get('title', '')[:50]}...")
                    else:
                        logger.warning(f"    No results for {search_term}")
                else:
                    logger.warning(f"    API failed for {search_term}: {response.status_code}")
                
                # Small delay between searches
                time.sleep(2)
                
            except Exception as e:
                logger.warning(f"    Error searching {search_term}: {e}")
                continue
        
        logger.info(f"✅ {brand_name}: Found {len(all_products)} products")
        return all_products
    
    def extract_tcin(self, url: str) -> str:
        """Extract TCIN from URL"""
        if "/-/A-" in url:
            try:
                return url.split("/-/A-")[1].split("/")[0]
            except:
                pass
        return ""
    
    def search_all_brands(self):
        """Search for all target brands"""
        logger.info("🚀 Starting Brand-Specific Search")
        logger.info("=" * 50)
        
        brands = ["Learning Resources", "Lavazza", "Life Extensions"]
        all_products = []
        
        for brand in brands:
            logger.info(f"\n🔍 Searching: {brand}")
            logger.info("-" * 30)
            
            products = self.search_brand(brand)
            all_products.extend(products)
            
            # Delay between brands
            if brand != brands[-1]:
                time.sleep(3)
        
        self.products = all_products
        logger.info(f"\n🎉 TOTAL PRODUCTS FOUND: {len(all_products)}")
        
        # Count by brand
        for brand in brands:
            count = len([p for p in all_products if p['brand'] == brand])
            logger.info(f"  {brand}: {count} products")
        
        return all_products
    
    def save_to_csv(self, filename: str = "oxylabs_brand_search_results.csv"):
        """Save results to CSV"""
        if not self.products:
            logger.warning("No products to save")
            return
        
        fieldnames = ['tcin', 'url', 'title', 'price', 'brand', 'category']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.products)
        
        logger.info(f"📁 Results saved to: {filename}")

def main():
    USERNAME = "tereo_gmDZq"
    PASSWORD = "7xiek=6GMk4BgLY"
    
    searcher = OxylabsBrandSearch(USERNAME, PASSWORD)
    
    try:
        products = searcher.search_all_brands()
        
        if products:
            searcher.save_to_csv()
            logger.info("\n✅ BRAND SEARCH COMPLETE!")
        else:
            logger.warning("No products found")
    
    except Exception as e:
        logger.error(f"Search failed: {e}")

if __name__ == "__main__":
    main()

