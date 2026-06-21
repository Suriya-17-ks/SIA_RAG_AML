# ── SIA-RAG Backend Dockerfile ───────────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /app

# Install system dependencies required for building some python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to cache them in docker layer
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Final Runtime Image ───────────────────────────────────────────────────────
FROM python:3.10-slim

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime system dependencies (e.g. for pdf parsing if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . /app/

# Create data directory for ChromaDB and graphs
RUN mkdir -p /app/data && chmod 777 /app/data

# Expose FastAPI port
EXPOSE 8000

# Set environment variables for production behaviour
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000
# Ensure local paths resolve correctly
ENV PYTHONPATH=/app

# Run uvicorn server
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
