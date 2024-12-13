# Base image
FROM python:3.11-slim

# Install system dependencies and Chromium
RUN apt-get update && \
    apt-get install -y wget gnupg unzip jq curl chromium chromium-driver && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Debugging: Print installed Chromium version and WebDriver version
RUN chromium --version && ls /usr/bin | grep chromium

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the entry point for the application
CMD ["python3", "test1.py"]