#!/usr/bin/env python3
"""
Error recovery and dead letter queue for failed jobs
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"

@dataclass
class FailedJob:
    """Represents a failed job in the dead letter queue"""
    job_id: str
    keyword: str
    error: str
    attempt_count: int
    last_attempt: datetime
    created_at: datetime
    next_retry_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = asdict(self)
        # Convert datetime to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FailedJob':
        """Create from dictionary"""
        # Convert ISO strings to datetime
        for key, value in data.items():
            if isinstance(value, str) and ('at' in key or 'created' in key):
                try:
                    data[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
        return cls(**data)

class DeadLetterQueue:
    """Dead letter queue for failed jobs that exceed retry limits"""
    
    def __init__(self, queue_file: str = "dead_letter_queue.json"):
        self.queue_file = queue_file
        self.queue: List[FailedJob] = []
        self._load_queue()
    
    def _load_queue(self):
        """Load queue from file"""
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                    self.queue = [FailedJob.from_dict(item) for item in data]
                logger.info(f"Loaded {len(self.queue)} items from dead letter queue")
            except Exception as e:
                logger.error(f"Error loading dead letter queue: {e}")
                self.queue = []
    
    def _save_queue(self):
        """Save queue to file"""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump([job.to_dict() for job in self.queue], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving dead letter queue: {e}")
    
    def add(self, job_id: str, keyword: str, error: str, attempt_count: int):
        """Add a failed job to the dead letter queue"""
        failed_job = FailedJob(
            job_id=job_id,
            keyword=keyword,
            error=error,
            attempt_count=attempt_count,
            last_attempt=datetime.now(),
            created_at=datetime.now()
        )
        self.queue.append(failed_job)
        self._save_queue()
        logger.warning(f"Added job {job_id} to dead letter queue (attempts: {attempt_count})")
    
    def get_all(self) -> List[FailedJob]:
        """Get all failed jobs"""
        return self.queue.copy()
    
    def remove(self, job_id: str):
        """Remove a job from the queue"""
        self.queue = [job for job in self.queue if job.job_id != job_id]
        self._save_queue()

class JobRecovery:
    """Handles automatic retry and recovery of failed jobs"""
    
    def __init__(self, max_retries: int = 3, retry_delays: List[float] = None):
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [60, 300, 900]  # 1min, 5min, 15min
        self.dead_letter_queue = DeadLetterQueue()
        self.retry_queue: Dict[str, Dict[str, Any]] = {}
    
    async def retry_failed_job(
        self, 
        job_id: str, 
        keyword: str, 
        scrape_func: callable,
        attempt: int = 1
    ) -> Dict[str, Any]:
        """
        Retry a failed job with exponential backoff
        
        Args:
            job_id: Job identifier
            keyword: Search keyword
            scrape_func: Function to retry
            attempt: Current attempt number
            
        Returns:
            Result from scrape function
        """
        if attempt > self.max_retries:
            # Move to dead letter queue
            self.dead_letter_queue.add(
                job_id=job_id,
                keyword=keyword,
                error="Max retries exceeded",
                attempt_count=attempt
            )
            return {
                "success": False,
                "error": f"Max retries ({self.max_retries}) exceeded",
                "dead_lettered": True
            }
        
        # Calculate delay based on attempt
        delay_index = min(attempt - 1, len(self.retry_delays) - 1)
        delay = self.retry_delays[delay_index]
        
        logger.info(f"Retrying job {job_id} (attempt {attempt}/{self.max_retries}) after {delay}s")
        
        # Schedule retry
        await asyncio.sleep(delay)
        
        try:
            # Retry the scrape
            result = await scrape_func(keyword)
            
            if result.get("success"):
                logger.info(f"Job {job_id} recovered successfully on attempt {attempt}")
                return result
            else:
                # Retry again
                return await self.retry_failed_job(job_id, keyword, scrape_func, attempt + 1)
                
        except Exception as e:
            logger.error(f"Retry attempt {attempt} failed for job {job_id}: {e}")
            # Retry again
            return await self.retry_failed_job(job_id, keyword, scrape_func, attempt + 1)
    
    def get_dead_letter_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs in dead letter queue"""
        return [job.to_dict() for job in self.dead_letter_queue.get_all()]

# Global recovery instance
_recovery: Optional[JobRecovery] = None

try:
    from config import Config
    DEFAULT_MAX_RETRIES = Config.API_MAX_RETRIES
except:
    DEFAULT_MAX_RETRIES = 3

def get_recovery() -> JobRecovery:
    """Get global recovery instance"""
    global _recovery
    if _recovery is None:
        _recovery = JobRecovery(max_retries=DEFAULT_MAX_RETRIES)
    return _recovery

