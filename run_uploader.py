import os
import json
import logging
import requests

# Configuration
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")  # Loaded from GitHub Secrets
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")  # Set as a GitHub Secret or hardcoded
WEBFLOW_API_URL = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"
HEADERS = {
    "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
    "Content-Type": "application/json",
    "Accept-Version": "1.0.0",
}

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

# Helper Function to Upload an Image to Webflow CDN
def upload_image_to_webflow(image_path):
    try:
        with open(image_path, "rb") as image_file:
            image_name = os.path.basename(image_path)
            files = {"file": (image_name, image_file)}
            response = requests.post(
                "https://api.webflow.com/upload",
                headers={"Authorization": f"Bearer {WEBFLOW_API_TOKEN}", "Accept-Version": "1.0.0"},
                files=files,
            )
            response.raise_for_status()
            image_url = response.json().get("url")
            if image_url:
                logging.info(f"Image uploaded successfully: {image_url}")
                return image_url
            else:
                logging.error(f"Failed to upload image: {image_path}")
                return None
    except Exception as e:
        logging.error(f"Error uploading image {image_path}: {e}")
        return None

# Function to Upload a Property to Webflow CMS
def upload_property_to_webflow(property_data):
    try:
        # Prepare images for upload
        big_images = []
        small_images = []

        for image in property_data.get("big_images", []):
            image_path = os.path.join("scraped_data", str(property_data["page_id"]), image)
            uploaded_image_url = upload_image_to_webflow(image_path)
            if uploaded_image_url:
                big_images.append(uploaded_image_url)

        for image in property_data.get("small_images", []):
            image_path = os.path.join("scraped_data", str(property_data["page_id"]), image)
            uploaded_image_url = upload_image_to_webflow(image_path)
            if uploaded_image_url:
                small_images.append(uploaded_image_url)

        # Prepare data for Webflow CMS
        cms_data = {
            "fields": {
                "name": property_data["title"],
                "slug": f"property-{property_data['page_id']}",
                "description": property_data["description"],
                "bigImages": big_images,
                "smallImages": small_images,
                "_archived": False,
                "_draft": False,
            }
        }

        # Make API request to create a CMS item
        response = requests.post(WEBFLOW_API_URL, headers=HEADERS, json=cms_data)
        response.raise_for_status()

        logging.info(f"Property uploaded successfully: {property_data['title']} (Page ID: {property_data['page_id']})")
    except Exception as e:
        logging.error(f"Failed to upload property {property_data['page_id']}: {e}")

# Main Function to Process and Upload Scraped Data
def main():
    # Ensure Webflow API token is set
    if not WEBFLOW_API_TOKEN:
        logging.error("WEBFLOW_API_TOKEN is not set. Please check your GitHub Secrets.")
        return

    if not WEBFLOW_COLLECTION_ID:
        logging.error("WEBFLOW_COLLECTION_ID is not set. Please check your GitHub Secrets or script configuration.")
        return

    # Check the scraped data directory
    scraped_data_dir = "scraped_data"
    if not os.path.exists(scraped_data_dir):
        logging.error(f"Scraped data directory does not exist: {scraped_data_dir}")
        return

    # Process each property JSON file
    for root, _, files in os.walk(scraped_data_dir):
        for file in files:
            if file.endswith(".json"):
                json_path = os.path.join(root, file)
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        property_data = json.load(f)
                    upload_property_to_webflow(property_data)
                except Exception as e:
                    logging.error(f"Failed to process file {json_path}: {e}")

if __name__ == "__main__":
    main()
