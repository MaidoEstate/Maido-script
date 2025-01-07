import os
import json
import logging
import requests
import time

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
    with open(image_path, "rb") as image_file:
        response = requests.post(url, files={"file": image_file}, data={"upload_preset": UPLOAD_PRESET})
    if response.status_code == 200:
        return response.json()["secure_url"]
    else:
        logging.error(f"Failed to upload image: {response.text}")
        return None

def upload_to_webflow(data):
    headers = {"Authorization": f"Bearer {WEBFLOW_API_TOKEN}", "Content-Type": "application/json"}
    url = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"
    response = requests.post(url, headers=headers, json=data)
    if response.status_code in (200, 201):
        logging.info(f"Successfully uploaded: {response.json()}")
    else:
        logging.error(f"Upload failed: {response.text}")

def process_scraped_data():
    for page_folder in os.listdir(BASE_DIRECTORY):
        json_file = os.path.join(BASE_DIRECTORY, page_folder, f"property_{page_folder}.json")
        if not os.path.exists(json_file):
            continue
        with open(json_file, "r", encoding="utf-8") as f:
            property_data = json.load(f)
        hosted_images = [upload_image_to_cloudinary(os.path.join(BASE_DIRECTORY, page_folder, img)) for img in property_data["big_images"]]
        webflow_data = {"fields": {"name": property_data["title"], "slug": f"property-{property_data['page_id']}", "description": property_data["description"], "images": hosted_images}}
        upload_to_webflow(webflow_data)

if __name__ == "__main__":
    process_scraped_data()
