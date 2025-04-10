# Placeholder for workflow management logic
import asyncio
from .config import logger
# Import the new task status functions instead of the dict from main
from . import tasks

# Import processing functions (will be defined later)
from . import processing

# Import Gemini client (assuming it's now in lib/)
import sys
import os
# Add lib directory to path to allow import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
try:
    from lib.gemini_client import GeminiClient
except ImportError:
    logger.error("Could not import GeminiClient from lib directory.")
    GeminiClient = None # Define as None to avoid NameError during import


async def process_pdf(task_id: str, gcs_uri: str):
    """
    Orchestrates the PDF processing workflow.
    1. Perform OCR (OSS)
    2. Perform Gemini Extraction
    3. Perform Gemini Reconciliation
    4. Generate Excel Report
    """
    logger.info(f"Workflow started for Task ID: {task_id}, GCS URI: {gcs_uri}")
    tasks.add_task_log(task_id, f"Starting workflow with GCS URI: {gcs_uri}")
    # Update status using the tasks module function
    tasks.update_task_status(task_id, status="processing_ocr")

    try:
        # --- Step 1: OSS OCR ---
        logger.info(f"[Task {task_id}] Performing OCR...")
        tasks.add_task_log(task_id, "Starting OCR processing...")
        ocr_text = await processing.perform_ocr(gcs_uri)
        ocr_length = len(ocr_text) if ocr_text else 0
        tasks.add_task_log(task_id, f"OCR completed successfully. Extracted {ocr_length} characters.")
        tasks.update_task_status(task_id, status="processing_gemini_extract")

        # --- Step 2: Gemini Extraction ---
        logger.info(f"[Task {task_id}] Performing Gemini Extraction...")
        tasks.add_task_log(task_id, "Starting Gemini extraction...")
        extracted_data_json = await processing.extract_with_gemini(gcs_uri)
        
        # Log extraction results
        if extracted_data_json:
            metadata_count = len(extracted_data_json.get('metadata', {})) if isinstance(extracted_data_json.get('metadata'), dict) else 0
            kv_count = len(extracted_data_json.get('key_value_pairs', {})) if isinstance(extracted_data_json.get('key_value_pairs'), dict) else 0
            sections_count = len(extracted_data_json.get('text_sections', {})) if isinstance(extracted_data_json.get('text_sections'), dict) else 0
            tables_count = len(extracted_data_json.get('tables', [])) if isinstance(extracted_data_json.get('tables'), list) else 0
            
            tasks.add_task_log(task_id, f"Gemini extraction completed. Found {metadata_count} metadata items, {kv_count} key-value pairs, {sections_count} text sections, and {tables_count} tables.")
        else:
            tasks.add_task_log(task_id, "Gemini extraction completed but no structured data was returned.")
            
        tasks.update_task_status(task_id, status="processing_reconciliation")

        # --- Step 3: Gemini Reconciliation ---
        logger.info(f"[Task {task_id}] Performing Gemini Reconciliation...")
        tasks.add_task_log(task_id, "Starting Gemini reconciliation...")
        reconciled_data_json = await processing.reconcile_with_gemini(extracted_data_json, ocr_text)
        
        # Log reconciliation results
        if reconciled_data_json:
            metadata_count = len(reconciled_data_json.get('metadata', {})) if isinstance(reconciled_data_json.get('metadata'), dict) else 0
            kv_count = len(reconciled_data_json.get('key_value_pairs', {})) if isinstance(reconciled_data_json.get('key_value_pairs'), dict) else 0
            sections_count = len(reconciled_data_json.get('text_sections', {})) if isinstance(reconciled_data_json.get('text_sections'), dict) else 0
            tables_count = len(reconciled_data_json.get('tables', [])) if isinstance(reconciled_data_json.get('tables'), list) else 0
            
            tasks.add_task_log(task_id, f"Gemini reconciliation completed. Final data has {metadata_count} metadata items, {kv_count} key-value pairs, {sections_count} text sections, and {tables_count} tables.")
        else:
            tasks.add_task_log(task_id, "Gemini reconciliation completed but no structured data was returned.")
            
        tasks.update_task_status(task_id, status="generating_report")

        # --- Step 4: Generate Excel Report ---
        logger.info(f"[Task {task_id}] Generating Excel report...")
        tasks.add_task_log(task_id, "Generating Excel report...")
        excel_file_path = await processing.generate_excel(reconciled_data_json, task_id)
        tasks.add_task_log(task_id, f"Excel report generated at: {excel_file_path}")

        # --- Update Task Status to Completed ---
        tasks.update_task_status(task_id, status="completed", result_file=excel_file_path)
        tasks.add_task_log(task_id, "Workflow completed successfully!")
        logger.info(f"Workflow completed successfully for Task ID: {task_id}")

    except Exception as e:
        error_msg = f"Workflow failed: {str(e)}"
        logger.error(f"Workflow failed for Task ID {task_id}: {e}", exc_info=True)
        tasks.add_task_log(task_id, error_msg)
        # Update status to Failed using the tasks module function
        tasks.update_task_status(task_id, status="failed", error=str(e))
