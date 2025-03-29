# Dockerfile for the API service
# Builds a lightweight container for the gRPC SentimentService, optimized for deployment on GKE.
# Uses a multi-stage build to separate build dependencies from runtime.

# Stage 1: Build
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency files to leverage caching
COPY pyproject.toml poetry.lock* ./

# Install Poetry and dependencies
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy the API source code and proto files
COPY api/src/ ./api/src/
COPY protos/ ./protos/
COPY config/ ./config/

# Compile .proto files to Python
RUN python -m grpc_tools.protoc -I./protos --python_out=./api/src --grpc_python_out=./api/src ./protos/sentiment.proto

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

# Set working directory
WORKDIR /app

# Create a non-root user for security
RUN useradd -m -r appuser && chown appuser:appuser /app
USER appuser

# Copy only the necessary files from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /app/api/src/ ./api/src/
COPY --from=builder /app/config/ ./config/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GRPC_PORT=50051

# Expose the gRPC port
EXPOSE ${GRPC_PORT}

# Command to run the gRPC server
CMD ["python", "api/src/server.py"]