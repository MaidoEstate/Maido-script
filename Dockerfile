# Base image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y wget gnupg unzip jq && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable

# Debugging: Print installed Google Chrome version
RUN google-chrome --version

# Fetch ChromeDriver compatible version
RUN GOOGLE_CHROME_VERSION=$(google-chrome --version | awk '{print $3}') && \
    echo "Detected Google Chrome version: $GOOGLE_CHROME_VERSION" && \
    CHROME_DRIVER_VERSION=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json | jq -r ".milestones[\"${GOOGLE_CHROME_VERSION%%.*}\"].downloads.chromedriver.linux64[0].version") && \
    echo "Detected ChromeDriver version: $CHROME_DRIVER_VERSION" && \
    wget https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${GOOGLE_CHROME_VERSION}/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver-linux64.zip

# Clean up
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the entry point for the application
CMD ["python3", "test1.py"]