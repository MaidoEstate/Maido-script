import os
import re
import time
import requests
import logging
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import json

# Configuration
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
MAX_CONSECUTIVE_INVALID = 10
MAX_RETRIES = 3
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
START_PAGE = int(os.getenv("START_PAGE", 12453))  # Default starting page
GITHUB_PAT = os.getenv("GITHUB_PAT")
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

# Validate Configurations
logging.info(f"CLOUDINARY_CLOUD_NAME: {CLOUDINARY_CLOUD_NAME}")
logging.info(f"CLOUDINARY_API_KEY: {'Set' if CLOUDINARY_API_KEY else 'Not Set'}")
logging.info(f"CLOUDINARY_API_SECRET: {'Set' if CLOUDINARY_API_SECRET else 'Not Set'}")

if not (CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
    logging.error("Cloudinary configuration is incomplete. Ensure all Cloudinary credentials are set.")
    exit(1)

if not GITHUB_PAT:
    logging.error("GITHUB_PAT is not set. Check your environment and GitHub Actions secrets.")
    exit(1)

if not WEBFLOW_API_TOKEN:
    logging.error("WEBFLOW_API_TOKEN is not set. Check your environment variables or GitHub Actions secrets.")
    exit(1)

if not WEBFLOW_COLLECTION_ID:
    logging.error("WEBFLOW_COLLECTION_ID is not set. Ensure you've added the correct collection ID.")
    exit(1)

# Helper Functions
def upload_image_to_cloudinary(image_path):
    """
    Upload an image to Cloudinary and return its URL.
    """
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    with open(image_path, "rb") as image_file:
        response = requests.post(
            url, 
            files={"file": image_file}, 
            data={"upload_preset": "default"}
        )
    if response.status_code == 200:
        return response.json()["url"]
    else:
        logging.error(f"Failed to upload image to Cloudinary: {response.status_code}, {response.text}")
        return None

def upload_to_webflow(data):
    """
    Upload a single item to the Webflow CMS collection.
    """
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }

    url = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code in (200, 201):
            logging.info(f"Item successfully uploaded to Webflow: {response.json()}")
        else:
            logging.error(f"Failed to upload item to Webflow: {response.status_code}, {response.text}")
    except Exception as e:
        logging.error(f"Error while uploading item to Webflow: {e}")

def download_image(img_url, folder, image_counter, page_id):
    img_name = os.path.basename(img_url)
    if re.match(r'^\d', img_name):  # Image name starts with a digit
        for attempt in range(MAX_RETRIES):
            try:
                img_data = requests.get(img_url, timeout=10).content
                new_img_name = f"Maido_{datetime.now().strftime('%Y%m%d')}_{image_counter}.jpg"
                img_path = os.path.join(folder, new_img_name)
                with open(img_path, "wb") as f:
                    f.write(img_data)
                logging.info(f"Downloaded image for page {page_id}: {img_url} -> {new_img_name}")
                return img_path
            except Exception as e:
                logging.error(f"Failed to download image from page {page_id}: {e}")
        return None
    else:
        logging.info(f"Image {img_name} skipped as it does not start with a digit.")
        return None

def scrape_page(page_id):
    """
    Scrape a single page and upload data to Webflow.
    """
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Accessing URL: {url}")
    try:
        driver.get(url)
        time.sleep(2)
        if driver.current_url == "https://www.designers-osaka-chintai.info/":  # Redirected to homepage
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return False

        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_folder = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(page_folder, exist_ok=True)

        # Extract details and images
        property_data = {
            "title": soup.find("h1").text.strip() if soup.find("h1") else "No title",
            "description": soup.find("div", class_="description").text.strip() if soup.find("div", "description") else "No description",
            "images": [],
        }

        image_counter = 1
        for img_tag in soup.find_all("img"):
            img_url = img_tag.get("src")
            if img_url and img_url.startswith("http"):
                downloaded_image = download_image(img_url, page_folder, image_counter, page_id)
                if downloaded_image:
                    uploaded_url = upload_image_to_cloudinary(downloaded_image)
                    if uploaded_url:
                        property_data["images"].append(uploaded_url)
                    image_counter += 1

        # Prepare Webflow data
        webflow_data = {
            "fields": {
                "name": property_data["title"],
                "slug": f"property-{page_id}",
                "description": property_data["description"],
                "_archived": False,
                "_draft": False,
                "images": property_data["images"],
            }
        }

        # Upload to Webflow
        upload_to_webflow(webflow_data)
        logging.info(f"Page {page_id} processed and uploaded successfully.")
        return True

    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False

# Main Function
def main():
    try:
        with open("last_page.txt", "r") as f:
            current_page = int(f.read().strip()) + 1
    except (FileNotFoundError, ValueError):
        current_page = START_PAGE

    consecutive_invalid = 0
    while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
        success = scrape_page(current_page)
        if success:
            with open("last_page.txt", "w") as f:
                f.write(str(current_page))
            consecutive_invalid = 0
        else:
            consecutive_invalid += 1
            logging.warning(f"Page {current_page} was invalid or redirected.")
        current_page += 1

if __name__ == "__main__":
    # Selenium setup
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROMIUM_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        main()
    finally:
        driver.quit()
