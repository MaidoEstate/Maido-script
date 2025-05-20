import os
import json
import requests
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright
from googletrans import Translator  # pip install googletrans

# Configuration
START_PAGE = int(os.getenv("START_PAGE", 12453))
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
HOMEPAGE_URL = "https://www.designers-osaka-chintai.info"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_UPLOAD_PRESET = os.getenv("CLOUDINARY_UPLOAD_PRESET")
MAX_CONSECUTIVE_INVALID = 10

# Initialize translator
translator = Translator()

def translate(text):
    try:
        return translator.translate(text, dest='en').text
    except Exception as e:
        logging.warning(f"Translation failed for '{text}': {e}")
        return text

# Logging setup
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s]: %(message)s")

# Validate environment variables
for var in ("WEBFLOW_API_TOKEN", "WEBFLOW_COLLECTION_ID", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_UPLOAD_PRESET"):
    if not os.getenv(var):
        logging.error(f"Environment variable {var} is not set.")
        exit(1)

# Cloudinary upload
def upload_image_to_cloudinary(image_path, page_id):
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    for attempt in range(3):
        try:
            with open(image_path, "rb") as image_file:
                data = {"upload_preset": CLOUDINARY_UPLOAD_PRESET, "folder": str(page_id)}
                resp = requests.post(url, files={"file": image_file}, data=data)
            if resp.status_code == 200:
                return resp.json().get("secure_url")
            logging.error(f"Cloudinary upload failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            logging.warning(f"Retry {attempt+1}/3 for Cloudinary upload failed: {e}")
    return None

# Webflow upload
def upload_to_webflow(data):
    headers = {"Authorization": f"Bearer {WEBFLOW_API_TOKEN}", "Content-Type": "application/json; charset=utf-8"}
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"
    payload = {"items": [{**data["fields"], "multi-image": data["fields"].get("multi-image", [])[:25]}]}
    payload_str = json.dumps(payload, ensure_ascii=False)
    try:
        logging.debug(f"Uploading payload: {payload_str}")
        response = requests.post(url, headers=headers, data=payload_str.encode('utf-8'))
        logging.debug(f"Webflow Response: {response.status_code} - {response.text}")
        if response.status_code in (200, 201):
            logging.info("Uploaded to Webflow successfully.")
        else:
            logging.error(f"Webflow upload failed: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"Error uploading to Webflow: {e}")

# Scrape one page
def scrape_page(page_id, playwright):
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Scraping URL: {url}")
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.goto(url)
        if page.url.rstrip('/') == HOMEPAGE_URL:
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return False

        # Title & description
        raw_title = page.query_selector("h1").inner_text().strip() if page.query_selector("h1") else ""
        title_jp = raw_title or f"Property {page_id}"
        title = translate(title_jp)
        logging.debug(f"Title JP: '{title_jp}' -> EN: '{title}'")

        raw_desc = page.query_selector(".description").inner_text().strip() if page.query_selector(".description") else ""
        description = translate(raw_desc)
        logging.debug(f"Description JP: '{raw_desc}' -> EN: '{description}'")

        # Tables
        property_info, room_info = {}, {}
        for tbl in page.query_selector_all("table"):
            headers = [th.inner_text().strip() for th in tbl.query_selector_all("tr:nth-of-type(1) th")]
            if "種別" in headers:
                vals1 = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(2) td")]
                struct = vals1[2].splitlines() if len(vals1) > 2 else [""]
                # Translate each
                property_info = {
                    "property_type": translate(vals1[0]),
                    "location": translate(vals1[1]),
                    "structure": translate(struct[0]),
                    "floors": translate(struct[1] if len(struct) > 1 else ""),
                    "parking": translate(vals1[3] if len(vals1) > 3 else "")
                }
                logging.debug(f"Property JP: {vals1} -> EN: {property_info}")
                vals2 = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(4) td")]
                if len(vals2) >= 4:
                    property_info.update({
                        "layout": translate(vals2[0]),
                        "elevator": translate(vals2[1]),
                        "completion_date": translate(vals2[2]),
                        "units": [translate(u) for u in vals2[3].split()]
                    })
                    logging.debug(f"Property vals2 JP: {vals2} -> EN update: {property_info}")
                # Equipment & transport
                eq = tbl.query_selector("tr:has-text('物件設備') td")
                property_info["property_equipment"] = [translate(x) for x in eq.inner_text().split()] if eq else []
                tr_el = tbl.query_selector("tr:has-text('交通') td")
                property_info["transportation"] = translate(tr_el.inner_text().strip()) if tr_el else ""
            if "家賃" in headers:
                r1 = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(2) td")]
                if len(r1) >= 4:
                    room_info = {"rent": translate(r1[0]), "area": translate(r1[1]), "deposit": translate(r1[2]), "key_money": translate(r1[3])}
                logging.debug(f"Room vals_r1 JP: {r1} -> EN: {room_info}")
                r2 = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(4) td")]
                if len(r2) >= 4:
                    room_info.update({
                        "water_fee": translate(r2[0]),
                        "common_service_fee": translate(r2[1]),
                        "year_built": translate(r2[2]),
                        "balcony_direction": translate(r2[3])
                    })
                re_el = tbl.query_selector("tr:has-text('部屋設備') td")
                room_info["room_equipment"] = [translate(x) for x in re_el.inner_text().split()] if re_el else []
                logging.debug(f"Room vals_r2 JP: {r2} -> EN: {room_info}")

        # Map link
        map_el = page.query_selector("a:has-text('大きな地図で見る')")
        map_link = map_el.get_attribute("href") if map_el else ""

        # Images
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        page_dir = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(page_dir, exist_ok=True)
        images = []
        for img in page.query_selector_all("img"):
            src = img.get_attribute("src") or ""
            fname = src.split('/')[-1]
            if not fname or not fname[0].isdigit():
                continue
            local_path = os.path.join(page_dir, f"MAIDO_{datetime.now().strftime('%Y%m%d')}_{len(images)+1}.jpg")
            with open(local_path, 'wb') as f:
                f.write(requests.get(src).content)
            cloud_url = upload_image_to_cloudinary(local_path, page_id)
            if cloud_url:
                images.append({"url": cloud_url})

        # Build payload
        fields = {
            "name": title,
            "slug": f"property-{page_id}-{int(datetime.now().timestamp())}",
            "_archived": False,
            "_draft": False,
            "description": description,
            "multi-image": images,
            "map_link": map_link,
            "district": "6672b625a00e8f837e7b4e68",
            "category": "665b099bc0ffada56b489baf"
        }
        fields.update(property_info)
        fields.update(room_info)
        upload_to_webflow({"fields": fields})
        logging.info(f"Page {page_id} scraped and uploaded successfully.")
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
    consecutive_invalid = 0
    with sync_playwright() as playwright:
        while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
            if scrape_page(current, playwright):
                with open("last_page.txt", "w") as f:
                    f.write(str(current))
                consecutive_invalid = 0
            else:
                consecutive_invalid += 1
            current += 1
