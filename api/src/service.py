# service.py
# Contains the business logic for the SentimentService API endpoints.
# This module handles querying sentiment data from Google BigQuery and formatting
# it for the gRPC responses, ensuring separation of concerns from the server implementation.

import logging
import os
from typing import Dict, Iterator, Optional
from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions
from google.protobuf.timestamp_pb2 import Timestamp
from data.models import SentimentScore
from data.schema import SENTIMENT_DATA_SCHEMA

# Generated proto module
import sentiment_pb2

# Load configuration
from config import settings
from config.logging import logging_config

# Configure logging
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

class SentimentService:
    """Business logic for retrieving and processing stock sentiment data."""

    def __init__(self):
        logger.info(f"Raw env GCP_PROJECT_ID: {os.getenv('GCP_PROJECT_ID')}")
        logger.info(f"Settings GCP_PROJECT_ID: {settings.GCP_PROJECT_ID}")
        self.bq_client = bigquery.Client(project=settings.GCP_PROJECT_ID)
        self.dataset = settings.BQ_DATASET
        self.table = settings.SENTIMENT_TABLE
        logger.info("SentimentService initialized with BigQuery client.")

    def get_stock_sentiment(
        self, ticker: str, timeframe: int = sentiment_pb2.TIMEFRAME_1H
    ) -> Dict[str, Optional[float]]:
        """
        Retrieve the current sentiment score for a stock ticker over a specified timeframe.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            timeframe: Timeframe enum value (e.g., TIMEFRAME_1H).

        Returns:
            Dict containing sentiment_score (float), timestamp (int), data_point_count (int),
            and optionally an error message (str).
        """
        if not ticker or not ticker.isalnum() or len(ticker) > 5:
            logger.warning(f"Invalid ticker received: {ticker}")
            return {"error": "Ticker must be a valid alphanumeric string (max 5 characters)"}

        # Map Timeframe enum to BigQuery interval
        timeframe_map = {
            sentiment_pb2.TIMEFRAME_1H: "1 HOUR",
            sentiment_pb2.TIMEFRAME_1D: "24 HOUR",
            sentiment_pb2.TIMEFRAME_1W: "7 DAY"
        }
        bq_timeframe = timeframe_map.get(timeframe, "1 HOUR")  # Default to 1 hour

        query = f"""
            SELECT 
                AVG(sentiment_score) AS sentiment_score,
                UNIX_SECONDS(timestamp) AS timestamp,
                COUNT(*) AS data_point_count
            FROM `{self.dataset}.{self.table}`
            WHERE ticker = @ticker
            AND timestamp BETWEEN TIMESTAMP_SECONDS(@start_time) AND TIMESTAMP_SECONDS(@end_time)
            GROUP BY FLOOR(UNIX_SECONDS(timestamp) / @interval_seconds)
            ORDER BY timestamp ASC
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("ticker", "STRING", ticker)]
        )

        try:
            logger.info(f"Querying sentiment for ticker {ticker} over timeframe {bq_timeframe}")
            query_job = self.bq_client.query(query, job_config=job_config)
            result = next(query_job.result(), None)  # Expect one row or none
            if result:
                score = SentimentScore(
                    ticker=ticker,
                    sentiment_score=float(result["sentiment_score"]),
                    timestamp=int(result["timestamp"].timestamp()),
                    data_point_count=int(result["data_point_count"])
                )
                return score.to_dict()
            return SentimentScore(
                ticker=ticker,
                sentiment_score=0.0,
                timestamp=0,
                data_point_count=0,
                error=f"No data available for {ticker} in the last {bq_timeframe}"
            ).to_dict()
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"BigQuery query failed for {ticker}: {str(e)}")
            return {"error": f"Internal server error: {str(e)}"}

    def stream_stock_sentiment(
        self, ticker: str, start_time: Timestamp, end_time: Timestamp, interval: int = sentiment_pb2.INTERVAL_1H
    ) -> Iterator[Dict[str, Optional[float]]]:
        """
        Stream historical sentiment data for a stock ticker over a time range.

        Args:
            ticker: Stock ticker symbol (e.g., "TSLA").
            start_time: Start timestamp (google.protobuf.Timestamp).
            end_time: End timestamp (google.protobuf.Timestamp).
            interval: Interval enum value (e.g., INTERVAL_1H).

        Yields:
            Dict containing sentiment_score (float), timestamp (int), data_point_count (int),
            and optionally an error message (str) for each interval.
        """
        if not ticker or not ticker.isalnum() or len(ticker) > 5:
            logger.warning(f"Invalid ticker received: {ticker}")
            yield {"error": "Ticker must be a valid alphanumeric string (max 5 characters)"}
            return
        if start_time.seconds >= end_time.seconds:
            logger.warning(f"Invalid time range: start_time {start_time.seconds} >= end_time {end_time.seconds}")
            yield {"error": "Start time must be less than end time"}
            return

        interval_map = {
            sentiment_pb2.INTERVAL_1M: 60,
            sentiment_pb2.INTERVAL_1H: 3600,
            sentiment_pb2.INTERVAL_1D: 86400
        }
        interval_seconds = interval_map.get(interval, 3600)

        query = f"""
            SELECT 
                AVG(sentiment_score) AS sentiment_score,
                MIN(UNIX_SECONDS(timestamp)) AS timestamp,
                COUNT(*) AS data_point_count
            FROM `{self.dataset}.{self.table}`
            WHERE ticker = @ticker
            AND timestamp BETWEEN TIMESTAMP_SECONDS(@start_time) AND TIMESTAMP_SECONDS(@end_time)
            GROUP BY FLOOR(UNIX_SECONDS(timestamp) / @interval_seconds)
            ORDER BY timestamp ASC
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticker", "STRING", ticker),
                bigquery.ScalarQueryParameter("start_time", "INT64", start_time.seconds),
                bigquery.ScalarQueryParameter("end_time", "INT64", end_time.seconds),
                bigquery.ScalarQueryParameter("interval_seconds", "INT64", interval_seconds),
            ]
        )

        try:
            logger.info(f"Streaming sentiment for {ticker} from {start_time.seconds} to {end_time.seconds}")
            query_job = self.bq_client.query(query, job_config=job_config)
            for row in query_job.result():
                yield {
                    "ticker": ticker,
                    "sentiment_score": float(row["sentiment_score"]),
                    "timestamp": int(row["timestamp"]),
                    "data_point_count": int(row["data_point_count"])
                }
        except gcp_exceptions.GoogleAPIError as e:
            logger.error(f"BigQuery streaming query failed for {ticker}: {str(e)}")
            yield {"error": f"Internal server error: {str(e)}"}

if __name__ == "__main__":
    # Example usage for testing
    service = SentimentService()
    
    # Test GetStockSentiment
    result = service.get_stock_sentiment("AAPL", sentiment_pb2.TIMEFRAME_1H)
    logger.info(f"GetStockSentiment result: {result}")

    # Test StreamStockSentiment
    start_time = Timestamp(seconds=1711440000)  # 2025-03-26 08:00:00 UTC
    end_time = Timestamp(seconds=1711526400)    # 2025-03-27 08:00:00 UTC
    for data in service.stream_stock_sentiment("TSLA", start_time, end_time, sentiment_pb2.INTERVAL_1H):
        logger.info(f"StreamStockSentiment data: {data}")