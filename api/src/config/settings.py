# settings.py
# Centralized configuration settings for the Stock Sentiment Analyzer project.
# Uses environment variables to manage sensitive or environment-specific values,
# ensuring portability across development, testing, and production environments.

import os
from typing import Optional
from pathlib import Path
from decouple import config

GCP_PROJECT_ID = config('GCP_PROJECT_ID')
BQ_DATASET = config('BQ_DATASET')
SENTIMENT_TABLE = config('SENTIMENT_TABLE')

# Base directory for the project (relative to this file)
BASE_DIR = Path(__file__).resolve().parent.parent

# Google Cloud Project settings
GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "stock-sentiment-analyzer")
"""The Google Cloud Project ID used for BigQuery and other GCP services."""

BQ_DATASET: str = os.getenv("BQ_DATASET", "sentiment_dataset")
"""The BigQuery dataset containing sentiment data tables."""

# API settings
GRPC_PORT: int = int(os.getenv("GRPC_PORT", "50051"))
"""The port on which the gRPC server listens."""

# Ingestion settings
X_API_KEY: Optional[str] = os.getenv("X_API_KEY")
"""API key for accessing the X API (Twitter). Required for ingestion."""

X_API_SECRET: Optional[str] = os.getenv("X_API_SECRET")
"""API secret for accessing the X API (Twitter). Required for ingestion."""

# Processing settings
SENTIMENT_TABLE: str = os.getenv("SENTIMENT_TABLE", "sentiment_data")
"""The BigQuery table name for storing processed sentiment data."""

BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "1000"))
"""Number of records to process in a single batch for efficiency."""

# Logging settings (used indirectly via logging.yaml)
LOG_DIR: str = str(BASE_DIR / "logs")
"""Directory for storing log files."""

# Environment-specific settings
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
"""Current environment (development, testing, production)."""

DEBUG: bool = ENVIRONMENT == "development"
"""Enable debug mode in development environment."""

def validate_settings() -> None:
    """Validate critical settings and raise exceptions if misconfigured."""
    if not GCP_PROJECT_ID:
        raise ValueError("GCP_PROJECT_ID must be set in the environment.")
    if not BQ_DATASET:
        raise ValueError("BQ_DATASET must be set in the environment.")
    if ENVIRONMENT not in ["development", "testing", "production"]:
        raise ValueError(f"Invalid ENVIRONMENT: {ENVIRONMENT}. Must be 'development', 'testing', or 'production'.")
    if X_API_KEY is None or X_API_SECRET is None:
        logger.warning("X_API_KEY or X_API_SECRET not set; ingestion may fail.")

if __name__ == "__main__":
    # Example usage for testing
    import logging
    from config.logging import logging_config
    logging.config.dictConfig(logging_config)
    logger = logging.getLogger(__name__)

    validate_settings()
    logger.info(f"GCP_PROJECT_ID: {GCP_PROJECT_ID}")
    logger.info(f"BQ_DATASET: {BQ_DATASET}")
    logger.info(f"GRPC_PORT: {GRPC_PORT}")
    logger.info(f"ENVIRONMENT: {ENVIRONMENT}")