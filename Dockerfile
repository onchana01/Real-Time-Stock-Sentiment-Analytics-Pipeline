FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/src/ /app/api/src/

CMD ["python", "/app/api/src/server.py"]