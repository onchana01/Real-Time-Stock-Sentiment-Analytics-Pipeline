# models.py
# Defines data models for the Stock Sentiment Analyzer project.
# These models represent structured data entities used across ingestion, processing,
# and API services, ensuring consistency and type safety.

from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime
import logging as logging_module
from logging.config import dictConfig

# Configure logging
from config.logging import logging_config
dictConfig(logging_config)
logger = logging_module.getLogger(__name__)

@dataclass
class SentimentScore:
    """
    Represents a sentiment score for a stock ticker at a specific point in time.

    Attributes:
        ticker: Stock ticker symbol (e.g., "AAPL").
        sentiment_score: Sentiment value between -1.0 (negative) and 1.0 (positive).
        timestamp: Unix epoch timestamp in seconds when the sentiment was recorded.
        data_point_count: Number of data points (e.g., tweets) used to compute the score.
        error: Optional error message if the sentiment data is invalid or unavailable.
    """
    def __init__(self, ticker="", sentiment_score=0.0, timestamp=0, data_point_count=0, error=None):
        self.ticker = ticker
        self.sentiment_score = sentiment_score
        self.timestamp = timestamp
        self.data_point_count = data_point_count
        self.error = error
        if not self.ticker or not self.ticker.isalnum() or len(self.ticker) > 5:
            logger.warning(f"Invalid ticker in SentimentScore: {self.ticker}")
            self.error = "Ticker must be a non-empty string (max 5 characters)"
    ticker: str
    sentiment_score: float
    timestamp: int
    data_point_count: int
    error: Optional[str] = None

    def __post_init__(self):
        """Validate and normalize the model's attributes after initialization."""
        if not self.ticker or not isinstance(self.ticker, str) or len(self.ticker) > 5:
            self.error = "Ticker must be a non-empty string (max 5 characters)"
            logger.warning(f"Invalid ticker in SentimentScore: {self.ticker}")
        if not -1.0 <= self.sentiment_score <= 1.0:
            self.error = "Sentiment score must be between -1.0 and 1.0"
            logger.warning(f"Invalid sentiment_score: {self.sentiment_score}")
        if not isinstance(self.timestamp, int) or self.timestamp < 0:
            self.error = "Timestamp must be a non-negative integer"
            logger.warning(f"Invalid timestamp: {self.timestamp}")
        if not isinstance(self.data_point_count, int) or self.data_point_count < 0:
            self.error = "Data point count must be a non-negative integer"
            logger.warning(f"Invalid data_point_count: {self.data_point_count}")

    @property
    def is_valid(self) -> bool:
        """Check if the sentiment score is valid (no error)."""
        return self.error is None

    @classmethod
    def from_dict(cls, data: dict) -> "SentimentScore":
        """
        Create a SentimentScore instance from a dictionary.

        Args:
            data: Dictionary with keys matching SentimentScore attributes.

        Returns:
            A SentimentScore instance.
        """
        return cls(
            ticker=data.get("ticker", ""),
            sentiment_score=data.get("sentiment_score", 0.0),
            timestamp=data.get("timestamp", 0),
            data_point_count=data.get("data_point_count", 0),
            error=data.get("error")
        )

    def to_dict(self) -> dict:
        """
        Convert the SentimentScore instance to a dictionary.

        Returns:
            A dictionary representation of the instance.
        """
        return asdict(self)

    def human_readable_timestamp(self) -> str:
        """
        Convert the timestamp to a human-readable string.

        Returns:
            A formatted datetime string (e.g., "2025-03-27 12:00:00").
        """
        return datetime.utcfromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    # Example usage for testing
    valid_score = SentimentScore(
        ticker="AAPL",
        sentiment_score=0.75,
        timestamp=1711500000,  # 2025-03-27 00:00:00 UTC
        data_point_count=50
    )
    logger.info(f"Valid SentimentScore: {valid_score.to_dict()}")
    logger.info(f"Human-readable timestamp: {valid_score.human_readable_timestamp()}")

    invalid_score = SentimentScore(
        ticker="INVALID_TICKER",
        sentiment_score=2.0,
        timestamp=-1,
        data_point_count=-10
    )
    logger.info(f"Invalid SentimentScore: {invalid_score.to_dict()}")
    assert not invalid_score.is_valid, "Invalid score should not be valid"