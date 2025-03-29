# test_service.py
# Unit and integration tests for the SentimentService class in service.py.
# Ensures the business logic for stock sentiment retrieval and streaming works as expected.

import pytest
import logging
from unittest.mock import Mock, patch
from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions

# Import the service to test
from api.src.service import SentimentService

# Sample data for mocking BigQuery responses
SAMPLE_SENTIMENT_ROW = {
    "sentiment_score": 0.75,
    "timestamp": 1711500000,  # Example Unix timestamp (2025-03-27 00:00:00 UTC)
    "data_point_count": 50
}

SAMPLE_STREAM_ROWS = [
    {"sentiment_score": 0.5, "timestamp": 1711500000, "data_point_count": 30},
    {"sentiment_score": -0.2, "timestamp": 1711503600, "data_point_count": 20},
]

# Configure logging for test output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def sentiment_service():
    """Fixture to create a SentimentService instance with a mocked BigQuery client."""
    with patch("google.cloud.bigquery.Client") as mock_bq_client:
        service = SentimentService()
        service.bq_client = mock_bq_client.return_value
        yield service

def test_init_sentiment_service(sentiment_service):
    """Test that SentimentService initializes correctly with BigQuery client."""
    assert sentiment_service.bq_client is not None
    assert sentiment_service.dataset == "your_dataset"  # Replace with actual settings value
    assert sentiment_service.table == "sentiment_data"
    logger.info("SentimentService initialized successfully in test.")

def test_get_stock_sentiment_valid_request(sentiment_service):
    """Test get_stock_sentiment with a valid ticker and timeframe."""
    # Mock BigQuery query result
    mock_query_job = Mock()
    mock_query_job.result.return_value = iter([Mock(**SAMPLE_SENTIMENT_ROW)])
    sentiment_service.bq_client.query.return_value = mock_query_job

    result = sentiment_service.get_stock_sentiment("AAPL", "1h")

    assert "sentiment_score" in result
    assert result["sentiment_score"] == 0.75
    assert result["timestamp"] == 1711500000
    assert result["data_point_count"] == 50
    assert "error" not in result
    logger.info("get_stock_sentiment returned valid data for AAPL.")

def test_get_stock_sentiment_invalid_ticker(sentiment_service):
    """Test get_stock_sentiment with an invalid ticker."""
    result = sentiment_service.get_stock_sentiment("", "1h")

    assert "error" in result
    assert result["error"] == "Ticker must be a valid alphanumeric string (max 5 characters)"
    assert "sentiment_score" not in result
    logger.info("get_stock_sentiment correctly rejected empty ticker.")

def test_get_stock_sentiment_no_data(sentiment_service):
    """Test get_stock_sentiment when no data is found."""
    # Mock BigQuery query with no results
    mock_query_job = Mock()
    mock_query_job.result.return_value = iter([])
    sentiment_service.bq_client.query.return_value = mock_query_job

    result = sentiment_service.get_stock_sentiment("AAPL", "1h")

    assert "error" in result
    assert result["error"] == "No data available for AAPL in the last 1h"
    assert "sentiment_score" not in result
    logger.info("get_stock_sentiment handled no data case correctly.")

def test_get_stock_sentiment_bigquery_error(sentiment_service):
    """Test get_stock_sentiment when BigQuery raises an error."""
    # Mock BigQuery query to raise an error
    sentiment_service.bq_client.query.side_effect = gcp_exceptions.GoogleAPIError("Query failed")

    result = sentiment_service.get_stock_sentiment("AAPL", "1h")

    assert "error" in result
    assert "Internal server error" in result["error"]
    logger.info("get_stock_sentiment handled BigQuery error gracefully.")

def test_stream_stock_sentiment_valid_request(sentiment_service):
    """Test stream_stock_sentiment with a valid request."""
    # Mock BigQuery query result for streaming
    mock_query_job = Mock()
    mock_query_job.result.return_value = iter([Mock(**row) for row in SAMPLE_STREAM_ROWS])
    sentiment_service.bq_client.query.return_value = mock_query_job

    result = list(sentiment_service.stream_stock_sentiment("TSLA", 1711496400, 1711507200, "1h"))

    assert len(result) == 2
    assert result[0]["sentiment_score"] == 0.5
    assert result[0]["timestamp"] == 1711500000
    assert result[0]["data_point_count"] == 30
    assert result[1]["sentiment_score"] == -0.2
    assert "error" not in result[0]
    logger.info("stream_stock_sentiment streamed valid data for TSLA.")

def test_stream_stock_sentiment_invalid_time_range(sentiment_service):
    """Test stream_stock_sentiment with an invalid time range."""
    result = list(sentiment_service.stream_stock_sentiment("TSLA", 1711507200, 1711496400, "1h"))

    assert len(result) == 1
    assert "error" in result[0]
    assert result[0]["error"] == "Start time must be less than end time"
    logger.info("stream_stock_sentiment rejected invalid time range.")

def test_stream_stock_sentiment_unsupported_interval(sentiment_service):
    """Test stream_stock_sentiment with an unsupported interval."""
    result = list(sentiment_service.stream_stock_sentiment("TSLA", 1711496400, 1711507200, "5h"))

    assert len(result) == 1
    assert "error" in result[0]
    assert "Unsupported interval" in result[0]["error"]
    logger.info("stream_stock_sentiment rejected unsupported interval.")

def test_stream_stock_sentiment_bigquery_error(sentiment_service):
    """Test stream_stock_sentiment when BigQuery raises an error."""
    # Mock BigQuery query to raise an error
    sentiment_service.bq_client.query.side_effect = gcp_exceptions.GoogleAPIError("Streaming failed")

    result = list(sentiment_service.stream_stock_sentiment("TSLA", 1711496400, 1711507200, "1h"))

    assert len(result) == 1
    assert "error" in result[0]
    assert "Internal server error" in result[0]["error"]
    logger.info("stream_stock_sentiment handled BigQuery error in stream.")

if __name__ == "__main__":
    pytest.main(["-v"])