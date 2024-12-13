import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import threading
import socketserver
import socket

# Configuration
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
START_PAGE = int(os.getenv("START_PAGE", "12440"))
MAX_CONSECUTIVE_INVALID = 10
MAX_RETRIES = 3
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/scraped_data")  # Default to Docker's app folder
PORT = int(os.getenv("PORT", 8080))

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

# Helper: Create directory if it doesn't exist
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Helper: Log messages to a file
def log_message(filename, message):
    with open(filename, "a") as f:
        f.write(f"{datetime.now()}: {message}\n")

# Helper: Download image with retries
def download_image(url, folder, image_counter):
    for attempt in range(MAX_RETRIES):
        try:
            img_data = requests.get(url, timeout=10).content
            img_name = f"image_{image_counter}.jpg"
            img_path = os.path.join(folder, img_name)
            with open(img_path, "wb") as f:
                f.write(img_data)
            return img_path
        except Exception as e:
            if attempt == MAX_RETRIES - 1:  # Log error if all retries fail
                log_message("error.log", f"Failed to download image {url}: {e}")
    return None

# Scraper: Process a single page
def scrape_page(page_id, output_dir):
    url = f"{BASE_URL}{page_id}"
    print(f"Accessing URL: {url}")
    try:
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
        log_message("success.log", f"Page {page_id} scraped successfully.")
        return True

    except Exception as e:
        log_message("error.log", f"Error scraping page {page_id}: {e}")
        return None

# Main scraper loop
def main():
    current_page = START_PAGE
    consecutive_invalid = 0
    create_directory(OUTPUT_DIR)

    while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
        print(f"Scraping page {current_page}...")
        result = scrape_page(current_page, OUTPUT_DIR)
        if result:
            consecutive_invalid = 0  # Reset on success
        else:
            consecutive_invalid += 1  # Increment on failure
            print(f"Consecutive invalid pages: {consecutive_invalid}")
        current_page += 1

    print("Scraping complete. Exiting.")
    graceful_exit()

# Start the scraper
if __name__ == "__main__":
    try:
        threading.Thread(target=main, daemon=False).start()
    except KeyboardInterrupt:
        graceful_exit()