# sentiment.py
# Implements sentiment analysis logic for the Stock Sentiment Analyzer project.
# Analyzes text data (e.g., tweets) to compute sentiment scores, designed for integration
# with the ETL pipeline and extensible to support advanced models.

import logging
from typing import Optional, Dict, Any
from textblob import TextBlob

# Project imports
from config.logging import logging_config
from data.models import SentimentScore

# Configure logging
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Performs sentiment analysis on text data."""

    def __init__(self):
        """Initialize the sentiment analyzer."""
        logger.info("SentimentAnalyzer initialized with TextBlob.")

    def analyze_text(self, text: str, ticker: str, timestamp: int) -> Optional[SentimentScore]:
        """
        Analyze the sentiment of a given text and return a SentimentScore object.

        Args:
            text: The text to analyze (e.g., tweet content).
            ticker: The stock ticker associated with the text.
            timestamp: Unix epoch timestamp in seconds for the text.

        Returns:
            SentimentScore object if valid, None if analysis fails or text is invalid.
        """
        if not text or not isinstance(text, str):
            logger.warning(f"Invalid text provided for analysis: {text}")
            return None

        if not ticker:
            logger.warning("No ticker provided for sentiment analysis.")
            return None

        try:
            # Use TextBlob for sentiment analysis
            blob = TextBlob(text)
            sentiment_score = blob.sentiment.polarity  # Range: -1.0 (negative) to 1.0 (positive)

            # Create SentimentScore instance
            score = SentimentScore(
                ticker=ticker,
                sentiment_score=sentiment_score,
                timestamp=timestamp,
                data_point_count=1  # One text item per analysis
            )

            if score.is_valid:
                logger.debug(f"Sentiment analyzed for ticker {ticker}: {sentiment_score}")
                return score
            else:
                logger.warning(f"Invalid sentiment score generated: {score.error}")
                return None
        except Exception as e:
            logger.error(f"Failed to analyze sentiment for text '{text}': {str(e)}")
            return None

    def analyze_batch(self, data: List[Dict[str, Any]]) -> List[SentimentScore]:
        """
        Analyze sentiment for a batch of text data.

        Args:
            data: List of dictionaries containing 'text', 'ticker', and 'timestamp' keys.

        Returns:
            List of valid SentimentScore objects.
        """
        if not data or not isinstance(data, list):
            logger.warning("No valid data provided for batch analysis.")
            return []

        results = []
        for item in data:
            text = item.get("text", "")
            ticker = item.get("ticker", "")
            timestamp = item.get("timestamp")

            # Convert timestamp if necessary (assuming it might be ISO format or int)
            if isinstance(timestamp, str):
                try:
                    timestamp = int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp())
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid timestamp in batch item: {timestamp}, error: {str(e)}")
                    continue
            if not isinstance(timestamp, int):
                logger.warning(f"Skipping item with invalid timestamp: {timestamp}")
                continue

            score = self.analyze_text(text, ticker, timestamp)
            if score:
                results.append(score)

        logger.info(f"Analyzed sentiment for {len(results)} out of {len(data)} items in batch.")
        return results

if __name__ == "__main__":
    # Example usage for testing
    analyzer = SentimentAnalyzer()

    # Single text analysis
    sample_text = "Loving $AAPL today!"
    sample_ticker = "AAPL"
    sample_timestamp = 1711500000  # 2025-03-27 00:00:00 UTC
    score = analyzer.analyze_text(sample_text, sample_ticker, sample_timestamp)
    if score:
        logger.info(f"Single analysis result: {score.to_dict()}")

    # Batch analysis
    sample_batch = [
        {
            "text": "Loving $AAPL today!",
            "ticker": "AAPL",
            "timestamp": 1711500000
        },
        {
            "text": "$TSLA is terrible!",
            "ticker": "TSLA",
            "timestamp": "2025-03-27T12:01:00Z"
        },
        {
            "text": "No ticker here",
            "ticker": "",
            "timestamp": 1711500000
        }
    ]
    batch_results = analyzer.analyze_batch(sample_batch)
    for result in batch_results:
        logger.info(f"Batch analysis result: {result.to_dict()}")