import grpc
import os
import logging
from concurrent import futures
import json
from datetime import datetime
import tweepy
from textblob import TextBlob

import sentiment_pb2
import sentiment_pb2_grpc

from config import settings
from config.logging import logging_config
from service import SentimentService
from data.models import SentimentScore
from prometheus_client import Counter, Histogram, start_http_server
from google.cloud import bigquery, storage, monitoring_v3

logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter('sentiment_requests_total', 'Total gRPC requests', ['method'])
REQUEST_LATENCY = Histogram('sentiment_request_latency_seconds', 'Request latency', ['method'])

gcs_client = storage.Client(project=settings.GCP_PROJECT_ID)
bq_client = bigquery.Client(project=settings.GCP_PROJECT_ID)

# X API V2 Client
client = tweepy.Client(
    consumer_key=os.getenv("X_API_KEY"),
    consumer_secret=os.getenv("X_API_SECRET"),
    access_token=os.getenv("X_ACCESS_TOKEN"),
    access_token_secret=os.getenv("X_ACCESS_SECRET")
)

class SentimentServiceServicer(sentiment_pb2_grpc.SentimentServiceServicer):
    def __init__(self):
        self.service = SentimentService()
        self.bq_client = bigquery.Client(project=settings.GCP_PROJECT_ID)
        self.dataset = settings.BQ_DATASET
        self.table = settings.SENTIMENT_TABLE
        logger.info("SentimentServiceServicer initialized with BigQuery client.")

    def GetStockSentiment(self, request, context):
        logger.info(f"Received GetStockSentiment request for ticker: {request.ticker}")
        REQUEST_COUNT.labels(method='GetStockSentiment').inc()
        with REQUEST_LATENCY.labels(method='GetStockSentiment').time():
            if not request.ticker:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Ticker is required")
                return sentiment_pb2.SentimentResponse()

            timeframe = request.timeframe if request.timeframe else sentiment_pb2.TIMEFRAME_1H
            result = self.service.get_stock_sentiment(request.ticker, timeframe)
            score = SentimentScore.from_dict(result)
            return sentiment_pb2.SentimentResponse(
                ticker=score.ticker,
                sentiment_score=score.sentiment_score,
                timestamp=score.timestamp,
                data_point_count=score.data_point_count,
                error=score.error or ""
            )
    def log_metric(self, metric_name, value):
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{settings.GCP_PROJECT_ID}"
        series = monitoring_v3.TimeSeries()
        series.metric.type = f'custom.googleapis.com/sentiment/{metric_name}'
        series.resource.type = 'global'
        point = series.points.add()
        point.value.double_value = value
        point.interval.end_time.GetCurrentTime()
        client.create_time_series(name=project_name, time_series=[series])
        
    def StreamStockSentiment(self, request, context):
        logger.info(f"Received StreamStockSentiment request for ticker: {request.ticker}")
        REQUEST_COUNT.labels(method='StreamStockSentiment').inc()
        with REQUEST_LATENCY.labels(method='StreamStockSentiment').time():
            ticker = request.ticker
            start_time = request.start_time.ToDatetime().isoformat() + "Z" if hasattr(request.start_time, 'ToDatetime') else request.start_time
            end_time = request.end_time.ToDatetime().isoformat() + "Z" if hasattr(request.end_time, 'ToDatetime') else request.end_time
            interval = request.interval if request.interval else sentiment_pb2.INTERVAL_1H

            try:
                start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
                end_dt = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError as e:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f"Invalid time format: {str(e)}")
                return

            if not ticker or start_dt >= end_dt:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Invalid ticker or time range")
                return

            # Fetch tweets with V2 API
            query = f"${ticker}"
            try:
                tweets = client.search_recent_tweets(
                    query=query,
                    max_results=100,
                    tweet_fields=["created_at", "text"]
                ).data or []
            except tweepy.TweepyException as e:
                context.set_code(grpc.StatusCode.UNKNOWN)
                context.set_details(f"X API error: {str(e)}")
                return

            raw_data = [{"text": tweet.text, "created_at": tweet.created_at.isoformat()} for tweet in tweets]
            gcs_bucket = gcs_client.bucket("raw-sentiment-data")
            blob = gcs_bucket.blob(f"{ticker}/{datetime.utcnow().isoformat()}.json")
            blob.upload_from_string(json.dumps(raw_data))

            rows_to_insert = []
            for tweet in tweets:
                text = tweet.text
                sentiment = TextBlob(text).sentiment.polarity
                timestamp = tweet.created_at

                rows_to_insert.append({
                    "ticker": ticker,
                    "sentiment_score": sentiment,
                    "timestamp": timestamp.isoformat()
                })

                yield sentiment_pb2.SentimentResponse(
                    ticker=ticker,
                    sentiment_score=sentiment,
                    timestamp=str(int(timestamp.timestamp())),
                    data_point_count=1,
                    error=""
                )
                self.log_metric("sentiment_score", sentiment) # Metric logging

            table = self.bq_client.dataset(self.dataset).table(self.table)
            errors = self.bq_client.insert_rows_json(table, rows_to_insert)
            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                yield sentiment_pb2.SentimentResponse(error=f"Failed to write to BigQuery: {errors}")

def serve():
    start_http_server(8000)
    logger.info("gRPC server initialized with metrics server.")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    sentiment_pb2_grpc.add_SentimentServiceServicer_to_server(SentimentServiceServicer(), server)
    port = settings.GRPC_PORT if hasattr(settings, "GRPC_PORT") else 50051
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Starting gRPC server on port {port}...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()