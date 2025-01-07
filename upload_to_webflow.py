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
BASE_DIRECTORY = os.getenv("OUTPUT_DIR", "./scraped_data")

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

def upload_image_to_cloudinary(image_path):
    """Upload an image to Cloudinary and return its URL."""
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"

    with open(image_path, "rb") as image_file:
        files = {"file": image_file}
        data = {
            "api_key": CLOUDINARY_API_KEY,  
            "timestamp": str(int(time.time())),  
            "folder": "real_estate",  # Optional: Organize in Cloudinary folders
        }

        # If using unsigned upload, require an "upload_preset"
        UPLOAD_PRESET = "default"  # Replace with your actual Cloudinary preset name
        if UPLOAD_PRESET:
            data["upload_preset"] = UPLOAD_PRESET
        else:
            # If using signed upload, generate a signature
            import hashlib, hmac
            sorted_params = "&".join(f"{k}={v}" for k, v in sorted(data.items()))
            signature = hmac.new(CLOUDINARY_API_SECRET.encode(), sorted_params.encode(), hashlib.sha256).hexdigest()
            data["signature"] = signature
            data["api_key"] = CLOUDINARY_API_KEY  

        response = requests.post(url, files=files, data=data)

    if response.status_code == 200:
        return response.json()["secure_url"]
    else:
        logging.error(f"Failed to upload image: {response.status_code}, {response.text}")
        return None

def process_scraped_data():
    """Process all scraped data and upload it to Webflow."""
    for page_folder in os.listdir(BASE_DIRECTORY):
        page_path = os.path.join(BASE_DIRECTORY, page_folder)
        if os.path.isdir(page_path):
            try:
                json_file = os.path.join(page_path, f"property_{page_folder}.json")
                if not os.path.exists(json_file):
                    logging.warning(f"No JSON file found in {page_path}")
                    continue

                with open(json_file, "r", encoding="utf-8") as f:
                    property_data = json.load(f)

                # Upload images
                hosted_images = []
                for image_file in property_data.get("big_images", []) + property_data.get("small_images", []):
                    image_path = os.path.join(page_path, image_file)
                    if os.path.exists(image_path):
                        image_url = upload_image_to_cloudinary(image_path)
                        if image_url:
                            hosted_images.append(image_url)

                # Prepare data for Webflow
                webflow_data = {
                    "fields": {
                        "name": property_data.get("title", "Untitled Property"),
                        "slug": f"property-{property_data['page_id']}",
                        "description": property_data.get("description", "No description."),
                        "_archived": False,
                        "_draft": False,
                        "images": hosted_images,
                    }
                }

                upload_to_webflow(webflow_data)

            except Exception as e:
                logging.error(f"Error processing {page_folder}: {e}")

if __name__ == "__main__":
    logging.info("Starting Webflow upload process...")
    process_scraped_data()
    logging.info("Webflow upload process completed.")
