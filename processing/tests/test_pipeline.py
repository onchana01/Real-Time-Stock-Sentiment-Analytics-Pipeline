# test_pipeline.py
# Unit tests for the SentimentPipeline class in pipeline.py.
# Verifies the ETL pipeline's ability to extract data from GCS, transform it with sentiment analysis,
# and load it into BigQuery.

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from google.api_core import exceptions as gcp_exceptions
from processing.src.pipeline import SentimentPipeline

# Sample data for mocking
SAMPLE_RAW_DATA = [
    {
        "tweet_id": 123456789,
        "text": "Loving $AAPL today!",
        "created_at": "2025-03-27T12:00:00Z",
        "username": "user1",
        "ticker": "AAPL"
    }
]

SAMPLE_TRANSFORMED_DATA = [
    {
        "ticker": "AAPL",
        "sentiment_score": 0.5,
        "timestamp": datetime.utcfromtimestamp(1711540800),  # 2025-03-27 12:00:00 UTC
        "data_point_count": 1,
        "source": "X"
    }
]

# Configure logging for test output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def pipeline(monkeypatch):
    """Fixture to create a SentimentPipeline instance with mocked dependencies."""
    # Mock settings
    monkeypatch.setattr("config.settings.GCP_PROJECT_ID", "test_project")
    monkeypatch.setattr("config.settings.BQ_DATASET", "test_dataset")
    monkeypatch.setattr("config.settings.SENTIMENT_TABLE", "test_table")

    with patch("google.cloud.storage.Client") as mock_storage, \
         patch("google.cloud.bigquery.Client") as mock_bq, \
         patch("data.schema.create_table_if_not_exists") as mock_create_table:
        pipeline = SentimentPipeline()
        pipeline.storage_client = mock_storage.return_value
        pipeline.bq_client = mock_bq.return_value
        yield pipeline

def test_init_pipeline_success(pipeline):
    """Test successful initialization of SentimentPipeline."""
    assert pipeline.storage_client is not None
    assert pipeline.bq_client is not None
    assert pipeline.bucket_name == "test_project-raw-data"
    pipeline.bq_client.get_table.assert_not_called()  # Handled by create_table_if_not_exists
    logger.info("SentimentPipeline initialized successfully in test.")

def test_extract_from_gcs_success(pipeline):
    """Test extract_from_gcs with a successful GCS response."""
    # Mock GCS response
    mock_blob = Mock()
    mock_blob.download_as_text.return_value = json.dumps(SAMPLE_RAW_DATA)
    mock_blob.name = "tweets/2025-03-27_12-00-00.json"
    pipeline.storage_client.list_blobs.return_value = [mock_blob]

    result = pipeline.extract_from_gcs()

    assert len(result) == 1
    assert result[0]["tweet_id"] == 123456789
    assert result[0]["ticker"] == "AAPL"
    logger.info("extract_from_gcs returned valid data from GCS.")

def test_extract_from_gcs_no_files(pipeline):
    """Test extract_from_gcs when no files are found in GCS."""
    pipeline.storage_client.list_blobs.return_value = []

    result = pipeline.extract_from_gcs()

    assert result == []
    logger.info("extract_from_gcs correctly handled no files case.")

def test_extract_from_gcs_error(pipeline):
    """Test extract_from_gcs when GCS raises an error."""
    pipeline.storage_client.list_blobs.side_effect = gcp_exceptions.GoogleAPIError("GCS error")

    result = pipeline.extract_from_gcs()

    assert result == []
    logger.info("extract_from_gcs handled GCS error gracefully.")

def test_transform_success(pipeline):
    """Test transform with valid raw data."""
    result = pipeline.transform(SAMPLE_RAW_DATA)

    assert len(result) == 1
    assert result[0]["ticker"] == "AAPL"
    assert isinstance(result[0]["sentiment_score"], float)
    assert result[0]["data_point_count"] == 1
    logger.info("transform successfully processed raw data.")

def test_transform_no_data(pipeline):
    """Test transform with no data."""
    result = pipeline.transform([])

    assert result == []
    logger.info("transform correctly handled no data case.")

def test_transform_invalid_timestamp(pipeline):
    """Test transform with invalid timestamp in raw data."""
    invalid_data = SAMPLE_RAW_DATA.copy()
    invalid_data[0]["created_at"] = "invalid_timestamp"

    result = pipeline.transform(invalid_data)

    assert result == []
    logger.info("transform skipped data with invalid timestamp.")

def test_load_to_bigquery_success(pipeline):
    """Test load_to_bigquery with successful insertion."""
    pipeline.bq_client.insert_rows_json.return_value = []  # No errors

    success = pipeline.load_to_bigquery(SAMPLE_TRANSFORMED_DATA)

    assert success is True
    pipeline.bq_client.insert_rows_json.assert_called_once()
    logger.info("load_to_bigquery successfully mocked insertion.")

def test_load_to_bigquery_no_data(pipeline):
    """Test load_to_bigquery with no data."""
    success = pipeline.load_to_bigquery([])

    assert success is False
    pipeline.bq_client.insert_rows_json.assert_not_called()
    logger.info("load_to_bigquery correctly handled no data case.")

def test_load_to_bigquery_error(pipeline):
    """Test load_to_bigquery when BigQuery raises an error."""
    pipeline.bq_client.insert_rows_json.return_value = [{"error": "Insert failed"}]

    success = pipeline.load_to_bigquery(SAMPLE_TRANSFORMED_DATA)

    assert success is False
    logger.info("load_to_bigquery handled BigQuery error gracefully.")

if __name__ == "__main__":
    pytest.main(["-v"])