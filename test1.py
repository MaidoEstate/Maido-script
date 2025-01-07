import os
import time
import logging
import json
import requests
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import subprocess

# Configuration
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
START_PAGE = int(os.getenv("START_PAGE", 12453))

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

def scrape_page(page_id):
    """Scrape a single page and save data locally."""
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Accessing URL: {url}")

    try:
        driver.get(url)
        time.sleep(2)

        # If redirected, skip the page
        if driver.current_url == "https://www.designers-osaka-chintai.info/":
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return False

        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_folder = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(page_folder, exist_ok=True)

        # Extract property details
        property_data = {
            "page_id": page_id,
            "title": soup.find("h1").text.strip() if soup.find("h1") else "No title",
            "description": soup.find("div", class_="description").text.strip() if soup.find("div", "description") else "No description",
            "big_images": [],
            "small_images": [],
        }

        # Define image filters
        def is_valid_image(img_url):
            """Check if the image URL is a property image (not UI elements)."""
            excluded_keywords = ["btn_", "icon_", "logo", "spacer", "blank", "menu"]
            return img_url and img_url.startswith("http") and not any(keyword in img_url for keyword in excluded_keywords)

        # Download images
        image_counter = 1
        for img_tag in soup.find_all("img"):
            img_url = img_tag.get("src")
            if is_valid_image(img_url):
                img_name = f"Maido_{datetime.now().strftime('%Y%m%d')}_{image_counter}.jpg"
                img_path = os.path.join(page_folder, img_name)

                try:
                    img_data = requests.get(img_url, timeout=10).content
                    with open(img_path, "wb") as f:
                        f.write(img_data)

                    logging.info(f"Downloaded image: {img_url} -> {img_name}")

                    # Categorize image based on size
                    if "big" in img_url:
                        property_data["big_images"].append(img_name)
                    else:
                        property_data["small_images"].append(img_name)

                    image_counter += 1
                except Exception as e:
                    logging.error(f"Failed to download image: {img_url}, Error: {e}")
            else:
                logging.info(f"Skipped UI image: {img_url}")

        # Save property data as JSON
        json_file_path = os.path.join(page_folder, f"property_{page_id}.json")
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(property_data, f, indent=4)

        logging.info(f"Scraped and saved data for page {page_id}")

        return True

    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROMIUM_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        scrape_page(START_PAGE)
        subprocess.run(["python", "upload_to_webflow.py"], check=True)
    finally:
        driver.quit()
