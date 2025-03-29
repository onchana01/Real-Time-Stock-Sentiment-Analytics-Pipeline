# Dockerfile for the Processing service
# Builds a container to process raw sentiment data and store it in BigQuery.
# Designed for efficiency and compatibility with GKE.

# Stage 1: Build
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install Poetry and dependencies
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy the processing source code, data models, and config
COPY processing/src/ ./processing/src/
COPY data/ ./data/
COPY config/ ./config/

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

# Set working directory
WORKDIR /app

# Create a non-root user
RUN useradd -m -r appuser && chown appuser:appuser /app
USER appuser

# Copy dependencies and source from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /app/processing/src/ ./processing/src/
COPY --from=builder /app/data/ ./data/
COPY --from=builder /app/config/ ./config/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Command to run the processing service
CMD ["python", "processing/src/pipeline.py"]