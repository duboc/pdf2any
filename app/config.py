import os
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings

# Set up basic logging configuration
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level_str)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Loads application settings from environment variables."""
    gcp_project_id: str
    gcs_bucket_name: str
    vertex_ai_location: str = "us-central1" # Default if not set
    google_application_credentials: str | None = None # Path to service account key
    log_level: str = "INFO"

    class Config:
        # Load settings from a .env file
        env_file = '../.env' # Path relative to this config.py file
        env_file_encoding = 'utf-8'

@lru_cache() # Cache the settings object for performance
def get_settings() -> Settings:
    """Returns the application settings."""
    try:
        settings = Settings()
        logger.info("Application settings loaded successfully.")
        # Log loaded settings, masking credentials if necessary (none sensitive here yet)
        # logger.debug(f"Settings: {settings.dict()}")
        if settings.google_application_credentials:
            logger.info(f"Using Service Account Credentials from: {settings.google_application_credentials}")
            # Ensure the credentials file is set in the environment for google libraries
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
        else:
             logger.info("Using Application Default Credentials (ADC).")
        return settings
    except Exception as e:
        logger.error(f"Error loading application settings: {e}")
        raise

# Load settings immediately to catch errors early
settings = get_settings()
