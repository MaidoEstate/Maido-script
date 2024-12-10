# Base image
FROM python:3.11-slim

# Set environment variables to minimize interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Install system dependencies
RUN apt-get update -o Dir::Cache::pkgcache="" -o Dir::Cache::srcpkgcache="" && \
    apt-get install -y --no-install-recommends gnupg unzip curl && \
    curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update -o Dir::Cache::pkgcache="" -o Dir::Cache::srcpkgcache="" && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    CHROME_DRIVER_VERSION=$(curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
    curl -O https://chromedriver.storage.googleapis.com/${CHROME_DRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the entry point for the application
CMD ["python3", "test1.py"]