import os
import socket
import time
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import signal
import sys
import http.server
import socketserver
import threading

# Environment variables
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
LAST_PAGE_FILE = os.getenv("LAST_PAGE_FILE", "last_page.txt")

# Setup Chrome options
chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium"
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

service = Service(CHROMIUM_DRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Graceful shutdown handler
def graceful_exit(*args):
    print("Shutting down scraper.")
    driver.quit()
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

# Run dummy server
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def run_server():
    port = int(os.getenv("PORT", 8080))
    if is_port_in_use(port):
        print(f"Port {port} is already in use. Skipping server start.")
        return
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving on port {port}")
        httpd.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# Scraper logic
last_processed_page = int(os.getenv("START_PAGE", "12440"))
base_url = "https://www.designers-osaka-chintai.info/detail/id/"
redirect_limit = 3
redirect_count = 0

while True:
    url = f"{base_url}{last_processed_page}"
    print(f"Accessing URL: {url}")
    try:
        driver.get(url)
        time.sleep(3)

        if driver.current_url == "https://www.designers-osaka-chintai.info/":
            print("Redirect detected.")
            redirect_count += 1
            if redirect_count >= redirect_limit:
                print("Too many redirects. Exiting.")
                break
            continue
        redirect_count = 0

        # Add scraping logic here...

        last_processed_page += 1

    except Exception as e:
        print(f"Error: {e}")
        break

driver.quit()