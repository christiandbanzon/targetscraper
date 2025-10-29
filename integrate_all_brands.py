#!/usr/bin/env python3
"""
Integrate all brand data into comprehensive CSV outputs
"""

import csv
import json
from datetime import datetime
import os

def integrate_all_brands():
    """Combine all brand data into comprehensive outputs"""
    
    print("Starting Brand Data Integration")
    print("=" * 50)
    
    # Initialize data storage
    all_products = []
    brand_counts = {}
    
    # 1. Seville Classics (from existing data)
    seville_file = "target_seville_classics_final_complete.csv"
    if os.path.exists(seville_file):
        print(f"Loading Seville Classics from {seville_file}")
        with open(seville_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            seville_products = list(reader)
            all_products.extend(seville_products)
            brand_counts['Seville Classics'] = len(seville_products)
            print(f"  Found {len(seville_products)} Seville Classics products")
    
    # 2. Life Extensions (from existing data)
    life_ext_file = "target_life_extensions_products.csv"
    if os.path.exists(life_ext_file):
        print(f"Loading Life Extensions from {life_ext_file}")
        with open(life_ext_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            life_products = list(reader)
            all_products.extend(life_products)
            brand_counts['Life Extensions'] = len(life_products)
            print(f"  Found {len(life_products)} Life Extensions products")
    
    # 3. Lavazza (from brand search results)
    lavazza_file = "oxylabs_brand_search_results.csv"
    if os.path.exists(lavazza_file):
        print(f"Loading Lavazza from {lavazza_file}")
        with open(lavazza_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            lavazza_products = list(reader)
            
            # Convert to standard format
            for product in lavazza_products:
                if product.get('brand') == 'Lavazza':
                    standard_product = {
                        'listing_title': product.get('title', ''),
                        'listings_url': product.get('url', ''),
                        'image_url': product.get('image_url', ''),
                        'marketplace': 'Target',
                        'price': product.get('price', ''),
                        'currency': 'USD',
                        'shipping': '',
                        'units_available': '',
                        'item_number': product.get('tcin', ''),
                        'tcin': product.get('tcin', ''),
                        'upc': '',
                        'seller_name': 'Target',
                        'seller_url': 'https://www.target.com',
                        'seller_business': 'Target Corporation',
                        'seller_address': '1000 Nicollet Mall, Minneapolis, MN 55403',
                        'seller_email': '',
                        'seller_phone': '1-800-440-0680'
                    }
                    all_products.append(standard_product)
            
            brand_counts['Lavazza'] = len([p for p in lavazza_products if p.get('brand') == 'Lavazza'])
            print(f"  Found {brand_counts['Lavazza']} Lavazza products")
    
    # 4. Learning Resources (from existing data)
    learning_file = "target_learning_resources_products.csv"
    if os.path.exists(learning_file):
        print(f"Loading Learning Resources from {learning_file}")
        with open(learning_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            learning_products = list(reader)
            all_products.extend(learning_products)
            brand_counts['Learning Resources'] = len(learning_products)
            print(f"  Found {len(learning_products)} Learning Resources products")
    
    # 5. Alternative products (from direct URL approach)
    alt_file = "target_alternative_products.csv"
    if os.path.exists(alt_file):
        print(f"Loading Alternative products from {alt_file}")
        with open(alt_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            alt_products = list(reader)
            all_products.extend(alt_products)
            brand_counts['Alternative'] = len(alt_products)
            print(f"  Found {len(alt_products)} Alternative products")
    
    # Create comprehensive CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # All products combined
    all_products_file = f"target_all_brands_complete_{timestamp}.csv"
    print(f"\nSaving all products to {all_products_file}")
    
    with open(all_products_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'listing_title', 'listings_url', 'image_url', 'marketplace', 'price', 'currency',
            'shipping', 'units_available', 'item_number', 'tcin', 'upc', 'seller_name',
            'seller_url', 'seller_business', 'seller_address', 'seller_email', 'seller_phone'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_products)
    
    # Create individual brand CSVs
    for brand, count in brand_counts.items():
        if count > 0:
            brand_products = [p for p in all_products if brand.lower() in p.get('listing_title', '').lower() or 
                            brand.lower() in p.get('listings_url', '').lower()]
            
            if not brand_products and brand == 'Lavazza':
                # Special handling for Lavazza from search results
                brand_products = [p for p in all_products if 'lavazza' in p.get('listing_title', '').lower()]
            
            if brand_products:
                brand_file = f"target_{brand.lower().replace(' ', '_')}_final_{timestamp}.csv"
                print(f"Saving {brand} products to {brand_file}")
                
                with open(brand_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(brand_products)
    
    # Create summary report
    summary_file = f"target_brands_summary_{timestamp}.txt"
    print(f"Creating summary report: {summary_file}")
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("TARGET.COM BRAND EXTRACTION SUMMARY\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("BRAND BREAKDOWN:\n")
        f.write("-" * 20 + "\n")
        for brand, count in brand_counts.items():
            f.write(f"{brand}: {count} products\n")
        
        f.write(f"\nTOTAL PRODUCTS: {len(all_products)}\n")
        f.write(f"SUCCESSFUL BRANDS: {len([b for b, c in brand_counts.items() if c > 0])}\n")
        
        f.write("\nFILES GENERATED:\n")
        f.write("-" * 20 + "\n")
        f.write(f"All products: {all_products_file}\n")
        for brand, count in brand_counts.items():
            if count > 0:
                f.write(f"{brand}: target_{brand.lower().replace(' ', '_')}_final_{timestamp}.csv\n")
    
    # Print summary
    print(f"\nINTEGRATION COMPLETE!")
    print(f"=" * 50)
    print(f"Total products: {len(all_products)}")
    print(f"Brands with data: {len([b for b, c in brand_counts.items() if c > 0])}")
    print(f"\nBrand breakdown:")
    for brand, count in brand_counts.items():
        print(f"  {brand}: {count} products")
    
    print(f"\nFiles created:")
    print(f"  All products: {all_products_file}")
    print(f"  Summary: {summary_file}")
    
    return all_products, brand_counts

if __name__ == "__main__":
    integrate_all_brands()
