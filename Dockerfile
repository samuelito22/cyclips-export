# Use the official Python slim image as the base
FROM python:3.11-slim-bookworm

# Set environment variables to avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies, including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Optional: Set the working directory (adjust to your project structure)
WORKDIR /app

# Install Python dependencies
COPY builder/requirements.txt /requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r /requirements.txt && \
    rm /requirements.txt

# Copy source code into the container
ADD src /app

EXPOSE 8000

# Define the command to run your application
CMD ["python", "-u", "/app/rp_handler.py"]
