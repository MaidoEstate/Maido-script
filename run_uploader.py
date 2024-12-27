import os
import requests
import logging
import json

# Configuration
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")  # Ensure this is set in your GitHub secrets or environment variables
WEBFLOW_COLLECTION_ID = "<Your_Webflow_Collection_ID>"  # Replace with your actual Webflow CMS collection ID
BASE_DIRECTORY = "./scraped_data"  # Ensure this matches your scraper's output directory

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

if not WEBFLOW_API_TOKEN:
    logging.error("WEBFLOW_API_TOKEN is not set. Check your environment variables or GitHub Actions secrets.")
    exit(1)

if not WEBFLOW_COLLECTION_ID:
    logging.error("WEBFLOW_COLLECTION_ID is not set. Ensure you've added the correct collection ID.")
    exit(1)

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
        if response.status_code == 200 or response.status_code == 201:
            logging.info("Item successfully uploaded to Webflow.")
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
                # Read property details CSV
                csv_file = os.path.join(page_path, "property_details.csv")
                with open(csv_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if len(lines) < 2:
                        logging.warning(f"No data found in {csv_file}")
                        continue
                    headers = lines[0].strip().split(",")
                    values = lines[1].strip().split(",")
                    property_data = dict(zip(headers, values))

                # Prepare data for Webflow
                webflow_data = {
                    "fields": {
                        "name": property_data.get("Title", "Untitled Property"),
                        "slug": f"property-{page_folder}",
                        "description": property_data.get("Description", "No description available."),
                        "_archived": False,
                        "_draft": False,
                    }
                }

                # Upload images
                images = []
                for image_file in os.listdir(page_path):
                    if image_file.endswith(('.jpg', '.jpeg', '.png')):
                        images.append(image_file)  # You need to host these images externally

                if images:
                    webflow_data["fields"]["images"] = images  # Replace with actual Webflow image field key

                upload_to_webflow(webflow_data)

            except Exception as e:
                logging.error(f"Error processing data for folder {page_folder}: {e}")

if __name__ == "__main__":
    logging.info("Starting Webflow CMS upload process...")
    process_scraped_data()
    logging.info("Webflow CMS upload process completed.")
