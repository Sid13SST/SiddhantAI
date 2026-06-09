FROM python:3.12-slim

WORKDIR /app

# Copy slim requirements (no PyTorch — uses HuggingFace API for embeddings)
COPY requirements.deploy.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.deploy.txt

# Copy application code and pre-built data
COPY app/ app/
COPY data/ data/

# Create necessary directories
RUN mkdir -p data/evaluation/history data/raw

# Set environment variables
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=10000
ENV DATA_DIR=data

EXPOSE 10000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
