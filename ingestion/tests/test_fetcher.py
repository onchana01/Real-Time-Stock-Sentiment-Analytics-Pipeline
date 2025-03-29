# test_fetcher.py
# Unit tests for the XDataFetcher class in fetcher.py.
# Verifies the ingestion service's ability to fetch tweets from the X API and upload them to GCS.

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
from google.api_core import exceptions as gcp_exceptions
from ingestion.src.fetcher import XDataFetcher

# Sample data for mocking
SAMPLE_TWEETS = [
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

# Configure logging for test output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def fetcher(monkeypatch):
    """Fixture to create an XDataFetcher instance with mocked dependencies."""
    # Mock settings
    monkeypatch.setattr("config.settings.X_API_KEY", "test_key")
    monkeypatch.setattr("config.settings.X_API_SECRET", "test_secret")
    monkeypatch.setattr("config.settings.GCP_PROJECT_ID", "test_project")

    with patch("tweepy.Client") as mock_client, \
         patch("google.cloud.storage.Client") as mock_storage:
        fetcher = XDataFetcher()
        fetcher.client = mock_client.return_value
        fetcher.storage_client = mock_storage.return_value
        fetcher.bucket = MagicMock()
        yield fetcher

def test_init_fetcher_success(fetcher):
    """Test successful initialization of XDataFetcher."""
    assert fetcher.client is not None
    assert fetcher.storage_client is not None
    assert fetcher.bucket is not None
    logger.info("XDataFetcher initialized successfully in test.")

def test_init_fetcher_missing_credentials(monkeypatch):
    """Test initialization fails when X API credentials are missing."""
    monkeypatch.setattr("config.settings.X_API_KEY", None)
    monkeypatch.setattr("config.settings.X_API_SECRET", "test_secret")
    
    with pytest.raises(ValueError, match="X_API_KEY and X_API_SECRET must be set"):
        XDataFetcher()
    logger.info("XDataFetcher correctly rejected missing credentials.")

def test_fetch_tweets_success(fetcher):
    """Test fetch_tweets with a successful API response."""
    # Mock Tweepy response
    mock_response = Mock()
    mock_response.data = [
        Mock(id=123456789, text="Loving $AAPL today!", created_at="2025-03-27T12:00:00Z", author_id=1),
        Mock(id=987654321, text="$TSLA is skyrocketing!", created_at="2025-03-27T12:01:00Z", author_id=2)
    ]
    mock_response.includes = {"users": [Mock(id=1, username="user1"), Mock(id=2, username="user2")]}
    fetcher.client.search_recent_tweets.return_value = mock_response

    result = fetcher.fetch_tweets("AAPL $AAPL", max_results=10)

    assert len(result) == 2
    assert result[0]["tweet_id"] == 123456789
    assert result[0]["ticker"] == "AAPL"
    assert result[1]["username"] == "user2"
    logger.info("fetch_tweets returned valid data for AAPL.")

def test_fetch_tweets_no_data(fetcher):
    """Test fetch_tweets when no tweets are returned."""
    fetcher.client.search_recent_tweets.return_value = Mock(data=None)

    result = fetcher.fetch_tweets("AAPL $AAPL")

    assert result == []
    logger.info("fetch_tweets correctly handled no data case.")

def test_fetch_tweets_api_error(fetcher):
    """Test fetch_tweets when the X API raises an error."""
    fetcher.client.search_recent_tweets.side_effect = tweepy.TweepyException("API error")

    result = fetcher.fetch_tweets("AAPL $AAPL")

    assert result == []
    logger.info("fetch_tweets handled API error gracefully.")

def test_extract_ticker_valid(fetcher):
    """Test _extract_ticker with valid ticker in text."""
    text = "Loving $AAPL today!"
    ticker = fetcher._extract_ticker(text)

    assert ticker == "AAPL"
    logger.info("extract_ticker correctly extracted AAPL.")

def test_extract_ticker_no_ticker(fetcher):
    """Test _extract_ticker when no ticker is present."""
    text = "Loving tech today!"
    ticker = fetcher._extract_ticker(text)

    assert ticker == ""
    logger.info("extract_ticker returned empty string for no ticker.")

def test_upload_to_gcs_success(fetcher):
    """Test upload_to_gcs with a successful upload."""
    fetcher.bucket.blob.return_value = Mock()
    with patch("json.dumps") as mock_dumps:
        mock_dumps.return_value = '{"data": "test"}'
        uri = fetcher.upload_to_gcs(SAMPLE_TWEETS)

    assert uri.startswith(f"gs://{fetcher.bucket_name}/tweets/")
    fetcher.bucket.blob.assert_called_once()
    logger.info("upload_to_gcs successfully mocked an upload.")

def test_upload_to_gcs_empty_data(fetcher):
    """Test upload_to_gcs with empty data."""
    uri = fetcher.upload_to_gcs([])

    assert uri == ""
    logger.info("upload_to_gcs correctly handled empty data.")

def test_upload_to_gcs_gcs_error(fetcher):
    """Test upload_to_gcs when GCS raises an error."""
    fetcher.bucket.blob.return_value.upload_from_string.side_effect = gcp_exceptions.GoogleAPIError("GCS error")

    uri = fetcher.upload_to_gcs(SAMPLE_TWEETS)

    assert uri == ""
    logger.info("upload_to_gcs handled GCS error gracefully.")

if __name__ == "__main__":
    pytest.main(["-v"])