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
                cloudinary_url = response.json().get("secure_url")
                logging.debug(f"Image uploaded to Cloudinary: {cloudinary_url}")
                return cloudinary_url
            logging.error(f"Cloudinary upload failed: {response.status_code} - {response.text}")
        except Exception as e:
            logging.warning(f"Retry {attempt + 1}/3 for Cloudinary upload: {e}")
    logging.error("Cloudinary upload failed after 3 attempts.")
    return None

# Upload data to Webflow
def upload_to_webflow(data):
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json",
    }
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"

    payload = {
        "items": [
            {
                "name": data["fields"].get("name", "Default Name"),
                "slug": data["fields"].get("slug", f"default-slug-{int(datetime.now().timestamp())}"),
                "_archived": False,
                "_draft": False,
                "description": data["fields"].get("description", "<p>No Description</p>"),
                "multi-image": data["fields"].get("multi-image", [])[:25],
                "district": data["fields"].get("district"),
                "category": data["fields"].get("category"),
            }
        ]
    }

    try:
        logging.debug(f"Uploading to Webflow: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        logging.debug(f"Webflow Response: {response.status_code} - {response.text}")
        if response.status_code in (200, 201):
            logging.info("Uploaded item to Webflow successfully.")
        else:
            logging.error(f"Webflow upload failed: {response.status_code} - {response.text}")
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
        # Skip if redirected to homepage
        if page.url == "https://www.designers-osaka-chintai.info/":
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return False

        # Extract title
        title = None
        for h1 in page.query_selector_all("h1"):
            text = h1.inner_text().strip()
            if text != "大阪デザイナーズマンション専門サイト キワミ":
                title = text
                break
        if not title:
            title = "No Title"
        logging.info(f"Title for page {page_id}: {title}")

        # Extract description
        desc_el = page.query_selector(".description")
        description = desc_el.inner_text().strip() if desc_el else "No Description"

        # Extract property info (first table)
        tables = page.query_selector_all("table")
        property_info = {}
        if len(tables) >= 1:
            prop_table = tables[0]
            # First value row
            vals1 = [td.inner_text().strip() for td in prop_table.query_selector_all("tr:nth-of-type(2) td")]
            # Structure and floors are split by newline
            struct_lines = vals1[2].splitlines()
            property_info.update({
                "property_type": vals1[0],
                "location": vals1[1],
                "structure": struct_lines[0] if struct_lines else "",
                "floors": struct_lines[1] if len(struct_lines) > 1 else "",
                "parking": vals1[3]
            })
            # Second value row
            vals2 = [td.inner_text().strip() for td in prop_table.query_selector_all("tr:nth-of-type(4) td")]
            property_info.update({
                "layout": vals2[0],
                "elevator": vals2[1],
                "completion_date": vals2[2],
                "units": vals2[3].split()
            })
            # Equipment list
            eq_el = prop_table.query_selector("tr:has-text('物件設備') td")
            equipment = eq_el.inner_text().strip().split() if eq_el else []
            property_info["property_equipment"] = equipment
            # Transportation
            trans_el = prop_table.query_selector("tr:has-text('交通') td")
            property_info["transportation"] = trans_el.inner_text().strip() if trans_el else ""

        # Extract room info (second table)
        room_info = {}
        if len(tables) >= 2:
            room_table = tables[1]
            # Rent, area, deposit, key money
            vals_r1 = [td.inner_text().strip() for td in room_table.query_selector_all("tr:nth-of-type(2) td")]
            room_info.update({
                "rent": vals_r1[0],
                "area": vals_r1[1],
                "deposit": vals_r1[2],
                "key_money": vals_r1[3]
            })
            # Water, common fee, built, balcony direction
            vals_r2 = [td.inner_text().strip() for td in room_table.query_selector_all("tr:nth-of-type(4) td")]
            room_info.update({
                "water_fee": vals_r2[0],
                "common_service_fee": vals_r2[1],
                "year_built": vals_r2[2],
                "balcony_direction": vals_r2[3]
            })
            # Room equipment
            room_eq_el = room_table.query_selector("tr:has-text('部屋設備') td")
            room_equips = room_eq_el.inner_text().strip().split() if room_eq_el else []
            room_info["room_equipment"] = room_equips

        # Create output folder and download/upload images
        page_folder = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(page_folder, exist_ok=True)

        images = []
        for img in page.query_selector_all("img"):
            img_url = img.get_attribute("src")
            if img_url and img_url.startswith("http") and img_url.split("/")[-1][0].isdigit():
                img_name = f"MAIDO_{datetime.now().strftime('%Y%m%d')}_{len(images)+1}.jpg"
                image_path = os.path.join(page_folder, img_name)
                with open(image_path, "wb") as f:
                    f.write(requests.get(img_url).content)
                cloud_url = upload_image_to_cloudinary(image_path)
                if cloud_url:
                    images.append({"url": cloud_url})

        # Prepare Webflow payload
        webflow_data = {
            "fields": {
                "name": title,
                "slug": f"property-{page_id}-{int(datetime.now().timestamp())}",
                "_archived": False,
                "_draft": False,
                "description": f"<p>{description}</p>",
                "multi-image": images[:25],
                "district": "6672b625a00e8f837e7b4e68",
                "category": "665b099bc0ffada56b489baf",
            }
        }
        # Merge info
        webflow_data["fields"].update(property_info)
        webflow_data["fields"].update(room_info)

        # Upload to Webflow
        upload_to_webflow(webflow_data)
        logging.info(f"Page {page_id} scraped and uploaded successfully.")
        return True

    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False

    finally:
        browser.close()

# Main function
if __name__ == "__main__":
    try:
        with open("last_page.txt", "r") as f:
            current_page = int(f.read().strip()) + 1
    except FileNotFoundError:
        current_page = START_PAGE

    consecutive_invalid = 0
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with sync_playwright() as playwright:
        while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
            if scrape_page(current_page, playwright):
                with open("last_page.txt", "w") as f:
                    f.write(str(current_page))
                consecutive_invalid = 0
            else:
                consecutive_invalid += 1
            current_page += 1
