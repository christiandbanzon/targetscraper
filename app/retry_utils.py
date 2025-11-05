#!/usr/bin/env python3
"""
Retry utilities with exponential backoff
"""

import asyncio
import logging
from typing import Callable, TypeVar, Optional, List
from functools import wraps
import httpx
from .config import Config

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RetryableError(Exception):
    """Exception that should trigger a retry"""
    pass

class NonRetryableError(Exception):
    """Exception that should NOT trigger a retry"""
    pass

async def retry_with_backoff(
    func: Callable,
    max_retries: int = None,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = None,
    *args,
    **kwargs
) -> T:
    """
    Retry a function with exponential backoff
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retries (default from Config)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_exceptions: Tuple of exceptions that should trigger retry
        *args, **kwargs: Arguments to pass to func
        
    Returns:
        Result from function call
        
    Raises:
        Last exception if all retries fail
    """
    if max_retries is None:
        max_retries = Config.API_MAX_RETRIES
    
    if retryable_exceptions is None:
        retryable_exceptions = (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.HTTPStatusError,  # For 429, 500, 502, 503
            ConnectionError,
            asyncio.TimeoutError
        )
    
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            
            # If we got a response, check status code for retryable errors
            if isinstance(result, httpx.Response):
                status_code = result.status_code
                if status_code in (429, 500, 502, 503, 504):
                    if attempt < max_retries:
                        logger.warning(
                            f"Retryable HTTP {status_code} error (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                        continue
                    else:
                        result.raise_for_status()
            
            # Success - reset delay for next call
            if attempt > 0:
                logger.info(f"Successfully retried after {attempt} attempts")
            return result
            
        except retryable_exceptions as e:
            last_exception = e
            
            # Check if it's a retryable HTTP error
            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                # Don't retry 4xx errors except 429 (rate limit)
                if 400 <= status_code < 500 and status_code != 429:
                    logger.error(f"Non-retryable HTTP {status_code} error: {e}")
                    raise NonRetryableError(f"HTTP {status_code}: {e}") from e
            
            if attempt < max_retries:
                logger.warning(
                    f"Retryable error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * exponential_base, max_delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
                raise
                
        except Exception as e:
            # Non-retryable exception
            logger.error(f"Non-retryable error: {e}")
            raise NonRetryableError(f"Non-retryable: {e}") from e
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception

def retry_on_failure(
    max_retries: int = None,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0
):
    """
    Decorator for retrying async functions with exponential backoff
    
    Usage:
        @retry_on_failure(max_retries=3)
        async def my_function():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func,
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                *args,
                **kwargs
            )
        return wrapper
    return decorator

