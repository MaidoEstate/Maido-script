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

# Cloudinary image upload with retry logic
def upload_image_to_cloudinary(image_path):
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    for attempt in range(3):
        try:
            with open(image_path, "rb") as image_file:
                response = requests.post(
                    url,
                    files={"file": image_file},
                    data={"upload_preset": CLOUDINARY_UPLOAD_PRESET}
                )
            if response.status_code == 200:
                cloudinary_url = response.json().get("secure_url")
                logging.debug(f"Image uploaded to Cloudinary: {cloudinary_url}")
                return cloudinary_url
            logging.error(f"Cloudinary upload failed: {response.status_code} - {response.text}")
        except Exception as e:
            logging.warning(f"Retry {attempt + 1}/3 for Cloudinary upload: {e}")
    logging.error("Cloudinary upload failed after 3 attempts.")
    return None

# Upload data to Webflow
def upload_to_webflow(data):
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"

    # Prepare payload for v2
    payload = {
        "items": [
            {
                "name": data["fields"].get("name", "Default Name"),
                "slug": data["fields"].get("slug", f"default-slug-{int(datetime.now().timestamp())}"),
                "_archived": False,
                "_draft": False,
                "description": data["fields"].get("description", "<p>No Description</p>"),
                "multi-image": data["fields"].get("multi-image", [])[:25],  # Limit to 25 images
                "district": data["fields"].get("district"),
                "category": data["fields"].get("category"),
            }
        ]
    }

    try:
        logging.debug(f"Uploading to Webflow: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        logging.debug(f"Webflow Response: {response.status_code} - {response.text}")
        if response.status_code in (200, 201):
            logging.info(f"Uploaded item to Webflow successfully.")
        else:
            logging.error(f"Webflow upload failed: {response.status_code} - {response.text}")
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

        # Extract title and exclude undesired ones
        title = None
        h1_elements = page.query_selector_all("h1")
        for h1 in h1_elements:
            extracted_title = h1.inner_text()
            if extracted_title != "大阪デザイナーズマンション専門サイト キワミ":
                title = extracted_title
                break

        if not title:
            title = "No Title"
        logging.info(f"Title for page {page_id}: {title}")

        # Extract description
        description = page.query_selector(".description").inner_text() if page.query_selector(".description") else "No Description"

        # Create output folder
        page_folder = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(page_folder, exist_ok=True)

        # Download and upload images
        images = []
        for img in page.query_selector_all("img"):
            img_url = img.get_attribute("src")
            if img_url and img_url.startswith("http") and img_url.split("/")[-1][0].isdigit():
                image_path = os.path.join(page_folder, f"MAIDO_{datetime.now().strftime('%Y%m%d')}_{len(images) + 1}.jpg")
                with open(image_path, "wb") as img_file:
                    img_file.write(requests.get(img_url).content)
                cloudinary_url = upload_image_to_cloudinary(image_path)
                if cloudinary_url:
                    images.append({"url": cloudinary_url})

        # Prepare data for Webflow
        webflow_data = {
            "fields": {
                "name": title,
                "slug": f"property-{page_id}-{int(datetime.now().timestamp())}",
                "_archived": False,
                "_draft": False,
                "description": f"<p>{description}</p>",
                "multi-image": images[:25],  # Limit to 25 images
                "district": "6672b625a00e8f837e7b4e68",  # Adjust this ID
                "category": "665b099bc0ffada56b489baf",  # Adjust this ID
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
