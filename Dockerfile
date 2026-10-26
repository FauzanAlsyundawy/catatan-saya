# ── Catatan Saya — Production Dockerfile ──────────────────────────────────────
# Runtime: Python 3.12 slim | Server: Uvicorn | Port: 8000
# Build:  docker build -t catatan-saya .
# Run:    docker run -p 8000:8000 --env-file .env catatan-saya
# ------------------------------------------------------------------------------

FROM python:3.12-slim

# Prevent .pyc files and enable real-time log streaming
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install OS deps needed by argon2-cffi (libffi)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libffi-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cached)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create persistent directories (will be overridden by Docker volumes in prod)
RUN mkdir -p data uploads

# Expose application port
EXPOSE 8000

# Entrypoint: Uvicorn with production settings
# - host 0.0.0.0  → reachable from outside the container
# - workers 2     → adjust to (2 × CPU cores) + 1 if needed
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
