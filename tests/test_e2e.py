# test_e2e.py
# End-to-end and integration tests for the Stock Sentiment Analyzer project.
# Verifies the complete workflow: ingestion from X API, processing into BigQuery,
# and serving via the gRPC API.

import pytest
import logging
import grpc
from unittest.mock import patch, Mock
from datetime import datetime
import time
import json
from google.cloud import storage, bigquery
import tweepy

# Project imports
from ingestion.src.fetcher import XDataFetcher
from processing.src.pipeline import SentimentPipeline
from api.src.server import SentimentServiceServicer
import sentiment_pb2
import sentiment_pb2_grpc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample data for testing
SAMPLE_TWEET = {
    "tweet_id": 123456789,
    "text": "Loving $AAPL today!",
    "created_at": "2025-03-27T12:00:00Z",
    "username": "user1",
    "ticker": "AAPL"
}

SAMPLE_TRANSFORMED = {
    "ticker": "AAPL",
    "sentiment_score": 0.5,  # Mocked TextBlob result
    "timestamp": datetime.utcfromtimestamp(1711540800),  # 2025-03-27 12:00:00 UTC
    "data_point_count": 1,
    "source": "X"
}

@pytest.fixture(scope="module")
def grpc_channel():
    """Fixture to set up a gRPC channel for API testing."""
    with grpc.insecure_channel("localhost:50051") as channel:
        yield channel

@pytest.fixture
def mock_dependencies(monkeypatch):
    """Fixture to mock external dependencies for E2E testing."""
    # Mock settings
    monkeypatch.setattr("config.settings.GCP_PROJECT_ID", "test_project")
    monkeypatch.setattr("config.settings.BQ_DATASET", "test_dataset")
    monkeypatch.setattr("config.settings.SENTIMENT_TABLE", "test_table")
    monkeypatch.setattr("config.settings.X_API_KEY", "test_key")
    monkeypatch.setattr("config.settings.X_API_SECRET", "test_secret")

    # Mock external services
    with patch("tweepy.Client") as mock_tweepy, \
         patch("google.cloud.storage.Client") as mock_storage, \
         patch("google.cloud.bigquery.Client") as mock_bq, \
         patch("data.schema.create_table_if_not_exists") as mock_create_table:
        # Mock Tweepy response
        mock_response = Mock()
        mock_response.data = [Mock(id=SAMPLE_TWEET["tweet_id"], text=SAMPLE_TWEET["text"],
                                  created_at=SAMPLE_TWEET["created_at"], author_id=1)]
        mock_response.includes = {"users": [Mock(id=1, username=SAMPLE_TWEET["username"])]}
        mock_tweepy.return_value.search_recent_tweets.return_value = mock_response

        # Mock GCS
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_blob.download_as_text.return_value = json.dumps([SAMPLE_TWEET])
        mock_storage.return_value.list_blobs.return_value = [mock_blob]
        mock_storage.return_value.get_bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Mock BigQuery
        mock_bq.return_value.insert_rows_json.return_value = []  # No errors
        mock_bq.return_value.query.return_value.result.return_value = [
            Mock(ticker="AAPL", sentiment_score=0.5, timestamp=1711540800, data_point_count=1, source="X")
        ]

        yield {
            "mock_tweepy": mock_tweepy,
            "mock_storage": mock_storage,
            "mock_bq": mock_bq
        }

def test_e2e_full_workflow(mock_dependencies, grpc_channel):
    """Test the full E2E workflow: ingestion -> processing -> API serving."""
    # Step 1: Ingestion
    fetcher = XDataFetcher()
    tweets = fetcher.fetch_tweets("AAPL $AAPL")
    assert len(tweets) == 1
    assert tweets[0]["ticker"] == "AAPL"
    uri = fetcher.upload_to_gcs(tweets)
    assert uri.startswith("gs://test_project-raw-data/tweets/")
    logger.info("Ingestion step completed successfully.")

    # Step 2: Processing
    pipeline = SentimentPipeline()
    raw_data = pipeline.extract_from_gcs()
    assert len(raw_data) == 1
    transformed_data = pipeline.transform(raw_data)
    assert len(transformed_data) == 1
    assert transformed_data[0]["ticker"] == "AAPL"
    success = pipeline.load_to_bigquery(transformed_data)
    assert success is True
    logger.info("Processing step completed successfully.")

    # Step 3: API serving (mocked servicer for simplicity)
    with patch.object(SentimentServiceServicer, '_query_sentiment', return_value={
        "sentiment_score": 0.5,
        "timestamp": 1711540800,
        "data_point_count": 1
    }):
        stub = sentiment_pb2_grpc.SentimentServiceStub(grpc_channel)
        request = sentiment_pb2.StockSentimentRequest(ticker="AAPL", timeframe="1h")
        response = stub.GetStockSentiment(request)
        assert response.ticker == "AAPL"
        assert response.sentiment_score == 0.5
        assert response.data_point_count == 1
        assert not response.error
        logger.info("API serving step completed successfully.")

def test_integration_ingestion_to_processing(mock_dependencies):
    """Test integration between ingestion and processing."""
    # Ingestion
    fetcher = XDataFetcher()
    tweets = fetcher.fetch_tweets("AAPL $AAPL")
    fetcher.upload_to_gcs(tweets)

    # Processing
    pipeline = SentimentPipeline()
    raw_data = pipeline.extract_from_gcs()
    transformed_data = pipeline.transform(raw_data)
    success = pipeline.load_to_bigquery(transformed_data)

    assert len(raw_data) == 1
    assert len(transformed_data) == 1
    assert success is True
    logger.info("Integration test from ingestion to processing succeeded.")

def test_integration_processing_to_api(mock_dependencies, grpc_channel):
    """Test integration between processing and API serving."""
    # Processing
    pipeline = SentimentPipeline()
    pipeline.load_to_bigquery([SAMPLE_TRANSFORMED])

    # API serving (mocked servicer)
    with patch.object(SentimentServiceServicer, '_query_sentiment', return_value={
        "sentiment_score": 0.5,
        "timestamp": 1711540800,
        "data_point_count": 1
    }):
        stub = sentiment_pb2_grpc.SentimentServiceStub(grpc_channel)
        request = sentiment_pb2.StockSentimentRequest(ticker="AAPL", timeframe="1h")
        response = stub.GetStockSentiment(request)
        assert response.ticker == "AAPL"
        assert response.sentiment_score == 0.5
        logger.info("Integration test from processing to API succeeded.")

if __name__ == "__main__":
    pytest.main(["-v"])