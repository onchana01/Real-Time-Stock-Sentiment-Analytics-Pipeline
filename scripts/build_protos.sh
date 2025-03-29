#!/bin/bash
# build_protos.sh
# Compiles Protocol Buffer (.proto) files into Python code for the Stock Sentiment Analyzer.
# Generates gRPC service stubs and message classes, ensuring compatibility with the project.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROTO_DIR="$PROJECT_ROOT/api/protos"
OUTPUT_DIR="$PROJECT_ROOT/api/src"

if ! poetry run python -c "import grpc_tools" 2>/dev/null; then
    echo "Error: grpc_tools not found in Poetry environment. Ensure 'grpcio-tools' is in pyproject.toml and run 'poetry install'."
    exit 1
fi

if [ ! -d "$PROTO_DIR" ]; then
    echo "Error: Proto directory $PROTO_DIR does not exist."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Compiling .proto files from $PROTO_DIR to $OUTPUT_DIR..."
for proto_file in "$PROTO_DIR"/*.proto; do
    if [ -f "$proto_file" ]; then
        echo "Processing $(basename "$proto_file")..."
        poetry run python -m grpc_tools.protoc             -I"$PROTO_DIR"             --python_out="$OUTPUT_DIR"             --grpc_python_out="$OUTPUT_DIR"             "$proto_file"
    else
        echo "No .proto files found in $PROTO_DIR."
        exit 1
    fi
done

echo "Proto compilation completed successfully."
