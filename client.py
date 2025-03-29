# client.py
import grpc
import sentiment_pb2
import sentiment_pb2_grpc
from api.src.sentiment_pb2 import StockSentimentRequest, StockSentimentStreamRequest
from google.protobuf.timestamp_pb2 import Timestamp

def run():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = sentiment_pb2_grpc.SentimentServiceStub(channel)

        # Test GetStockSentiment
        request = sentiment_pb2.StockSentimentRequest(ticker="TSLA", timeframe=sentiment_pb2.TIMEFRAME_1H)
        response = stub.GetStockSentiment(request)
        print("GetStockSentiment:", response)

        # Test StreamStockSentiment
        start = Timestamp(seconds=1664400000)  # 2022-09-29 00:00:00 UTC
        end = Timestamp(seconds=1664486400)    # 2022-09-30 00:00:00 UTC
        stream_request = sentiment_pb2.StockSentimentStreamRequest(
            ticker="TSLA", start_time=start, end_time=end, interval=sentiment_pb2.INTERVAL_1H
        )
        for response in stub.StreamStockSentiment(stream_request):
            print("StreamStockSentiment:", response)

if __name__ == "__main__":
    run()
