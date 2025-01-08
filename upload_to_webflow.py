import os
import json
import logging
import requests

# Configuration
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
UPLOAD_PRESET = "default"

BASE_DIRECTORY = os.getenv("OUTPUT_DIR", "./scraped_data")

logging.basicConfig(level=logging.DEBUG)

def upload_image_to_cloudinary(image_path):
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    logging.debug(f"Uploading image to Cloudinary: {image_path}")
    with open(image_path, "rb") as image_file:
        response = requests.post(
            url,
            files={"file": image_file},
            data={"upload_preset": UPLOAD_PRESET}
        )
    if response.status_code == 200:
        secure_url = response.json().get("secure_url")
        logging.debug(f"Successfully uploaded image to Cloudinary: {secure_url}")
        return secure_url
    else:
        logging.error(f"Failed to upload image to Cloudinary: {response.status_code} - {response.text}")
        return None

def upload_to_webflow(data):
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"
    logging.debug(f"Uploading data to Webflow: {data}")
    response = requests.post(url, headers=headers, json=data)
    if response.status_code in (200, 201):
        logging.info(f"Successfully uploaded to Webflow: {response.json()}")
    else:
        logging.error(f"Upload to Webflow failed: {response.status_code} - {response.text}")

def process_scraped_data():
    if not os.path.isdir(BASE_DIRECTORY):
        logging.error(f"Base directory does not exist: {BASE_DIRECTORY}")
        return

    for page_folder in os.listdir(BASE_DIRECTORY):
        json_file = os.path.join(BASE_DIRECTORY, page_folder, f"property_{page_folder}.json")
        if not os.path.exists(json_file):
            logging.warning(f"JSON file does not exist for folder: {page_folder}")
            continue

        with open(json_file, "r", encoding="utf-8") as f:
            property_data = json.load(f)

        # Upload images to Cloudinary
        hosted_images = []
        for img in property_data.get("big_images", []):
            img_path = os.path.join(BASE_DIRECTORY, page_folder, img)
            cloudinary_url = upload_image_to_cloudinary(img_path)
            if cloudinary_url:
                hosted_images.append({"url": cloudinary_url})

        # Prepare Webflow data
        webflow_data = {
            "fields": {
                "name": property_data["title"],
                "slug": f"property-{property_data['page_id']}",
                "description": f"<p>{property_data['description']}</p>",
                "multi-image": hosted_images,
                "district": property_data.get("district_id", "default_district_id"),
                "category": property_data.get("category_id", "default_category_id"),
            }
        }

        # Upload data to Webflow
        upload_to_webflow(webflow_data)

if __name__ == "__main__":
    process_scraped_data()
