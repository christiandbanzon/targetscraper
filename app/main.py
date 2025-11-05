#!/usr/bin/env python3
"""
Target Product Scraper API

A professional FastAPI application for scraping Target.com products by keyword.
Features include async job processing, retry logic, rate limiting, pagination,
data validation, error recovery, and real-time progress updates.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
import uuid
import json
import os
from datetime import datetime
import logging
from .config import Config
from .error_recovery import get_recovery, JobRecovery

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

# WebSocket connections for real-time updates
websocket_connections: Dict[str, List[WebSocket]] = {}

# Job recovery system
recovery = get_recovery()

# Pydantic models
class KeywordScrapeRequest(BaseModel):
    """Request model for keyword-based scraping"""
    keyword: str = Field(..., min_length=1, max_length=100, description="Search keyword for Target.com")
    search_type: str = Field(default="keyword", description="Type of search (always 'keyword')")
    max_pages: int = Field(default=5, ge=1, le=20, description="Maximum number of pages to scrape")
    
    class Config:
        schema_extra = {
            "example": {
                "keyword": "Nike Air Max",
                "search_type": "keyword",
                "max_pages": 5
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
        "message": "Target Product Scraper API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "scrape_keyword": "/scrape/keyword",
            "scrape_batch": "/scrape/keywords/batch",
            "job_status": "/jobs/{job_id}",
            "download_csv": "/download/{job_id}/csv",
            "download_json": "/download/{job_id}/json",
            "list_jobs": "/jobs",
            "dead_letter_queue": "/dead-letter-queue",
            "websocket": "/ws/jobs/{job_id}",
            "sse": "/events/jobs/{job_id}",
            "docs": "/docs"
        }
    }

# Keyword scraping endpoint
@app.post("/scrape/keyword", response_model=JobResponse)
async def scrape_keyword(request: KeywordScrapeRequest, background_tasks: BackgroundTasks):
    """Start a keyword scraping job with pagination and error recovery"""
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": f"Starting keyword search for '{request.keyword}'",
        "keyword": request.keyword,
        "search_type": request.search_type,
        "max_pages": request.max_pages,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "results": None
    }
    
    # Add background task with retry logic and pagination
    background_tasks.add_task(run_keyword_scrape, job_id, request.keyword, request.max_pages)
    
    return JobResponse(
        job_id=job_id,
        status="pending",
        message=f"Keyword scraping job started for '{request.keyword}' (max {request.max_pages} pages)",
        created_at=jobs[job_id]["created_at"]
    )

# Batch keyword scraping endpoint (NEW - for concurrent processing)
@app.post("/scrape/keywords/batch")
async def scrape_keywords_batch(keywords: List[str], background_tasks: BackgroundTasks):
    """Start concurrent batch scraping for multiple keywords"""
    from .async_keyword_scraper import batch_scrape_keywords
    
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": f"Starting batch scrape for {len(keywords)} keywords",
        "keywords": keywords,
        "search_type": "batch",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "results": None
    }
    
    # Run batch scrape directly (concurrent processing)
    async def run_batch_scrape(job_id: str, keywords: List[str]):
        try:
            jobs[job_id]["status"] = "running"
            jobs[job_id]["progress"] = 20
            jobs[job_id]["updated_at"] = datetime.now().isoformat()
            
            results = await batch_scrape_keywords(keywords)
            
            success_count = sum(1 for r in results.values() if r.get("success"))
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["message"] = f"Batch scrape completed: {success_count}/{len(keywords)} successful"
            jobs[job_id]["results"] = results
            jobs[job_id]["updated_at"] = datetime.now().isoformat()
        except Exception as e:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = f"Batch scrape failed: {str(e)}"
            jobs[job_id]["updated_at"] = datetime.now().isoformat()
    
    background_tasks.add_task(run_batch_scrape, job_id, keywords)
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Batch scraping job started for {len(keywords)} keywords",
        "created_at": jobs[job_id]["created_at"]
    }

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

# WebSocket endpoint for real-time progress updates
@app.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress updates"""
    await websocket.accept()
    
    # Add to connections list
    if job_id not in websocket_connections:
        websocket_connections[job_id] = []
    websocket_connections[job_id].append(websocket)
    
    try:
        # Send initial status if job exists
        if job_id in jobs:
            await websocket.send_json({
                "job_id": job_id,
                "status": jobs[job_id]["status"],
                "progress": jobs[job_id]["progress"],
                "message": jobs[job_id]["message"],
                "timestamp": datetime.now().isoformat()
            })
        
        # Keep connection alive and listen for messages
        while True:
            try:
                # Wait for client messages (ping/pong)
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        # Remove from connections
        if job_id in websocket_connections:
            websocket_connections[job_id] = [
                ws for ws in websocket_connections[job_id] if ws != websocket
            ]
            if not websocket_connections[job_id]:
                del websocket_connections[job_id]

# Server-Sent Events (SSE) endpoint for progress updates
@app.get("/events/jobs/{job_id}")
async def sse_endpoint(job_id: str):
    """Server-Sent Events endpoint for real-time job progress"""
    async def event_generator():
        last_progress = -1
        while True:
            if job_id in jobs:
                job = jobs[job_id]
                current_progress = job.get("progress", 0)
                
                if current_progress != last_progress:
                    data = {
                        "job_id": job_id,
                        "status": job.get("status"),
                        "progress": current_progress,
                        "message": job.get("message"),
                        "timestamp": job.get("updated_at")
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_progress = current_progress
                    
                    if job.get("status") in ["completed", "failed", "dead_letter"]:
                        break
            else:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            
            await asyncio.sleep(1)  # Update every second
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Dead letter queue endpoint
@app.get("/dead-letter-queue")
async def get_dead_letter_queue():
    """Get all jobs in dead letter queue"""
    dead_letter_jobs = recovery.get_dead_letter_jobs()
    return {
        "total": len(dead_letter_jobs),
        "jobs": dead_letter_jobs
    }

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


async def _update_job_progress(job_id: str, progress: int, message: str, status: str = None):
    """Update job progress and notify WebSocket connections"""
    if job_id in jobs:
        jobs[job_id]["progress"] = progress
        jobs[job_id]["message"] = message
        jobs[job_id]["updated_at"] = datetime.now().isoformat()
        if status:
            jobs[job_id]["status"] = status
    
    # Notify WebSocket connections
    if job_id in websocket_connections:
        message_data = {
            "job_id": job_id,
            "progress": progress,
            "message": message,
            "status": status or jobs.get(job_id, {}).get("status", "unknown"),
            "timestamp": datetime.now().isoformat()
        }
        disconnected = []
        for ws in websocket_connections[job_id]:
            try:
                await ws.send_json(message_data)
            except:
                disconnected.append(ws)
        
        # Remove disconnected clients
        for ws in disconnected:
            websocket_connections[job_id].remove(ws)

# Background task functions
async def run_keyword_scrape(job_id: str, keyword: str, max_pages: int = 5):
    """Run keyword scraping in background using async scraper with error recovery"""
    try:
        # Import async scraper
        from .async_keyword_scraper import keyword_scraper_async
        
        # Progress callback
        async def progress_callback(current_page: int, total_pages: int):
            progress = int((current_page / total_pages) * 90) + 10  # 10-100%
            await _update_job_progress(
                job_id, 
                progress, 
                f"Scraping page {current_page}/{total_pages} for '{keyword}'",
                "running"
            )
        
        # Update job status
        await _update_job_progress(job_id, 5, f"Starting keyword search for '{keyword}'", "running")
        
        # Run the async keyword scraper with retry logic
        result = await keyword_scraper_async(keyword, max_pages=max_pages, progress_callback=progress_callback)
        
        if result.get("success"):
            await _update_job_progress(
                job_id, 
                100, 
                f"Successfully scraped {len(result.get('products', []))} products for '{keyword}'",
                "completed"
            )
            jobs[job_id]["results"] = {
                "success": True,
                "products_count": len(result.get('products', [])),
                "filename": result.get('filename'),
                "keyword": keyword,
                "pages_scraped": result.get("pages_scraped", 1),
                "total_found": result.get("total_found", 0),
                "valid_products": result.get("valid_products", 0),
                "quality_score": result.get("quality_score", 0.0),
                "validation": result.get("validation", {})
            }
        else:
            # Try error recovery
            logger.warning(f"Initial scrape failed, attempting recovery for job {job_id}")
            await _update_job_progress(job_id, 50, f"Retrying job '{keyword}'...", "retrying")
            
            recovery_result = await recovery.retry_failed_job(
                job_id=job_id,
                keyword=keyword,
                scrape_func=lambda kw: keyword_scraper_async(kw, max_pages=max_pages, progress_callback=progress_callback)
            )
            
            if recovery_result.get("success"):
                await _update_job_progress(
                    job_id, 
                    100, 
                    f"Recovered and scraped {len(recovery_result.get('products', []))} products",
                    "completed"
                )
                jobs[job_id]["results"] = {
                    "success": True,
                    "products_count": len(recovery_result.get('products', [])),
                    "filename": recovery_result.get('filename'),
                    "keyword": keyword,
                    "recovered": True
                }
            else:
                await _update_job_progress(
                    job_id, 
                    0, 
                    f"Failed to scrape '{keyword}': {result.get('error', 'Unknown error')}",
                    "failed"
                )
                jobs[job_id]["results"] = {
                    "success": False,
                    "error": result.get('error', 'Unknown error'),
                    "keyword": keyword,
                    "dead_lettered": recovery_result.get("dead_lettered", False)
                }
        
    except Exception as e:
        await _update_job_progress(job_id, 0, f"Error scraping '{keyword}': {str(e)}", "failed")
        logger.error(f"Error in keyword scraping for '{keyword}': {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    from .async_keyword_scraper import close_http_client
    await close_http_client()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
