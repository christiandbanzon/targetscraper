#!/usr/bin/env python3
"""
Rate limiting utilities using token bucket algorithm
"""

import asyncio
import time
import logging
from typing import Optional
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TokenBucket:
    """
    Token bucket rate limiter
    
    Parameters:
        rate: Tokens per second
        capacity: Maximum tokens in bucket
    """
    
    def __init__(self, rate: float, capacity: float):
        self.rate = rate  # Tokens per second
        self.capacity = capacity  # Maximum tokens
        self.tokens = capacity  # Current tokens
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: float = 1.0) -> bool:
        """
        Acquire tokens from bucket
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False otherwise
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # Add tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    async def wait(self, tokens: float = 1.0) -> None:
        """
        Wait until tokens are available
        
        Args:
            tokens: Number of tokens needed
        """
        while not await self.acquire(tokens):
            # Calculate wait time
            async with self._lock:
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now
                
                if self.tokens < tokens:
                    needed = tokens - self.tokens
                    wait_time = needed / self.rate
                    await asyncio.sleep(wait_time)

class RateLimiter:
    """
    Per-endpoint rate limiter using token bucket
    """
    
    def __init__(self):
        self.buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
    
    def get_bucket(self, endpoint: str, rate: float, capacity: float) -> TokenBucket:
        """Get or create a token bucket for an endpoint"""
        if endpoint not in self.buckets:
            self.buckets[endpoint] = TokenBucket(rate, capacity)
        return self.buckets[endpoint]
    
    async def limit(self, endpoint: str, rate: float = 10.0, capacity: float = 20.0, tokens: float = 1.0):
        """
        Rate limit an endpoint
        
        Args:
            endpoint: Endpoint identifier
            rate: Tokens per second
            capacity: Maximum tokens
            tokens: Number of tokens to consume
        """
        async with self._lock:
            bucket = self.get_bucket(endpoint, rate, capacity)
        
        await bucket.wait(tokens)
        logger.debug(f"Rate limit passed for {endpoint}")

# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

# Default rate limits
DEFAULT_RATE_LIMITS = {
    "api_request": {"rate": 5.0, "capacity": 10.0},  # 5 requests/sec, burst of 10
    "keyword_search": {"rate": 2.0, "capacity": 5.0},  # 2 searches/sec, burst of 5
    "batch_search": {"rate": 1.0, "capacity": 3.0},  # 1 batch/sec, burst of 3
}

