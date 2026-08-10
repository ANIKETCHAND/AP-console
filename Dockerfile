FROM python:3.11-slim

# Install system dependencies for OpenCV & Librosa (audio/video forensics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement list and install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY backend /app/backend
COPY frontend /app/frontend

WORKDIR /app/backend

# Expose server port
EXPOSE 8000

# Start Uvicorn production server
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port \"]
