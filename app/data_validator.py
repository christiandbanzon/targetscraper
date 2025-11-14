#!/usr/bin/env python3
"""
Data validation and quality checks for scraped products
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DataValidator:
    """Validates and checks data quality"""
    
    # Required fields that must be present (using new format field names)
    REQUIRED_FIELDS = ['Listing Title*', 'Listings URL*', 'Item Number']
    
    # URL patterns for validation
    VALID_URL_PATTERN = re.compile(r'^https?://(www\.)?target\.com/.*')
    VALID_TCIN_PATTERN = re.compile(r'^\d{8,}$')  # TCINs are typically 8+ digits
    
    @classmethod
    def validate_product(cls, product: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a single product
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        for field in cls.REQUIRED_FIELDS:
            value = product.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append(f"Missing required field: {field}")
        
        # Validate URL
        url = product.get('Listings URL*', '')
        if url:
            if not cls.VALID_URL_PATTERN.match(url):
                errors.append(f"Invalid URL format: {url}")
        
        # Validate TCIN (now in Item Number column)
        tcin = product.get('Item Number', '')
        if tcin:
            if not cls.VALID_TCIN_PATTERN.match(str(tcin)):
                errors.append(f"Invalid TCIN format: {tcin}")
        
        # Validate title
        title = product.get('Listing Title*', '')
        if title:
            if len(title) < 3:
                errors.append(f"Title too short: {title}")
            if len(title) > 500:
                errors.append(f"Title too long: {title}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_products(cls, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a list of products
        
        Returns:
            dict with validation results
        """
        valid_products = []
        invalid_products = []
        all_errors = []
        
        for idx, product in enumerate(products):
            is_valid, errors = cls.validate_product(product)
            
            if is_valid:
                valid_products.append(product)
            else:
                invalid_products.append({
                    "index": idx,
                    "product": product,
                    "errors": errors
                })
                all_errors.extend(errors)
        
        return {
            "total": len(products),
            "valid": len(valid_products),
            "invalid": len(invalid_products),
            "valid_products": valid_products,
            "invalid_products": invalid_products,
            "errors": all_errors,
            "quality_score": len(valid_products) / len(products) if products else 0.0
        }
    
    @classmethod
    def remove_duplicates(cls, products: List[Dict[str, Any]], key: str = 'Item Number') -> List[Dict[str, Any]]:
        """
        Remove duplicate products based on a key field
        
        Args:
            products: List of products
            key: Field to use for deduplication (default: 'Item Number' which contains TCIN)
            
        Returns:
            List of unique products
        """
        seen = set()
        unique_products = []
        
        for product in products:
            identifier = product.get(key, '')
            
            # Use URL as fallback if Item Number (TCIN) not available
            if not identifier:
                identifier = product.get('Listings URL*', '')
            
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique_products.append(product)
            elif not identifier:
                # If no identifier, still include but log warning
                logger.warning(f"Product without {key} or URL: {product.get('Listing Title*', 'Unknown')}")
                unique_products.append(product)
        
        removed_count = len(products) - len(unique_products)
        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate products")
        
        return unique_products
    
    @classmethod
    def quality_score(cls, products: List[Dict[str, Any]]) -> float:
        """
        Calculate overall data quality score
        
        Returns:
            Score between 0.0 and 1.0
        """
        if not products:
            return 0.0
        
        validation_result = cls.validate_products(products)
        base_score = validation_result["quality_score"]
        
        # Check completeness (how many fields are filled)
        completeness_scores = []
        for product in validation_result["valid_products"]:
            filled_fields = sum(1 for v in product.values() if v and str(v).strip())
            total_fields = len(product)
            completeness_scores.append(filled_fields / total_fields if total_fields > 0 else 0)
        
        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0
        
        # Combined score (70% validation, 30% completeness)
        final_score = (base_score * 0.7) + (avg_completeness * 0.3)
        
        return round(final_score, 3)

