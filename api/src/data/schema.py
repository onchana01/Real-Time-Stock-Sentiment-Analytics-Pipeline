# schema.py
# Defines the BigQuery schema for the Stock Sentiment Analyzer project.
# This schema is used to create and manage the sentiment_data table, ensuring
# consistency in data storage and retrieval for sentiment analysis.

from google.cloud import bigquery
import logging

# Configure logging
from config.logging import logging_config
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

# BigQuery schema definition for the sentiment_data table
SENTIMENT_DATA_SCHEMA = [
    bigquery.SchemaField(
        name="ticker",
        field_type="STRING",
        mode="REQUIRED",
        description="Stock ticker symbol (e.g., 'AAPL' for Apple Inc.). Max length: 5 characters."
    ),
    bigquery.SchemaField(
        name="sentiment_score",
        field_type="FLOAT",
        mode="REQUIRED",
        description="Sentiment score between -1.0 (negative) and 1.0 (positive), computed from alternative data."
    ),
    bigquery.SchemaField(
        name="timestamp",
        field_type="TIMESTAMP",
        mode="REQUIRED",
        description="Timestamp of when the sentiment data was recorded (UTC)."
    ),
    bigquery.SchemaField(
        name="data_point_count",
        field_type="INTEGER",
        mode="REQUIRED",
        description="Number of data points (e.g., tweets) used to calculate the sentiment score."
    ),
    bigquery.SchemaField(
        name="source",
        field_type="STRING",
        mode="NULLABLE",
        description="Source of the sentiment data (e.g., 'X' for Twitter). Optional metadata."
    )
]

def create_table_if_not_exists(client: bigquery.Client, dataset_id: str, table_id: str) -> None:
    """
    Create the sentiment_data table in BigQuery if it does not already exist.

    Args:
        client: BigQuery client instance.
        dataset_id: The ID of the dataset (e.g., 'sentiment_dataset').
        table_id: The ID of the table (e.g., 'sentiment_data').

    Raises:
        google.api_core.exceptions.GoogleAPIError: If table creation fails.
    """
    table_ref = f"{client.project}.{dataset_id}.{table_id}"
    table = bigquery.Table(table_ref, schema=SENTIMENT_DATA_SCHEMA)

    try:
        # Check if table exists
        client.get_table(table)
        logger.info(f"Table {table_ref} already exists.")
    except bigquery.NotFound:
        # Create the table if it doesn't exist
        table = client.create_table(table)
        logger.info(f"Created table {table_ref} with schema: {SENTIMENT_DATA_SCHEMA}")
    except Exception as e:
        logger.error(f"Failed to create table {table_ref}: {str(e)}")
        raise

def validate_schema_compatibility(data: dict) -> bool:
    """
    Validate that a data dictionary matches the SENTIMENT_DATA_SCHEMA.

    Args:
        data: Dictionary containing sentiment data to validate.

    Returns:
        bool: True if the data matches the schema, False otherwise.
    """
    required_fields = {"ticker", "sentiment_score", "timestamp", "data_point_count"}
    optional_fields = {"source"}

    # Check for required fields
    if not all(field in data for field in required_fields):
        missing = required_fields - set(data.keys())
        logger.warning(f"Data missing required fields: {missing}")
        return False

    # Validate field types
    if not isinstance(data["ticker"], str) or len(data["ticker"]) > 5:
        logger.warning(f"Invalid ticker: {data['ticker']}")
        return False
    if not isinstance(data["sentiment_score"], (int, float)) or not -1.0 <= data["sentiment_score"] <= 1.0:
        logger.warning(f"Invalid sentiment_score: {data['sentiment_score']}")
        return False
    if not isinstance(data["timestamp"], (int, float)):  # Allow float for conversion to TIMESTAMP
        logger.warning(f"Invalid timestamp: {data['timestamp']}")
        return False
    if not isinstance(data["data_point_count"], int) or data["data_point_count"] < 0:
        logger.warning(f"Invalid data_point_count: {data['data_point_count']}")
        return False
    if "source" in data and not isinstance(data["source"], str):
        logger.warning(f"Invalid source: {data['source']}")
        return False

    return True

if __name__ == "__main__":
    # Example usage for testing
    from config import settings

    # Initialize BigQuery client
    bq_client = bigquery.Client(project=settings.GCP_PROJECT_ID)

    # Create table
    create_table_if_not_exists(bq_client, settings.BQ_DATASET, settings.SENTIMENT_TABLE)

    # Test schema validation
    valid_data = {
        "ticker": "AAPL",
        "sentiment_score": 0.75,
        "timestamp": 1711500000,  # 2025-03-27 00:00:00 UTC
        "data_point_count": 50,
        "source": "X"
    }
    invalid_data = {
        "ticker": "INVALID_TICKER",
        "sentiment_score": 2.0,
        "timestamp": "not_a_timestamp",
        "data_point_count": -1
    }

    logger.info(f"Valid data test: {validate_schema_compatibility(valid_data)}")
    logger.info(f"Invalid data test: {validate_schema_compatibility(invalid_data)}")