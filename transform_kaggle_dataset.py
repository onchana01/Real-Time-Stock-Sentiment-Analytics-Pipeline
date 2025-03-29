# scripts/transform_kaggle_dataset.py
import pandas as pd
from textblob import TextBlob

# Input and output paths
input_file = "archive/stock_tweets.csv"  # Matches your dataset location
output_file = "archive/transformed_sentiment_data.csv"

# Load Kaggle dataset
df = pd.read_csv(input_file)

# Map columns to SENTIMENT_DATA_SCHEMA
df["ticker"] = df["Stock Name"]  # Use ticker directly from Stock Name
df["sentiment_score"] = df["Tweet"].apply(lambda x: TextBlob(str(x)).sentiment.polarity)  # -1.0 to 1.0
df["timestamp"] = df["Date"]  # Already in ISO format (e.g., 2022-09-29 23:41:16+00:00)
df["data_point_count"] = 1
df["source"] = "X"

# Select required columns
transformed_df = df[["ticker", "sentiment_score", "timestamp", "data_point_count", "source"]]

# Save to CSV
transformed_df.to_csv(output_file, index=False)
print(f"Transformed dataset saved to {output_file}")