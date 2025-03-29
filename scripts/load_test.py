# load_test.py
# Locust script for load testing the SentimentService gRPC API.
# Simulates multiple users making unary and streaming requests to evaluate performance
# and scalability under load.

import logging
import grpc
from locust import User, task, between, events
import sentiment_pb2
import sentiment_pb2_grpc
from google.protobuf.timestamp_pb2 import Timestamp
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Host and port for the gRPC service (configurable via Locust --host)
DEFAULT_HOST = "localhost:50051"

class GrpcUser(User):
    """Custom Locust user class for gRPC requests."""
    
    # Wait time between tasks (1-5 seconds)
    wait_time = between(1, 5)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Establish gRPC channel
        self.channel = grpc.insecure_channel(self.host or DEFAULT_HOST)
        self.stub = sentiment_pb2_grpc.SentimentServiceStub(self.channel)
        logger.info(f"Initialized GrpcUser with host: {self.host or DEFAULT_HOST}")

    def on_stop(self):
        """Close the gRPC channel when the user stops."""
        self.channel.close()
        logger.info("Closed gRPC channel.")

    @task(3)  # Weight: 3x more frequent than streaming task
    def test_get_stock_sentiment(self):
        """Test the unary GetStockSentiment RPC."""
        request = sentiment_pb2.StockSentimentRequest(
            ticker="AAPL",
            timeframe="1h"
        )
        
        start_time = time.time()
        try:
            response = self.stub.GetStockSentiment(request)
            response_time = (time.time() - start_time) * 1000  # ms
            
            if response.error:
                events.request.fire(
                    request_type="grpc",
                    name="GetStockSentiment",
                    response_time=response_time,
                    response_length=0,
                    exception=Exception(f"Error: {response.error}")
                )
            else:
                events.request.fire(
                    request_type="grpc",
                    name="GetStockSentiment",
                    response_time=response_time,
                    response_length=len(str(response).encode('utf-8')),
                    exception=None
                )
                logger.debug(f"GetStockSentiment succeeded: {response.sentiment_score}")
        except grpc.RpcError as e:
            response_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="grpc",
                name="GetStockSentiment",
                response_time=response_time,
                response_length=0,
                exception=e
            )
            logger.error(f"GetStockSentiment failed: {str(e)}")

    @task(1)  # Weight: 1x less frequent than unary task
    def test_stream_stock_sentiment(self):
        """Test the streaming StreamStockSentiment RPC."""
        request = sentiment_pb2.StockSentimentStreamRequest(
            ticker="TSLA",
            start_time=int(time.time() - 3600),  # Last hour
            end_time=int(time.time()),
            interval="1h"
        )
        
        start_time = time.time()
        try:
            response_stream = self.stub.StreamStockSentiment(request)
            response_count = 0
            total_length = 0
            
            for response in response_stream:
                response_count += 1
                total_length += len(str(response).encode('utf-8'))
                if response.error:
                    raise Exception(f"Stream error: {response.error}")
            
            response_time = (time.time() - start_time) * 1000  # ms
            events.request.fire(
                request_type="grpc",
                name="StreamStockSentiment",
                response_time=response_time,
                response_length=total_length,
                exception=None
            )
            logger.debug(f"StreamStockSentiment received {response_count} responses")
        except grpc.RpcError as e:
            response_time = (time.time() - start_time) * 1000
            events.request.fire(
                request_type="grpc",
                name="StreamStockSentiment",
                response_time=response_time,
                response_length=0,
                exception=e
            )
            logger.error(f"StreamStockSentiment failed: {str(e)}")

if __name__ == "__main__":
    # Example usage: run locally with Locust
    import os
    os.system(f"locust -f scripts/load_test.py --host={DEFAULT_HOST}")