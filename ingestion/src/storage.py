# storage.py
# Implements logic to store raw data in Google Cloud Storage (GCS) for the Stock Sentiment Analyzer project.
# Provides a modular interface to upload data as JSON files, ensuring scalability and traceability.

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from google.cloud import storage
from google.api_core import exceptions as gcp_exceptions

# Project imports
from config import settings
from config.logging import logging_config

# Configure logging
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

class GCSStorage:
    """Handles storage of raw data in Google Cloud Storage."""

    def __init__(self, bucket_name: Optional[str] = None):
        """
        Initialize the GCS storage client.

        Args:
            bucket_name: Name of the GCS bucket. Defaults to '{GCP_PROJECT_ID}-raw-data' if not provided.

        Raises:
            ValueError: If GCP_PROJECT_ID is not set in settings.
        """
        if not settings.GCP_PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID must be set in the environment")

        self.client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.bucket_name = bucket_name or f"{settings.GCP_PROJECT_ID}-raw-data"
        self.bucket = self._get_or_create_bucket()
        logger.info(f"GCSStorage initialized with bucket: {self.bucket_name}")

    def _get_or_create_bucket(self) -> storage.Bucket:
        """
        Retrieve or create the GCS bucket.

        Returns:
            The GCS bucket object.

        Raises:
            gcp_exceptions.GoogleAPIError: If bucket creation fails unexpectedly.
        """
        try:
            bucket = self.client.get_bucket(self.bucket_name)
            logger.info(f"Using existing bucket: {self.bucket_name}")
        except gcp_exceptions.NotFound:
            try:
                bucket = self.client.create_bucket(self.bucket_name, location="US")
                logger.info(f"Created new bucket: {self.bucket_name}")
            except gcp_exceptions.GoogleAPIError as e:
                logger.error(f"Failed to create bucket {self.bucket_name}: {str(e)}")
                raise
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to access bucket {self.bucket_name}: {str(e)}")
            raise
        return bucket

    def upload_data(self, data: List[Dict[str, Any]], prefix: str = "tweets") -> str:
        """
        Upload data to GCS as a JSON file with a timestamped name.

        Args:
            data: List of dictionaries containing raw data (e.g., tweets).
            prefix: Prefix for the object name (e.g., "tweets" for "tweets/2025-03-27_12-00-00.json").

        Returns:
            GCS URI of the uploaded file (e.g., "gs://bucket/tweets/2025-03-27_12-00-00.json").

        Raises:
            ValueError: If data is empty or invalid.
            gcp_exceptions.GoogleAPIError: If upload fails.
        """
        if not data or not isinstance(data, list):
            logger.warning("No valid data provided for upload.")
            raise ValueError("Data must be a non-empty list of dictionaries")

        # Generate a unique filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        blob_name = f"{prefix}/{timestamp}.json"
        blob = self.bucket.blob(blob_name)

        try:
            # Upload data as JSON
            blob.upload_from_string(
                json.dumps(data, indent=2),
                content_type="application/json"
            )
            uri = f"gs://{self.bucket_name}/{blob_name}"
            logger.info(f"Successfully uploaded {len(data)} records to {uri}")
            return uri
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to upload data to GCS: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during upload: {str(e)}")
            raise

    def list_files(self, prefix: str = "tweets") -> List[str]:
        """
        List all files in the bucket with the given prefix.

        Args:
            prefix: Prefix to filter files (e.g., "tweets").

        Returns:
            List of GCS URIs for matching files.

        Raises:
            gcp_exceptions.GoogleAPIError: If listing fails.
        """
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            uris = [f"gs://{self.bucket_name}/{blob.name}" for blob in blobs]
            logger.info(f"Found {len(uris)} files with prefix '{prefix}' in {self.bucket_name}")
            return uris
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to list files in GCS: {str(e)}")
            raise

if __name__ == "__main__":
    # Example usage for testing
    storage = GCSStorage()

    # Sample data (e.g., from fetcher.py)
    sample_data = [
        {
            "tweet_id": 123456789,
            "text": "Loving $AAPL today!",
            "created_at": "2025-03-27T12:00:00Z",
            "username": "user1",
            "ticker": "AAPL"
        },
        {
            "tweet_id": 987654321,
            "text": "$TSLA is skyrocketing!",
            "created_at": "2025-03-27T12:01:00Z",
            "username": "user2",
            "ticker": "TSLA"
        }
    ]

    # Upload sample data
    uri = storage.upload_data(sample_data)
    logger.info(f"Uploaded sample data to: {uri}")

    # List files
    files = storage.list_files()
    logger.info(f"Files in bucket: {files}")