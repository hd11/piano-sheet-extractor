FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements_backup.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements_backup.txt

# Copy source code
COPY core/ core/
COPY scripts/ scripts/
COPY test_pipeline.py .

# Default command: run evaluation
CMD ["python", "scripts/evaluate.py", "--input-dir", "/data/test", "--output", "/data/results/docker_demucs_v1.json"]
