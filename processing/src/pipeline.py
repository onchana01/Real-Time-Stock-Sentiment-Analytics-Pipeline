# pipeline.py
# Implements the ETL pipeline for the Stock Sentiment Analyzer project.
# Extracts raw tweet data from GCS, transforms it with sentiment analysis,
# and loads the results into BigQuery for downstream analytics.

import logging
import json
from typing import List, Dict, Any
from datetime import datetime
import time
from google.cloud import storage, bigquery
from google.api_core import exceptions as gcp_exceptions
from textblob import TextBlob

# Project imports
from config import settings
from config.logging import logging_config
from data.models import SentimentScore
from data.schema import SENTIMENT_DATA_SCHEMA, create_table_if_not_exists, validate_schema_compatibility

from prometheus_client import Counter, Histogram, start_http_server
from processing.src.sentiment import SentimentAnalyzer
from processing.src.bigquery import BigQueryClient

PROCESS_COUNT = Counter('processing_records_total', 'Total records processed')
PROCESS_LATENCY = Histogram('processing_latency_seconds', 'Processing latency')


# Configure logging
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

class SentimentPipeline:
    """ETL pipeline to process raw tweet data into sentiment scores."""

    def __init__(self):
        """Initialize the pipeline with GCS and BigQuery clients."""
        self.storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.bq_client = bigquery.Client(project=settings.GCP_PROJECT_ID)
        self.bucket_name = f"{settings.GCP_PROJECT_ID}-raw-data"
        self.storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.bq_client = bigquery.Client(project=settings.GCP_PROJECT_ID)
        self.bucket_name = f"{settings.GCP_PROJECT_ID}-raw-data"
        self.analyzer = SentimentAnalyzer()  # Add analyzer
        start_http_server(8000)  # Expose metrics on port 8000
        logger.info("SentimentPipeline initialized with metrics server.")
        
        create_table_if_not_exists(self.bq_client, settings.BQ_DATASET, settings.SENTIMENT_TABLE)
        logger.info("SentimentPipeline initialized successfully.")

    def extract_from_gcs(self, prefix: str = "tweets") -> List[Dict[str, Any]]:
        """
        Extract raw tweet data from GCS.

        Args:
            prefix: GCS prefix to filter files (default: "tweets").

        Returns:
            List of tweet dictionaries from the latest GCS file.

        Raises:
            gcp_exceptions.GoogleAPIError: If GCS access fails.
        """
        try:
            blobs = list(self.storage_client.list_blobs(self.bucket_name, prefix=prefix))
            if not blobs:
                logger.warning(f"No files found in GCS with prefix: {prefix}")
                return []

            # Get the latest file based on name (timestamp)
            latest_blob = max(blobs, key=lambda b: b.name)
            data = json.loads(latest_blob.download_as_text())
            logger.info(f"Extracted {len(data)} records from GCS: gs://{self.bucket_name}/{latest_blob.name}")
            return data
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to extract data from GCS: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from GCS: {str(e)}")
            return []

    def transform(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform raw tweet data into sentiment scores.

        Args:
            raw_data: List of tweet dictionaries from GCS.

        Returns:
            List of transformed dictionaries ready for BigQuery.
        """
        if not raw_data:
            logger.warning("No raw data provided for transformation.")
            return []

        transformed_data = []
        scores = self.analyzer.analyze_batch(raw_data)
        transformed_data = [
            {
                "ticker": score.ticker,
                "sentiment_score": score.sentiment_score,
                "timestamp": datetime.utcfromtimestamp(score.timestamp),
                "data_point_count": score.data_point_count,
                "source": "X"
            }
            for score in scores
        ]
        logger.info(f"Transformed {len(transformed_data)} records from {len(raw_data)} raw tweets.")
        return transformed_data
        for tweet in raw_data:
            ticker = tweet.get("ticker", "")
            if not ticker:
                logger.debug(f"Skipping tweet with no ticker: {tweet['tweet_id']}")
                continue

            # Perform sentiment analysis
            blob = TextBlob(tweet["text"])
            sentiment_score = blob.sentiment.polarity  # -1.0 to 1.0

            # Convert created_at to timestamp
            try:
                timestamp = int(datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00")).timestamp())
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid timestamp in tweet {tweet['tweet_id']}: {str(e)}")
                continue

            # Create SentimentScore model instance
            score = SentimentScore(
                ticker=ticker,
                sentiment_score=sentiment_score,
                timestamp=timestamp,
                data_point_count=1,  # One tweet per record
                error=None
            )

            if score.is_valid:
                transformed_data.append({
                    "ticker": score.ticker,
                    "sentiment_score": score.sentiment_score,
                    "timestamp": datetime.utcfromtimestamp(score.timestamp),
                    "data_point_count": score.data_point_count,
                    "source": "X"
                })
            else:
                logger.warning(f"Invalid sentiment data for tweet {tweet['tweet_id']}: {score.error}")

        logger.info(f"Transformed {len(transformed_data)} records from {len(raw_data)} raw tweets.")
        return transformed_data

    def load_to_bigquery(self, data: List[Dict[str, Any]]) -> bool:
        """
        Load transformed data into BigQuery.

        Args:
            data: List of transformed dictionaries.

        Returns:
            True if load succeeds, False otherwise.

        Raises:
            gcp_exceptions.GoogleAPIError: If BigQuery insertion fails.
        """
        if not data:
            logger.warning("No data provided for loading into BigQuery.")
            return False

        # Validate data against schema
        valid_data = [row for row in data if validate_schema_compatibility(row)]
        if len(valid_data) < len(data):
            logger.warning(f"Filtered out {len(data) - len(valid_data)} invalid records.")

        table_ref = f"{settings.GCP_PROJECT_ID}.{settings.BQ_DATASET}.{settings.SENTIMENT_TABLE}"
        try:
            errors = self.bq_client.insert_rows_json(table_ref, valid_data)
            if not errors:
                logger.info(f"Successfully loaded {len(valid_data)} records into BigQuery: {table_ref}")
                return True
            else:
                logger.error(f"BigQuery insert errors: {errors}")
                return False
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to load data into BigQuery: {str(e)}")
            return False

    def run(self, interval: int = 300):
        """
        Run the ETL pipeline continuously.

        Args:
            interval: Time in seconds between pipeline runs (default: 300s = 5min).
        """
        logger.info("Starting SentimentPipeline...")
        while True:
            try:
                raw_data = self.extract_from_gcs()
                PROCESS_COUNT.inc(len(raw_data))
                with PROCESS_LATENCY.time():
                    transformed_data = self.transform(raw_data)
                    success = self.load_to_bigquery(transformed_data)
                    if not success:
                        logger.warning("Pipeline run completed with errors.")
            except Exception as e:
                logger.error(f"Pipeline run failed: {str(e)}")
            time.sleep(interval)

if __name__ == "__main__":
    # Example usage
    pipeline = SentimentPipeline()
    pipeline.run(interval=300)  # Run every 5 minutes