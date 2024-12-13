import os
import time
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import threading
import http.server
import socketserver
import socket

# Configuration
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
START_PAGE = int(os.getenv("START_PAGE", "12440"))
MAX_CONSECUTIVE_INVALID = 10  # Stop after 5 consecutive invalid IDs
OUTPUT_DIR = "/app/scraped_data"  # Directory for storing scraped data

# Selenium setup
chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium"
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMIUM_DRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Graceful exit
def graceful_exit():
    print("Shutting down scraper.")
    driver.quit()

# Check if port is in use
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

# Dummy HTTP server
def run_server():
    port = int(os.getenv("PORT", 8080))
    if is_port_in_use(port):
        print(f"Port {port} is already in use. Skipping server start.")
        return
    handler = http.server.SimpleHTTPRequestHandler
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"Serving on port {port}")
            httpd.serve_forever()
    except OSError as e:
        print(f"Failed to start server on port {port}: {e}")

# Start the dummy server in a separate thread
threading.Thread(target=run_server, daemon=True).start()

# Helper: Create directory
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Helper: Save errors to log
def log_error(message):
    with open("error.log", "a") as f:
        f.write(f"{datetime.now()}: {message}\n")

# Helper: Download images
def download_image(url, folder, image_counter):
    try:
        img_data = requests.get(url, timeout=10).content
        img_name = f"image_{image_counter}.jpg"
        img_path = os.path.join(folder, img_name)
        with open(img_path, "wb") as f:
            f.write(img_data)
        return img_path
    except Exception as e:
        log_error(f"Failed to download image {url}: {e}")
        return None

# Main scraping logic
def scrape_page(page_id, output_dir):
    url = f"{BASE_URL}{page_id}"
    driver.get(url)
    time.sleep(2)

    # Check if redirected to homepage
    if driver.current_url == "https://www.designers-osaka-chintai.info/":
        print(f"Page {page_id} redirected to homepage. Skipping.")
        return None

    # Parse page content
    soup = BeautifulSoup(driver.page_source, "html.parser")
    page_folder = os.path.join(output_dir, str(page_id))
    create_directory(page_folder)

    # Extract property details
    try:
        title = soup.find("h1").text.strip() if soup.find("h1") else "No title"
        description = soup.find("div", class_="description").text.strip() if soup.find("div", class_="description") else "No description"

        # Download images
        images = []
        image_tags = soup.find_all("img")
        for i, img_tag in enumerate(image_tags):
            img_url = img_tag.get("src")
            if img_url and img_url.startswith("http"):
                img_path = download_image(img_url, page_folder, i + 1)
                if img_path:
                    images.append(img_path)

        # Save data to CSV
        csv_file = os.path.join(output_dir, "scraped_data.csv")
        with open(csv_file, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if os.stat(csv_file).st_size == 0:  # Write header only if file is empty
                writer.writerow(["Page ID", "Title", "Description", "Images"])
            writer.writerow([page_id, title, description, ", ".join(images)])

        print(f"Page {page_id} scraped successfully.")
        return True

    except Exception as e:
        log_error(f"Error scraping page {page_id}: {e}")
        return None

# Main loop
def main():
    current_page = START_PAGE
    consecutive_invalid = 0
    create_directory(OUTPUT_DIR)

    while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
        print(f"Scraping page {current_page}...")
        result = scrape_page(current_page, OUTPUT_DIR)
        if result:
            consecutive_invalid = 0  # Reset on successful scrape
        else:
            consecutive_invalid += 1  # Increment on failure
            print(f"Consecutive invalid pages: {consecutive_invalid}")
        current_page += 1

    print("Scraping complete. Exiting.")
    graceful_exit()

if __name__ == "__main__":
    main()