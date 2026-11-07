# Resonant — Production Dockerfile for Render.com
# Includes Python 3.12 + ffmpeg + all dependencies

FROM python:3.12-slim

# Install system dependencies (ffmpeg for audio conversion)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create outputs directory for generated audio
RUN mkdir -p outputs

# Expose port (Render provides $PORT)
EXPOSE 10000

# Start the server
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}
