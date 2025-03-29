# Real-Time-Stock-Sentiment-Analytics-Pipeline
## Overview
This project builds a scalable pipeline to stream real-time stock sentiment data from X, process it with TextBlob, store results in Google BigQuery and Cloud Storage (GCS), and monitor sentiment scores using Google Cloud Monitoring (or logs in free tier). It’s deployed on Google Kubernetes Engine (GKE) with CI/CD via Google Cloud Build.

## Features
- Streams stock-related tweets via X API.
- Analyzes sentiment using TextBlob.
- Stores data in BigQuery and GCS.
- Exposes sentiment data via gRPC.
- Monitors sentiment scores (logs in free tier).
- Deployed on GKE with automated CI/CD.

## Prerequisites
- Google Cloud Project (`fresh-rain-454919-b2`)
- GKE Cluster (`sentiment-cluster`)
- X API Credentials (stored in `sentiment-api-secrets` Kubernetes secret)
- Tools: `kubectl`, `docker`, `gcloud`, `git`, `grpcurl`

## Project Structure

Real-Time-Stock-Sentiment-Analytics-Pipeline/stock-sentiment-analyzer/
├── api
│   ├── protos                  # gRPC protocol definitions
│   │   ├── sentiment.proto
│   │   ├── sentiment_pb2.py    # Generated proto files
│   │   └── sentiment_pb2_grpc.py
│   ├── src                    # API source code
│   │   ├── config             # Configuration modules
│   │   │   ├── init.py
│   │   │   ├── logging.py
│   │   │   ├── logging.yaml
│   │   │   └── settings.py
│   │   ├── data              # Data models and schemas
│   │   │   ├── init.py
│   │   │   ├── models.py
│   │   │   └── schema.py
│   │   ├── init.py
│   │   ├── server.py         # gRPC server implementation
│   │   ├── service.py        # Sentiment service logic
│   │   ├── sentiment_pb2.py   # Duplicates (can be cleaned)
│   │   └── sentiment_pb2_grpc.py
│   └── tests                 # API tests
│       ├── init.py
│       └── test_service.py
├── archive                   # Sample data files
│   ├── stock_tweets.csv
│   ├── stock_yfinance_data.csv
│   └── transformed_sentiment_data.csv
├── build.log                 # Docker build log
├── client.py                 # gRPC client script
├── config.py                 # Additional config (optional)
├── deployment
│   ├── docker                # Dockerfiles for components
│   │   ├── api/Dockerfile
│   │   ├── ingestion/Dockerfile
│   │   └── processing/Dockerfile
│   ├── istio                 # Istio config (optional)
│   │   └── virtual-service.yaml
│   └── k8s                   # Kubernetes manifests
│       ├── api.yaml
│       ├── cloudbuild.yaml   # CI/CD configuration
│       ├── deployment.yaml   # GKE deployment
│       ├── grafana.yaml      # Grafana setup (optional)
│       ├── ingestion.yaml
│       └── processing.yaml
├── Dockerfile                # Main Dockerfile for API
├── grafana-dashboard.json    # Grafana dashboard config (optional)
├── ingestion
│   ├── src                   # Data ingestion scripts
│   │   ├── fetcher.py
│   │   ├── init.py
│   │   └── storage.py
│   └── tests
│       ├── init.py
│       └── test_fetcher.py
├── poetry.lock               # Poetry lock file (optional)
├── processing
│   ├── src                   # Data processing scripts
│   │   ├── bigquery.py
│   │   ├── init.py
│   │   ├── pipeline.py
│   │   └── sentiment.py
│   └── tests
│       ├── init.py
│       └── test_pipeline.py
├── pyproject.toml            # Poetry config (optional)
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── scripts
│   ├── build_protos.sh       # Script to generate proto files
│   └── load_test.py          # Load testing script
├── tests                     # End-to-end tests
│   ├── init.py
│   └── test_e2e.py
├── transform_kaggle_dataset.py # Data transformation script
└── y                         # Unknown file (cleanup?)

## Setup Instructions
1. **Clone the Repository:**

   git clone https://github.com/onchana01/Real-Time-Stock-Sentiment-Analytics-Pipeline.git
   cd Real-Time-Stock-Sentiment-Analytics-Pipeline/stock-sentiment-analyzer

2. **Build the Docker Image:**

   docker build -t gcr.io/fresh-rain-454919-b2/stock-sentiment:v6 .
   docker push gcr.io/fresh-rain-454919-b2/stock-sentiment:v6

3. **Deploy to GKE:**

   kubectl apply -f deployment/k8s/deployment.yaml

4. **Set Up CI/CD (Optional):**

   gcloud builds submit --config deployment/k8s/cloudbuild.yaml .

5. **Verify Deployment:**

   kubectl get pods -l app=sentiment

Expected output:

   NAME                             READY   STATUS    RESTARTS   AGE
   sentiment-api-6999444f899d-6qf4v   1/1     Running   0          XXm
   sentiment-api-6999344f899d-jrpvm   1/1     Running   0          XXm

## How to Run
1. **Stream Sentiment Data:**
- **Locally:**
  ```
  kubectl port-forward sentiment-api-<pod-name> 50051:50051
  grpcurl -plaintext -proto api/protos/sentiment.proto -d '{"ticker": "TSLA", "start_time": "2025-03-22T00:00:00Z", "end_time": "2025-03-22T01:00:00Z", "interval": 2}' localhost:50051 sentiment.SentimentService/StreamStockSentiment
  ```
- **Externally:**
  ```
  grpcurl -plaintext -proto api/protos/sentiment.proto -d '{"ticker": "TSLA", "start_time": "2025-03-22T00:00:00Z", "end_time": "2025-03-22T01:00:00Z", "interval": 2}' 35.238.123.39:50051 sentiment.SentimentService/StreamStockSentiment
  ```

2. **Check Logs:**

   kubectl logs sentiment-api-<pod-name>

3. **Monitor Metrics (Free Tier Logs):**
- Check logs for sentiment scores:
  ```
  kubectl logs sentiment-api-<pod-name> | grep "Metric sentiment_score"
  ```
- If upgraded: Use Google Cloud Monitoring (`custom.googleapis.com/sentiment/sentiment_score`).

4. **Simulate Incident:**

   kubectl delete pod sentiment-api-<pod-name> --force
   kubectl get pods -l app=sentiment

## Dependencies
See `requirements.txt`:

tweepy>=4.10.0
google-cloud-bigquery
google-cloud-storage
textblob
grpcio
prometheus-client
google-cloud-monitoring
python-decouple

## Troubleshooting
- **Pods Crashing:** Check logs: `kubectl logs <pod-name>`.
- **gRPC Connection Refused:** Verify service: `kubectl get svc sentiment-service`.
- **No Metrics:** Ensure `roles/monitoring.metricWriter` is set or check logs.

## Next Steps
- Upgrade to paid tier for full Google Cloud Monitoring.
- Implement alerting for sentiment anomalies.
- Optimize ingestion and processing for larger datasets.

## License
MIT License.



