import os
import json
import requests
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuration
START_PAGE = int(os.getenv("START_PAGE", 12453))
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_UPLOAD_PRESET = os.getenv("CLOUDINARY_UPLOAD_PRESET")
MAX_CONSECUTIVE_INVALID = 10

# Logging setup
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s")

# Validate environment variables
REQUIRED_ENV_VARS = [
    "WEBFLOW_API_TOKEN", "WEBFLOW_COLLECTION_ID",
    "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_UPLOAD_PRESET"
]
for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        logging.error(f"Environment variable {var} is not set.")
        exit(1)

# Cloudinary image upload
def upload_image_to_cloudinary(image_path):
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    try:
        with open(image_path, "rb") as image_file:
            response = requests.post(
                url,
                files={"file": image_file},
                data={"upload_preset": CLOUDINARY_UPLOAD_PRESET}
            )
        if response.status_code == 200:
            cloudinary_url = response.json().get("secure_url")
            if cloudinary_url:
                logging.debug(f"Image uploaded to Cloudinary: {cloudinary_url}")
                return cloudinary_url
            else:
                logging.error("Cloudinary response did not contain a secure URL.")
        else:
            logging.error(f"Failed to upload image to Cloudinary: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error uploading to Cloudinary: {e}")
    return None

# Upload data to Webflow
def upload_to_webflow(data):
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"
    logging.debug(f"Preparing to upload to Webflow. URL: {url}")
    logging.debug(f"Payload: {json.dumps(data, indent=2)}")
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in (200, 201):
            logging.info(f"Successfully uploaded item to Webflow: {response.json()}")
        else:
            logging.error(f"Failed to upload item to Webflow: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error uploading to Webflow: {e}")

# Scrape a single page
def scrape_page(page_id, playwright):
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Scraping URL: {url}")
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        page.goto(url)
        if page.url == "https://www.designers-osaka-chintai.info/":
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return False

        # Extract data
        title = page.query_selector("h1").inner_text() if page.query_selector("h1") else "No Title"
        description = page.query_selector(".description").inner_text() if page.query_selector(".description") else "No Description"

        # Create output folder
        page_folder = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(page_folder, exist_ok=True)

        # Download and upload images
        images = []
        image_counter = 1
        for img in page.query_selector_all("img"):
            img_url = img.get_attribute("src")
            if img_url and img_url.startswith("http") and img_url.split("/")[-1][0].isdigit():  # Only numeric filenames
                image_path = os.path.join(page_folder, f"MAIDO_{datetime.now().strftime('%Y%m%d')}_{image_counter}.jpg")
                with open(image_path, "wb") as img_file:
                    img_file.write(requests.get(img_url).content)
                cloudinary_url = upload_image_to_cloudinary(image_path)
                if cloudinary_url:
                    images.append({"url": cloudinary_url})
                image_counter += 1
            else:
                logging.debug(f"Skipping non-numeric filename or invalid image URL: {img_url}")

        # Prepare data for Webflow
        webflow_data = {
            "fields": {
                "name": title,
                "slug": f"property-{page_id}",
                "_archived": False,
                "_draft": False,
                "description": f"<p>{description}</p>",
                "multi-image": images,
                "district": "6672b625a00e8f837e7b4e68",  # Example ID for "Naniwa-ku"
                "category": "665b099bc0ffada56b489baf",  # Example ID for "Rent a Home"
            }
        }

        # Upload to Webflow
        upload_to_webflow(webflow_data)
        logging.info(f"Page {page_id} scraped and uploaded successfully.")
        return True

    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False

    finally:
        browser.close()

# Main function
def main():
    try:
        with open("last_page.txt", "r") as f:
            current_page = int(f.read().strip()) + 1
    except FileNotFoundError:
        current_page = START_PAGE

    consecutive_invalid = 0
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as playwright:
        while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
            if scrape_page(current_page, playwright):
                with open("last_page.txt", "w") as f:
                    f.write(str(current_page))
                consecutive_invalid = 0
            else:
                consecutive_invalid += 1
            current_page += 1

if __name__ == "__main__":
    main()
