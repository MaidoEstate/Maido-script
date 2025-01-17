import os
import json
import logging
import requests

# Configuration
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")

# Logging setup
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s")

# Validate Environment Variables
def validate_env_vars():
    required_env_vars = ["WEBFLOW_API_TOKEN", "WEBFLOW_COLLECTION_ID"]
    for var in required_env_vars:
        if not os.getenv(var):
            logging.error(f"Environment variable {var} is not set.")
            exit(1)

# Upload data to Webflow
def upload_to_webflow(data):
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code in (200, 201):
            logging.info(f"Uploaded item to Webflow: {response.json()}")
        else:
            logging.error(f"Failed to upload item to Webflow: {response.status_code}, {response.text}")
    except Exception as e:
        logging.error(f"Error uploading to Webflow: {e}")

# Prepare Data and Upload to Webflow
def main():
    validate_env_vars()

    # Example data to upload
    data = {
        "fields": {
            "name": "Sample Property",
            "slug": "sample-property",
            "_archived": False,
            "_draft": False,
            "description": "<p>This is a sample property description.</p>",
            "multi-image": [
                {"url": "https://example.com/image1.jpg"},
                {"url": "https://example.com/image2.jpg"}
            ],
            "district": "6672b625a00e8f837e7b4e68",  # Example district ID
            "category": "665b099bc0ffada56b489baf",  # Example category ID
        }
    }

    # Log data
    logging.info("Preparing to upload the following data to Webflow:")
    logging.info(json.dumps(data, indent=2))
    
    # Upload to Webflow
    upload_to_webflow(data)

if __name__ == "__main__":
    main()
