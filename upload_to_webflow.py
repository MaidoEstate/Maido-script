import os
import json
import logging
import requests
import time

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
        logging.debug(f"Uploading to Webflow: {json.dumps(data, indent=2)}")
        response = requests.post(url, headers=headers, json=data)
        logging.debug(f"Response Status Code: {response.status_code}")
        logging.debug(f"Response Text: {response.text}")
        if response.status_code in (200, 201):
            logging.info(f"Uploaded item to Webflow successfully: {response.json()}")
        else:
            logging.error(f"Failed to upload item to Webflow: {response.status_code}, {response.text}")
    except Exception as e:
        logging.error(f"Error uploading to Webflow: {e}")

# Retry Logic for Webflow Uploads
def upload_to_webflow_with_retry(data, retries=3):
    for attempt in range(retries):
        try:
            upload_to_webflow(data)
            return  # Exit on success
        except Exception as e:
            logging.warning(f"Retry {attempt + 1}/{retries} for Webflow upload due to: {e}")
            time.sleep(2)  # Wait before retrying
    logging.error("Failed to upload item to Webflow after retries.")

# Prepare Data and Upload to Webflow
def main():
    validate_env_vars()

    # Example payload to upload to Webflow
    data = {
        "fields": {
            "name": "Sample Property",
            "slug": f"sample-property-{int(time.time())}",  # Unique slug
            "_archived": False,
            "_draft": False,
            "description": "<p>This is a sample property description.</p>",
            "multi-image": [
                {"url": "https://example.com/image1.jpg"},
                {"url": "https://example.com/image2.jpg"}
            ],
            "district": "6672b625a00e8f837e7b4e68",  # Example district ID (must exist in Webflow)
            "category": "665b099bc0ffada56b489baf",  # Example category ID (must exist in Webflow)
        }
    }

    logging.info("Preparing to upload the following data to Webflow:")
    logging.info(json.dumps(data, indent=2))

    # Upload with retry logic
    upload_to_webflow_with_retry(data)

if __name__ == "__main__":
    main()
