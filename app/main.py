import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import uuid
import shutil
import asyncio # Added for triggering background tasks

# Import settings - this also triggers loading/validation
from .config import settings, logger
# Import other necessary modules
from . import workflow_manager # Now created
from .utils import gcs_utils # Now created
from . import tasks # Import the new tasks module
from fastapi.middleware.cors import CORSMiddleware # Import CORS

# --- FastAPI App Initialization ---
app = FastAPI(title="PDF Extractor & Reconciler")

# Add CORS middleware - Allow requests from the frontend origin
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://0.0.0.0",       # Allow binding address
    "http://0.0.0.0:8000",
    # Add other origins if necessary, but localhost should cover this case
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all standard methods including POST
    allow_headers=["*"], # Allow all headers
)

# Task status is now managed in tasks.py


# --- API Endpoints ---
# Define API routes BEFORE mounting static files

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    logger.info("Health check endpoint called.")
    return JSONResponse(content={"status": "healthy", "message": "API is running."})

@app.post("/api/upload", tags=["Processing"])
async def upload_pdf_for_processing(file: UploadFile = File(...)):
    """
    Accepts a PDF file upload, saves it to GCS, and initiates the processing workflow.
    """
    if not file.filename.lower().endswith(".pdf"):
        logger.warning(f"Invalid file type uploaded: {file.filename}")
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are accepted.")

    task_id = str(uuid.uuid4())
    logger.info(f"Received file upload: {file.filename}. Assigned Task ID: {task_id}")
    # Initialize task status using the tasks module
    tasks.init_task(task_id, file.filename)

    try:
        # Upload file to GCS
        upload_blob_name = f"{task_id}_{file.filename}"
        gcs_uri = await gcs_utils.upload_file_to_gcs(file, upload_blob_name)
        logger.info(f"File uploaded to {gcs_uri}")
        # Update status to include GCS URI
        tasks.update_task_status(task_id, status="received", gcs_uri=gcs_uri)

        # Trigger background workflow
        logger.info(f"Triggering background processing for Task ID: {task_id}")
        asyncio.create_task(workflow_manager.process_pdf(task_id, gcs_uri))
        # Update status to processing after triggering the task
        tasks.update_task_status(task_id, status="processing")

        return JSONResponse(content={"message": "File received and processing started.", "task_id": task_id})

    except Exception as e:
        logger.error(f"Error during file upload or workflow initiation for Task ID {task_id}: {e}", exc_info=True)
        # Update status to failed using the tasks module
        tasks.update_task_status(task_id, status="failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@app.get("/api/status/{task_id}", tags=["Processing"])
async def get_task_status_endpoint(task_id: str): # Renamed function slightly
    """Checks the status of a processing task."""
    logger.debug(f"Status check requested for Task ID: {task_id}")
    # Get status using the tasks module
    status_info = tasks.get_task_status(task_id)
    if not status_info:
        logger.warning(f"Status check for unknown Task ID: {task_id}")
        raise HTTPException(status_code=404, detail="Task ID not found.")

    return JSONResponse(content=status_info)


@app.get("/api/download/{task_id}", tags=["Processing"])
async def download_result_endpoint(task_id: str): # Renamed function slightly
    """Downloads the resulting Excel file for a completed task."""
    logger.debug(f"Download requested for Task ID: {task_id}")
    # Get status using the tasks module
    status_info = tasks.get_task_status(task_id)
    if not status_info:
        logger.warning(f"Download requested for unknown Task ID: {task_id}")
        raise HTTPException(status_code=404, detail="Task ID not found.")

    if status_info["status"] != "completed" or not status_info.get("result_file"):
        logger.warning(f"Download attempt for non-completed/missing file Task ID: {task_id}, Status: {status_info['status']}")
        raise HTTPException(status_code=400, detail="Processing not complete or result file not available.")

    result_file_path = status_info["result_file"]
    # Ensure file exists (in a real app, this might be a GCS download path)
    if not os.path.exists(result_file_path):
         logger.error(f"Result file not found for Task ID {task_id} at path: {result_file_path}")
         raise HTTPException(status_code=404, detail="Result file not found.")

    # Extract original filename stem for download
    original_filename_stem = os.path.splitext(status_info["filename"])[0]
    download_filename = f"{original_filename_stem}_extracted.xlsx"

    logger.info(f"Serving result file for Task ID {task_id}: {result_file_path} as {download_filename}")
    return FileResponse(path=result_file_path, filename=download_filename, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.get("/api/logs/{task_id}", tags=["Processing"])
async def get_task_logs_endpoint(task_id: str):
    """Gets detailed processing logs for a specific task."""
    logger.debug(f"Logs requested for Task ID: {task_id}")
    
    # Get status using the tasks module
    status_info = tasks.get_task_status(task_id)
    if not status_info:
        logger.warning(f"Logs requested for unknown Task ID: {task_id}")
        raise HTTPException(status_code=404, detail="Task ID not found.")
    
    # Get logs from the task status
    logs = status_info.get("logs", [])
    
    # Return logs with timestamps and messages
    return JSONResponse(content={
        "task_id": task_id,
        "status": status_info["status"],
        "logs": logs
    })


# --- Optional: Run with Uvicorn directly (for simple local testing) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server directly for local testing...")
    # Note: Run from the project root directory using `python -m app.main`
    # Uvicorn will reload on code changes if reload=True
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level=settings.log_level.lower())


# --- Mount Static Files (for Frontend) ---
# Mount static files AFTER API routes are defined
# Serve files from the 'frontend' directory at the root URL path "/"
frontend_dir = "frontend"
if not os.path.exists(frontend_dir):
    os.makedirs(frontend_dir)
# This allows '/' to serve index.html, but specific API routes like /api/upload take precedence
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
