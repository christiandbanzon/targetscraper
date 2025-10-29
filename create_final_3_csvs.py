#!/usr/bin/env python3
"""
Create the final 3 CSV files for the 3 main brands
"""

import csv
import os
from datetime import datetime

def create_final_3_csvs():
    """Create final CSV files for the 3 main brands"""
    
    print("Creating Final 3 CSV Files")
    print("=" * 40)
    
    # Load the complete data
    complete_file = "target_all_brands_complete_20251029_122655.csv"
    
    if not os.path.exists(complete_file):
        print(f"Error: {complete_file} not found")
        return
    
    # Read all products
    all_products = []
    with open(complete_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_products = list(reader)
    
    print(f"Loaded {len(all_products)} total products")
    
    # Define the 3 main brands
    main_brands = {
        'Seville Classics': [],
        'Learning Resources': [],
        'Lavazza': []
    }
    
    # Categorize products
    for product in all_products:
        title = product.get('listing_title', '').lower()
        url = product.get('listings_url', '').lower()
        
        if 'seville classic' in title or 'seville classic' in url:
            main_brands['Seville Classics'].append(product)
        elif 'learning resource' in title or 'learning resource' in url:
            main_brands['Learning Resources'].append(product)
        elif 'lavazza' in title or 'lavazza' in url:
            main_brands['Lavazza'].append(product)
    
    # Create individual CSV files
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    for brand, products in main_brands.items():
        if products:
            filename = f"TARGET_{brand.upper().replace(' ', '_')}_FINAL_{timestamp}.csv"
            print(f"Creating {filename} with {len(products)} products")
            
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'listing_title', 'listings_url', 'image_url', 'marketplace', 'price', 'currency',
                    'shipping', 'units_available', 'item_number', 'tcin', 'upc', 'seller_name',
                    'seller_url', 'seller_business', 'seller_address', 'seller_email', 'seller_phone'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(products)
            
            print(f"  Saved: {filename}")
        else:
            print(f"No products found for {brand}")
    
    # Create summary
    print(f"\nFINAL SUMMARY:")
    print(f"=" * 40)
    for brand, products in main_brands.items():
        print(f"{brand}: {len(products)} products")
    
    total = sum(len(products) for products in main_brands.values())
    print(f"Total: {total} products")
    
    return main_brands

if __name__ == "__main__":
    create_final_3_csvs()
