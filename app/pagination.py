#!/usr/bin/env python3
"""
Pagination utilities for scraping multiple pages
"""

import re
import logging
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class PaginationHelper:
    """Helper for detecting and handling pagination"""
    
    @staticmethod
    def find_next_page_url(html_content: str, base_url: str = "https://www.target.com") -> Optional[str]:
        """
        Find the next page URL from HTML content
        
        Args:
            html_content: HTML content to parse
            base_url: Base URL for relative links
            
        Returns:
            Next page URL or None if no next page
        """
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Common pagination patterns
        pagination_selectors = [
            ('a', {'aria-label': re.compile(r'next', re.I)}),
            ('a', {'class': re.compile(r'next', re.I)}),
            ('a', {'aria-label': re.compile(r'page\s*\d+', re.I)}),
            ('a', {'data-test': re.compile(r'next', re.I)}),
        ]
        
        for tag, attrs in pagination_selectors:
            links = soup.find_all(tag, attrs)
            for link in links:
                href = link.get('href', '')
                text = link.get_text(strip=True).lower()
                
                # Check if this looks like a "next" link
                if any(keyword in text for keyword in ['next', '>', '→']):
                    if href:
                        if href.startswith('/'):
                            return f"{base_url}{href}"
                        elif href.startswith('http'):
                            return href
                        else:
                            return f"{base_url}/{href}"
        
        # Fallback: Look for pagination links with numbers
        pagination_links = soup.find_all('a', href=re.compile(r'page|p=\d+'))
        if pagination_links:
            # Find the highest page number
            max_page = 0
            next_url = None
            for link in pagination_links:
                href = link.get('href', '')
                page_match = re.search(r'page[=/-](\d+)|p[=/-](\d+)', href, re.I)
                if page_match:
                    page_num = int(page_match.group(1) or page_match.group(2))
                    if page_num > max_page:
                        max_page = page_num
                        if href.startswith('/'):
                            next_url = f"{base_url}{href}"
                        elif href.startswith('http'):
                            next_url = href
        
        return next_url
    
    @staticmethod
    def detect_page_number(html_content: str) -> Optional[int]:
        """Detect current page number from HTML"""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Look for pagination indicators
        pagination_text = soup.find_all(string=re.compile(r'page\s*\d+|page\s*of', re.I))
        for text in pagination_text:
            match = re.search(r'page\s*(\d+)', text, re.I)
            if match:
                return int(match.group(1))
        
        return None
    
    @staticmethod
    def has_more_pages(html_content: str) -> bool:
        """Check if there are more pages available"""
        next_url = PaginationHelper.find_next_page_url(html_content)
        return next_url is not None

