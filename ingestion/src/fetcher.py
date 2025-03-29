# fetcher.py
# Implements the data ingestion service for the Stock Sentiment Analyzer project.
# Fetches real-time tweets from the X API, processes them into a structured format,
# and uploads the raw data to Google Cloud Storage for further processing.

import logging
import json
import time
from typing import List, Dict, Any
from datetime import datetime
import tweepy
from google.cloud import storage
from google.api_core import exceptions as gcp_exceptions
from ingestion.src.storage import GCSStorage
from prometheus_client import Counter, Histogram, start_http_server

# Project imports
from config import settings
from config.logging import logging_config
from data.models import SentimentScore  # For reference, though not directly used here

# Configure logging
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

FETCH_COUNT = Counter('ingestion_fetch_total', 'Total tweet fetches', ['ticker'])
FETCH_LATENCY = Histogram('ingestion_fetch_latency_seconds', 'Fetch latency', ['ticker'])

class XDataFetcher:
    """Fetches and processes real-time data from the X API."""

    def __init__(self):
        """Initialize the fetcher with X API credentials and GCS client."""
        if not settings.X_API_KEY or not settings.X_API_SECRET:
            raise ValueError("X_API_KEY and X_API_SECRET must be set in the environment")

        # Initialize Tweepy client (using API v2)
        self.client = tweepy.Client(
            consumer_key=settings.X_API_KEY,
            consumer_secret=settings.X_API_SECRET,
            wait_on_rate_limit=True
        )

        self.gcs_storage = GCSStorage()
        start_http_server(8000)  # Expose metrics on port 8000
        logger.info("XDataFetcher initialized with metrics server.")
        
        # Initialize GCS client
        self.storage_client = storage.Client(project=settings.GCP_PROJECT_ID)
        self.bucket_name = f"{settings.GCP_PROJECT_ID}-raw-data"
        self.bucket = self._get_or_create_bucket()
        
        logger.info("XDataFetcher initialized successfully.")

    def _get_or_create_bucket(self) -> storage.Bucket:
        """Get or create the GCS bucket for raw data storage."""
        try:
            bucket = self.storage_client.get_bucket(self.bucket_name)
            logger.info(f"Using existing GCS bucket: {self.bucket_name}")
        except gcp_exceptions.NotFound:
            bucket = self.storage_client.create_bucket(self.bucket_name, location="US")
            logger.info(f"Created GCS bucket: {self.bucket_name}")
        return bucket

    def fetch_tweets(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch recent tweets matching the query from the X API.

        Args:
            query: Search query (e.g., "AAPL $AAPL -filter:retweets").
            max_results: Maximum number of tweets to fetch (default: 100).

        Returns:
            List of dictionaries containing tweet data.
        """
        try:
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["created_at", "text"],
                expansions=["author_id"],
                user_fields=["username"]
            )
            
            if not tweets.data:
                logger.warning(f"No tweets found for query: {query}")
                return []
            
            ticker = query.split()[0]  # Simplified ticker extraction
            FETCH_COUNT.labels(ticker=ticker).inc()
            with FETCH_LATENCY.labels(ticker=ticker).time():
                tweets = self.client.search_recent_tweets(
                    query=query,
                    max_results=max_results,
                    tweet_fields=["created_at", "text"],
                    expansions=["author_id"],
                    user_fields=["username"]
                )
            
            # Process tweet data
            results = []
            user_map = {user.id: user.username for user in tweets.includes.get("users", [])}
            for tweet in tweets.data:
                results.append({
                    "tweet_id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat(),
                    "username": user_map.get(tweet.author_id, "unknown"),
                    "ticker": self._extract_ticker(tweet.text)
                })
            
            logger.info(f"Fetched {len(results)} tweets for query: {query}")
            return results
        except tweepy.TweepyException as e:
            logger.error(f"Failed to fetch tweets: {str(e)}")
            return []

    def _extract_ticker(self, text: str) -> str:
        """
        Extract the stock ticker from tweet text (simplified logic).

        Args:
            text: Tweet content.

        Returns:
            Extracted ticker or empty string if not found.
        """
        # Simplified: Look for $ followed by 1-5 uppercase letters
        import re
        match = re.search(r"\$[A-Z]{1,5}\b", text)
        return match.group(0)[1:] if match else ""  # Remove the $ prefix

    def upload_to_gcs(self, data: List[Dict[str, Any]], prefix: str = "tweets") -> str:
        """
        Upload tweet data to Google Cloud Storage as a JSON file.

        Args:
            data: List of tweet dictionaries to upload.
            prefix: Prefix for the GCS object name (default: "tweets").

        Returns:
            GCS blob URI (e.g., "gs://bucket/tweets/2025-03-27_12-00-00.json").
        """
        if not data:
            logger.warning("No data to upload to GCS.")
            return ""

        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        blob_name = f"{prefix}/{timestamp}.json"
        blob = self.bucket.blob(blob_name)

        try:
            blob.upload_from_string(json.dumps(data, indent=2), content_type="application/json")
            uri = f"gs://{self.bucket_name}/{blob_name}"
            logger.info(f"Uploaded {len(data)} records to GCS: {uri}")
            return uri
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"Failed to upload to GCS: {str(e)}")
            return ""

    def run(self, tickers: List[str], interval: int = 300):
        """
        Continuously fetch and store tweets for specified tickers.

        Args:
            tickers: List of stock tickers to monitor (e.g., ["AAPL", "TSLA"]).
            interval: Time in seconds between fetches (default: 300s = 5min).
        """
        logger.info(f"Starting ingestion service for tickers: {tickers}")
        while True:
            for ticker in tickers:
                query = f"{ticker} ${ticker} -filter:retweets -filter:replies lang:en"
                tweets = self.fetch_tweets(query)
                if tweets:
                    self.upload_to_gcs(tweets)
            time.sleep(interval)

if __name__ == "__main__":
    # Example usage
    fetcher = XDataFetcher()
    tickers_to_monitor = ["AAPL", "TSLA", "MSFT"]
    fetcher.run(tickers_to_monitor, interval=300)  # Run every 5 minutes