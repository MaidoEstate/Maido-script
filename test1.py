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
DEFAULT_TITLE_KEYWORD = "大阪デザイナーズマンション専門サイト"

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
                return response.json().get("secure_url")
            logging.error(f"Cloudinary upload failed: {response.status_code} - {response.text}")
        except Exception as e:
            logging.warning(f"Retry {attempt + 1}/3 for Cloudinary upload: {e}")
    return None

# Upload data to Webflow
def upload_to_webflow(data):
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"
    payload = {
        "items": [{ **data["fields"], "multi-image": data["fields"].get("multi-image", [])[:25] }]
    }
    try:
        logging.debug(f"Uploading to Webflow: {json.dumps(payload, indent=2)}")
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            logging.info("Uploaded item to Webflow successfully.")
        else:
            logging.error(f"Webflow upload failed: {resp.status_code} - {resp.text}")
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
        if page.url.rstrip('/') == "https://www.designers-osaka-chintai.info":
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return False

        # Extract title
        title = None
        for h1 in page.query_selector_all("h1"):
            text = h1.inner_text().strip()
            if DEFAULT_TITLE_KEYWORD not in text:
                title = text
                break
        if not title:
            logging.warning(f"Page {page_id} has no valid title. Skipping.")
            return False
        logging.info(f"Title for page {page_id}: {title}")

        # Description
        desc_el = page.query_selector(".description")
        description = desc_el.inner_text().strip() if desc_el else ""

        # Tables
        tables = page.query_selector_all("table")
        property_info, room_info = {}, {}
        if tables:
            # Property table
            prop = tables[0]
            vals1 = [td.inner_text().strip() for td in prop.query_selector_all("tr:nth-of-type(2) td")]
            if len(vals1) >= 4:
                struct = vals1[2].splitlines()
                property_info = {
                    "property_type": vals1[0],
                    "location": vals1[1],
                    "structure": struct[0] if struct else "",
                    "floors": struct[1] if len(struct)>1 else "",
                    "parking": vals1[3]
                }
            vals2 = [td.inner_text().strip() for td in prop.query_selector_all("tr:nth-of-type(4) td")]
            if len(vals2) >= 4:
                property_info.update({
                    "layout": vals2[0],
                    "elevator": vals2[1],
                    "completion_date": vals2[2],
                    "units": vals2[3].split()
                })
            eq = prop.query_selector("tr:has-text('物件設備') td")
            property_info["property_equipment"] = eq.inner_text().split() if eq else []
            trans = prop.query_selector("tr:has-text('交通') td")
            property_info["transportation"] = trans.inner_text().strip() if trans else ""

        if len(tables) > 1:
            # Room table
            room = tables[1]
            vals_r1 = [td.inner_text().strip() for td in room.query_selector_all("tr:nth-of-type(2) td")]
            if len(vals_r1) >= 4:
                room_info = {
                    "rent": vals_r1[0],
                    "area": vals_r1[1],
                    "deposit": vals_r1[2],
                    "key_money": vals_r1[3]
                }
            vals_r2 = [td.inner_text().strip() for td in room.query_selector_all("tr:nth-of-type(4) td")]
            if len(vals_r2) >= 4:
                room_info.update({
                    "water_fee": vals_r2[0],
                    "common_service_fee": vals_r2[1],
                    "year_built": vals_r2[2],
                    "balcony_direction": vals_r2[3]
                })
            req = room.query_selector("tr:has-text('部屋設備') td")
            room_info["room_equipment"] = req.inner_text().split() if req else []

        # Images
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        page_folder = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(page_folder, exist_ok=True)
        images = []
        for img in page.query_selector_all("img"):
            src = img.get_attribute("src")
            if src and src.startswith("http") and src.split('/')[-1][0].isdigit():
                fname = f"MAIDO_{datetime.now().strftime('%Y%m%d')}_{len(images)+1}.jpg"
                path = os.path.join(page_folder, fname)
                with open(path, 'wb') as f:
                    f.write(requests.get(src).content)
                url = upload_image_to_cloudinary(path)
                if url:
                    images.append({"url": url})

        # Build payload
        fields = {
            "name": title,
            "slug": f"property-{page_id}-{int(datetime.now().timestamp())}",
            "_archived": False,
            "_draft": False,
            "description": f"<p>{description}</p>",
            "multi-image": images,
            "district": "6672b625a00e8f837e7b4e68",
            "category": "665b099bc0ffada56b489baf"
        }
        fields.update(property_info)
        fields.update(room_info)

        upload_to_webflow({"fields": fields})
        return True
    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False
    finally:
        browser.close()

# Main loop
if __name__ == "__main__":
    try:
        with open("last_page.txt") as f:
            current = int(f.read().strip()) + 1
    except FileNotFoundError:
        current = START_PAGE
    invalid = 0
    while invalid < MAX_CONSECUTIVE_INVALID:
        with sync_playwright() as pw:
            if scrape_page(current, pw):
                with open("last_page.txt", "w") as f:
                    f.write(str(current))
                invalid = 0
            else:
                invalid += 1
        current += 1
