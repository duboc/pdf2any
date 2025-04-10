from google.cloud import storage
from google.api_core import exceptions as google_exceptions
from fastapi import UploadFile
import logging

# Import settings from the main app config
from ..config import settings, logger

# Initialize GCS client globally or within functions as needed
# Initializing globally might be slightly more efficient if reused often
# but ensure credentials are handled correctly (usually done by the library via ADC or GOOGLE_APPLICATION_CREDENTIALS)
try:
    storage_client = storage.Client(project=settings.gcp_project_id)
except Exception as e:
    logger.error(f"Failed to initialize Google Cloud Storage client: {e}", exc_info=True)
    # Depending on the application needs, you might want to raise this
    # or handle it gracefully later when the client is used.
    storage_client = None

async def upload_file_to_gcs(file: UploadFile, destination_blob_name: str) -> str:
    """
    Uploads a file object (from FastAPI UploadFile) to the specified GCS bucket.

    Args:
        file: The FastAPI UploadFile object containing the file data and metadata.
        destination_blob_name: The desired name for the file in the GCS bucket.

    Returns:
        The GCS URI (gs://bucket_name/blob_name) of the uploaded file.

    Raises:
        Exception: If the upload fails.
        ValueError: If the storage client was not initialized.
    """
    if not storage_client:
        raise ValueError("Google Cloud Storage client not initialized. Check credentials and configuration.")

    try:
        bucket_name = settings.gcs_bucket_name
        client = storage.Client(project=settings.gcp_project_id)
        
        # Add these debug lines
        logger.info(f"Project ID: {settings.gcp_project_id}")
        logger.info(f"Bucket Name: {bucket_name}")
        logger.info(f"Client Project: {client.project}")
        
        bucket = client.bucket(bucket_name)
        #bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        logger.info(f"Attempting to upload '{file.filename}' to gs://{bucket_name}/{destination_blob_name}")

        # Reset file pointer just in case it was read before
        await file.seek(0)

        # Upload the file stream
        # Use content_type from the uploaded file
        blob.upload_from_file(file.file, content_type=file.content_type)

        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        logger.info(f"Successfully uploaded file to {gcs_uri}")
        return gcs_uri

    except google_exceptions.NotFound:
        logger.error(f"GCS Bucket '{bucket_name}' not found.")
        raise Exception(f"GCS Bucket '{bucket_name}' not found.")
    except google_exceptions.Forbidden as e:
         logger.error(f"Permission denied for GCS bucket '{bucket_name}'. Check IAM permissions: {e}", exc_info=True)
         raise Exception(f"Permission denied for GCS bucket '{bucket_name}'.")
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}", exc_info=True)
        raise Exception(f"Failed to upload file '{file.filename}' to GCS.")
    finally:
        # Ensure the file object is closed, especially if it's a temporary file
        # although FastAPI typically handles this for UploadFile.
        await file.close()
        logger.debug(f"Closed file object for {file.filename}")

# Optional: Add functions for downloading, deleting, etc. if needed later
# async def download_blob_to_file(...): ...
# async def delete_blob(...): ...
