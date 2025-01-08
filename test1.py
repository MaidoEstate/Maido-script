import os
import json
import logging
import requests
from datetime import datetime

# Configuration
START_PAGE = int(os.getenv("START_PAGE", 12453))
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
CLOUDINARY_UPLOAD_PRESET = os.getenv("UPLOAD_PRESET", "default")
MAX_CONSECUTIVE_INVALID = 10

# Logging setup
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s")

# Validate environment variables
required_env_vars = [
    "WEBFLOW_API_TOKEN", "WEBFLOW_COLLECTION_ID",
    "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"
]
for var in required_env_vars:
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
            cloudinary_url = response.json()["secure_url"]
            logging.debug(f"Image uploaded to Cloudinary: {cloudinary_url}")
            return cloudinary_url
        else:
            logging.error(f"Failed to upload image to Cloudinary: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error during Cloudinary upload: {e}")
        return None

# Webflow data upload
def upload_to_webflow(data):
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"

    logging.debug(f"Preparing to upload to Webflow. URL: {url}")
    logging.debug(f"Headers: {headers}")
    logging.debug(f"Payload: {json.dumps(data, indent=2)}")

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in (200, 201):
            logging.info(f"Successfully uploaded item to Webflow: {response.json()}")
        else:
            logging.error(f"Failed to upload item to Webflow: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error during Webflow upload: {e}")

# Scrape and process data
def process_scraped_data():
    for page_folder in os.listdir(OUTPUT_DIR):
        json_file = os.path.join(OUTPUT_DIR, page_folder, f"property_{page_folder}.json")
        if not os.path.exists(json_file):
            logging.debug(f"Skipping folder without JSON file: {page_folder}")
            continue

        with open(json_file, "r", encoding="utf-8") as f:
            property_data = json.load(f)

        # Log each field for verification
        logging.debug(f"Processing property: {property_data.get('title', 'No Title')}")
        logging.debug(f"Description length: {len(property_data.get('description', ''))}")
        logging.debug(f"Number of images: {len(property_data.get('big_images', []))}")

        # Upload images to Cloudinary
        hosted_images = [
            upload_image_to_cloudinary(os.path.join(OUTPUT_DIR, page_folder, img))
            for img in property_data.get("big_images", [])
            if img.split("/")[-1][0].isdigit()  # Only process images starting with a digit
        ]
        hosted_images = [url for url in hosted_images if url]  # Filter out failed uploads

        # Prepare data for Webflow
        webflow_data = {
            "fields": {
                "name": property_data.get("title", "No Title"),
                "slug": f"property-{property_data.get('page_id', 'no-id')}",
                "_archived": False,
                "_draft": False,
                "description": f"<p>{property_data.get('description', 'No Description')}</p>",
                "multi-image": [{"url": url} for url in hosted_images],
                "district": "6672b625a00e8f837e7b4e68",  # Example ID for "Naniwa-ku"
                "category": "665b099bc0ffada56b489baf",  # Example ID for "Rent a Home"
            }
        }

        # Upload to Webflow
        upload_to_webflow(webflow_data)

if __name__ == "__main__":
    process_scraped_data()
