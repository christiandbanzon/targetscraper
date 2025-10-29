#!/usr/bin/env python3
"""
Professional FastAPI Web API for Target.com Product Scraper
Keyword-based scraping with async job processing and file downloads
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
import uuid
import json
import os
import subprocess
from datetime import datetime
import logging
from config import Config

# Setup logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Target Product Scraper API",
    description="Professional API for scraping Target.com products by keyword",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job storage (in production, use a database)
jobs = {}

# Pydantic models
class KeywordScrapeRequest(BaseModel):
    """Request model for keyword-based scraping"""
    keyword: str = Field(..., min_length=1, max_length=100, description="Search keyword for Target.com")
    search_type: str = Field(default="keyword", description="Type of search (always 'keyword')")
    
    class Config:
        schema_extra = {
            "example": {
                "keyword": "Nike Air Max",
                "search_type": "keyword"
            }
        }

class CategoryScrapeRequest(BaseModel):
    """Request model for category-based scraping"""
    category: str = Field(..., min_length=1, max_length=100, description="Category to search on Target.com")
    search_type: str = Field(default="category", description="Type of search (always 'category')")
    
    class Config:
        schema_extra = {
            "example": {
                "category": "Electronics",
                "search_type": "category"
            }
        }

class JobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    created_at: str = Field(..., description="Job creation timestamp")
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "pending",
                "message": "Job started successfully",
                "created_at": "2024-01-01T12:00:00Z"
            }
        }

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    results: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Target Brand Scraper API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "scrape_keyword": "/scrape/keyword",
            "scrape_category": "/scrape/category", 
            "job_status": "/jobs/{job_id}",
            "download_csv": "/download/{job_id}/csv",
            "download_json": "/download/{job_id}/json",
            "list_jobs": "/jobs",
            "available_categories": "/categories"
        }
    }

# Keyword scraping endpoint
@app.post("/scrape/keyword", response_model=JobResponse)
async def scrape_keyword(request: KeywordScrapeRequest, background_tasks: BackgroundTasks):
    """Start a keyword scraping job"""
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": f"Starting keyword search for '{request.keyword}'",
        "keyword": request.keyword,
        "search_type": request.search_type,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "results": None
    }
    
    # Add background task
    background_tasks.add_task(run_keyword_scrape, job_id, request.keyword)
    
    return JobResponse(
        job_id=job_id,
        status="pending",
        message=f"Keyword scraping job started for '{request.keyword}'",
        created_at=jobs[job_id]["created_at"]
    )

# Category scraping endpoint
@app.post("/scrape/category", response_model=JobResponse)
async def scrape_category(request: CategoryScrapeRequest, background_tasks: BackgroundTasks):
    """Start a category scraping job"""
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": f"Starting category search for {request.category}",
        "category": request.category,
        "search_type": request.search_type,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "results": None
    }
    
    # Add background task
    background_tasks.add_task(run_category_scrape, job_id, request.category)
    
    return JobResponse(
        job_id=job_id,
        status="pending",
        message=f"Category scraping job started for {request.category}",
        created_at=jobs[job_id]["created_at"]
    )

# Job status endpoint
@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a scraping job"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return JobStatus(**job)

# Download CSV endpoint
@app.get("/download/{job_id}/csv")
async def download_csv(job_id: str):
    """Download results as CSV file"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    # Look for CSV files in outputs directory
    keyword = job.get("keyword", "unknown")
    category = job.get("category", "unknown")
    
    # Try to find the most recent CSV file
    csv_files = []
    if os.path.exists("outputs"):
        for filename in os.listdir("outputs"):
            if filename.endswith('.csv') and (keyword.lower() in filename.lower() or category.lower() in filename.lower()):
                file_path = os.path.join("outputs", filename)
                csv_files.append((filename, os.path.getmtime(file_path)))
    
    if not csv_files:
        raise HTTPException(status_code=404, detail="No CSV file found for this job")
    
    # Get the most recent file
    latest_file = max(csv_files, key=lambda x: x[1])
    file_path = os.path.join("outputs", latest_file[0])
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="CSV file not found")
    
    return FileResponse(
        path=file_path,
        filename=latest_file[0],
        media_type="text/csv"
    )

# Download JSON endpoint
@app.get("/download/{job_id}/json")
async def download_json(job_id: str):
    """Download results as JSON file"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    # Look for JSON files in outputs directory
    keyword = job.get("keyword", "unknown")
    category = job.get("category", "unknown")
    
    # Try to find the most recent JSON file
    json_files = []
    if os.path.exists("outputs"):
        for filename in os.listdir("outputs"):
            if filename.endswith('.json') and (keyword.lower() in filename.lower() or category.lower() in filename.lower()):
                file_path = os.path.join("outputs", filename)
                json_files.append((filename, os.path.getmtime(file_path)))
    
    if not json_files:
        raise HTTPException(status_code=404, detail="No JSON file found for this job")
    
    # Get the most recent file
    latest_file = max(json_files, key=lambda x: x[1])
    file_path = os.path.join("outputs", latest_file[0])
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="JSON file not found")
    
    return FileResponse(
        path=file_path,
        filename=latest_file[0],
        media_type="application/json"
    )

# List all jobs
@app.get("/jobs")
async def list_jobs():
    """List all jobs"""
    return {"jobs": list(jobs.values())}

# Available search examples
@app.get("/search-examples")
async def get_search_examples():
    """Get list of search examples"""
    return {
        "examples": [
            "Nike Air Max",
            "iPhone 15",
            "Samsung Galaxy",
            "Adidas shoes",
            "MacBook Pro",
            "Learning Resources",
            "Lavazza coffee",
            "Life Extensions",
            "Kitchen storage",
            "Wireless earbuds"
        ],
        "note": "You can search for any product keyword!"
    }

# Available categories
@app.get("/categories")
async def get_available_categories():
    """Get list of available categories"""
    return {
        "categories": [
            "Educational Toys",
            "Coffee",
            "Vitamins",
            "Health",
            "Home Organization",
            "Kitchen Storage"
        ]
    }

# Background task functions
async def run_keyword_scrape(job_id: str, keyword: str):
    """Run keyword scraping in background"""
    try:
        # Update job status
        jobs[job_id]["status"] = "running"
        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = f"Running keyword search for '{keyword}'"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        
        # Run the keyword scraper
        result = subprocess.run(
            ['python', 'keyword_scraper.py', keyword],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode == 0:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["message"] = f"Successfully scraped products for '{keyword}'"
            jobs[job_id]["results"] = {
                "success": True,
                "output": result.stdout,
                "keyword": keyword
            }
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["progress"] = 0
            jobs[job_id]["message"] = f"Failed to scrape '{keyword}': {result.stderr}"
            jobs[job_id]["results"] = {
                "success": False,
                "error": result.stderr,
                "keyword": keyword
            }
        
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = f"Error scraping '{keyword}': {str(e)}"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        logger.error(f"Error in keyword scraping for '{keyword}': {str(e)}")

async def run_category_scrape(job_id: str, category: str):
    """Run category scraping in background"""
    try:
        # Update job status
        jobs[job_id]["status"] = "running"
        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = f"Running category search for {category}"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        
        # Run the comprehensive scraper
        result = subprocess.run(
            ['python', 'direct_brand_scraper.py'],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode == 0:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["message"] = f"Successfully scraped {category} products"
            jobs[job_id]["results"] = {
                "success": True,
                "output": result.stdout,
                "category": category
            }
        else:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["progress"] = 0
            jobs[job_id]["message"] = f"Failed to scrape {category}: {result.stderr}"
            jobs[job_id]["results"] = {
                "success": False,
                "error": result.stderr,
                "category": category
            }
        
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = f"Error scraping {category}: {str(e)}"
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        logger.error(f"Error in category scraping for {category}: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
