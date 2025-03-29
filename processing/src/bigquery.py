# bigquery.py
# Implements BigQuery interaction logic for the Stock Sentiment Analyzer project.
# Provides methods to manage tables and insert/query sentiment data, ensuring robust
# integration with the ETL pipeline.

import logging
from typing import List, Dict, Any, Optional
from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions

# Project imports
from config import settings
from config.logging import logging_config
from data.schema import SENTIMENT_DATA_SCHEMA, create_table_if_not_exists, validate_schema_compatibility

# Configure logging
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

class BigQueryClient:
    """Handles interactions with Google BigQuery for sentiment data."""

    def __init__(self, dataset_id: str = settings.BQ_DATASET, table_id: str = settings.SENTIMENT_TABLE):
        """
        Initialize the BigQuery client.

        Args:
            dataset_id: BigQuery dataset ID (default from settings).
            table_id: BigQuery table ID (default from settings).

        Raises:
            ValueError: If GCP_PROJECT_ID is not set.
        """
        if not settings.GCP_PROJECT_ID:
            raise ValueError("GCP_PROJECT_ID must be set in the environment")

        self.client = bigquery.Client(project=settings.GCP_PROJECT_ID)
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.table_ref = f"{settings.GCP_PROJECT_ID}.{self.dataset_id}.{self.table_id}"

        # Ensure the table exists
        create_table_if_not_exists(self.client, self.dataset_id, self.table_id)
        logger.info(f"BigQueryClient initialized for table: {self.table_ref}")

    def insert_data(self, data: List[Dict[str, Any]]) -> bool:
        """
        Insert data into the BigQuery table.

        Args:
            data: List of dictionaries containing sentiment data.

        Returns:
            True if insertion succeeds, False otherwise.

        Raises:
            gcp_exceptions.GoogleAPIError: If insertion fails unexpectedly.
        """
        if not data or not isinstance(data, list):
            logger.warning("No valid data provided for insertion.")
            return False

        # Validate data against schema
        valid_data = [row for row in data if validate_schema_compatibility(row)]
        if len(valid_data) < len(data):
            logger.warning(f"Filtered out {len(data) - len(valid_data)} invalid records.")

        if not valid_data:
            logger.warning("No valid data to insert after validation.")
            return False

        try:
            errors = self.client.insert_rows_json(self.table_ref, valid_data)
            if not errors:
                logger.info(f"Successfully inserted {len(valid_data)} rows into {self.table_ref}")
                return True
            else:
                logger.error(f"BigQuery insert errors: {errors}")
                return False
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to insert data into BigQuery: {str(e)}")
            return False

    def query_data(self, ticker: str, start_time: int, end_time: int) -> List[Dict[str, Any]]:
        """
        Query sentiment data for a specific ticker within a time range.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            start_time: Start timestamp (Unix epoch in seconds).
            end_time: End timestamp (Unix epoch in seconds).

        Returns:
            List of dictionaries with query results.

        Raises:
            gcp_exceptions.GoogleAPIError: If query fails.
        """
        if not ticker or start_time >= end_time:
            logger.warning(f"Invalid query parameters: ticker={ticker}, start_time={start_time}, end_time={end_time}")
            return []

        query = f"""
            SELECT 
                ticker,
                sentiment_score,
                TIMESTAMP_SECONDS(timestamp) AS timestamp,
                data_point_count,
                source
            FROM `{self.table_ref}`
            WHERE ticker = @ticker
            AND timestamp BETWEEN @start_time AND @end_time
            ORDER BY timestamp ASC
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticker", "STRING", ticker),
                bigquery.ScalarQueryParameter("start_time", "INT64", start_time),
                bigquery.ScalarQueryParameter("end_time", "INT64", end_time),
            ]
        )

        try:
            query_job = self.client.query(query, job_config=job_config)
            results = [
                {
                    "ticker": row["ticker"],
                    "sentiment_score": float(row["sentiment_score"]),
                    "timestamp": int(row["timestamp"].timestamp()),
                    "data_point_count": int(row["data_point_count"]),
                    "source": row["source"]
                }
                for row in query_job.result()
            ]
            logger.info(f"Queried {len(results)} rows for ticker {ticker} from {self.table_ref}")
            return results
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to query BigQuery: {str(e)}")
            return []

    def get_latest_record(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most recent sentiment record for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").

        Returns:
            Dictionary with the latest record, or None if not found.
        """
        if not ticker:
            logger.warning("No ticker provided for latest record query.")
            return None

        query = f"""
            SELECT 
                ticker,
                sentiment_score,
                TIMESTAMP_SECONDS(timestamp) AS timestamp,
                data_point_count,
                source
            FROM `{self.table_ref}`
            WHERE ticker = @ticker
            ORDER BY timestamp DESC
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("ticker", "STRING", ticker)]
        )

        try:
            query_job = self.client.query(query, job_config=job_config)
            result = next(query_job.result(), None)
            if result:
                record = {
                    "ticker": result["ticker"],
                    "sentiment_score": float(result["sentiment_score"]),
                    "timestamp": int(result["timestamp"].timestamp()),
                    "data_point_count": int(result["data_point_count"]),
                    "source": result["source"]
                }
                logger.info(f"Retrieved latest record for ticker {ticker}")
                return record
            logger.info(f"No records found for ticker {ticker}")
            return None
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to query latest record: {str(e)}")
            return None

if __name__ == "__main__":
    # Example usage for testing
    bq_client = BigQueryClient()

    # Sample data
    sample_data = [
        {
            "ticker": "AAPL",
            "sentiment_score": 0.75,
            "timestamp": datetime.utcfromtimestamp(1711500000),  # 2025-03-27 00:00:00 UTC
            "data_point_count": 1,
            "source": "X"
        }
    ]

    # Insert data
    success = bq_client.insert_data(sample_data)
    logger.info(f"Insert succeeded: {success}")

    # Query data
    results = bq_client.query_data("AAPL", 1711496400, 1711507200)
    for row in results:
        logger.info(f"Query result: {row}")

    # Get latest record
    latest = bq_client.get_latest_record("AAPL")
    logger.info(f"Latest record: {latest}")