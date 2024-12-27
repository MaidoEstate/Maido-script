import os
import requests
import logging
import json

# Configuration
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")  # Ensure this is set in your GitHub secrets or environment variables
WEBFLOW_COLLECTION_ID = "665b06933a06a0a4893b7af2"  # Replace with your actual Webflow CMS collection ID
BASE_DIRECTORY = "./scraped_data"  # Ensure this matches your scraper's output directory
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

# Check essential configuration
if not WEBFLOW_API_TOKEN:
    logging.error("WEBFLOW_API_TOKEN is not set. Check your environment variables or GitHub Actions secrets.")
    exit(1)

if not WEBFLOW_COLLECTION_ID:
    logging.error("WEBFLOW_COLLECTION_ID is not set. Ensure you've added the correct collection ID.")
    exit(1)

if not (CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
    logging.error("Cloudinary configuration is incomplete. Ensure all Cloudinary credentials are set.")
    exit(1)

def upload_image_to_cloudinary(image_path):
    """
    Upload an image to Cloudinary and return its URL.
    """
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    with open(image_path, "rb") as image_file:
        response = requests.post(url, files={"file": image_file}, data={"upload_preset": "default"})
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

def process_scraped_data():
    """
    Read and process scraped data, then upload it to Webflow.
    """
    for page_folder in os.listdir(BASE_DIRECTORY):
        page_path = os.path.join(BASE_DIRECTORY, page_folder)
        if os.path.isdir(page_path):
            try:
                # Read property details JSON
                json_file = os.path.join(page_path, f"property_{page_folder}.json")
                if not os.path.exists(json_file):
                    logging.warning(f"No JSON file found in {page_path}")
                    continue

                with open(json_file, "r", encoding="utf-8") as f:
                    property_data = json.load(f)

                # Prepare data for Webflow
                webflow_data = {
                    "fields": {
                        "name": property_data.get("title", "Untitled Property"),
                        "slug": f"property-{property_data['page_id']}",
                        "description": property_data.get("description", "No description available."),
                        "_archived": False,
                        "_draft": False,
                    }
                }

                # Upload images to Cloudinary
                hosted_images = []
                for image_file in property_data.get("big_images", []) + property_data.get("small_images", []):
                    image_path = os.path.join(page_path, image_file)
                    if os.path.exists(image_path):
                        image_url = upload_image_to_cloudinary(image_path)
                        if image_url:
                            hosted_images.append(image_url)

                if hosted_images:
                    webflow_data["fields"]["images"] = hosted_images  # Replace with actual Webflow image field key

                upload_to_webflow(webflow_data)

            except Exception as e:
                logging.error(f"Error processing data for folder {page_folder}: {e}")

if __name__ == "__main__":
    logging.info("Starting Webflow CMS upload process...")
    process_scraped_data()
    logging.info("Webflow CMS upload process completed.")
