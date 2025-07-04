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
t = Translator()

def translate(text: str) -> str:
    try:
        return t.translate(text, dest='en').text
    except Exception as e:
        logging.warning(f"Translation failed for '{text}': {e}")
        return text

# Logging setup: INFO and above
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

# Validate environment variables
for var in ("WEBFLOW_API_TOKEN", "WEBFLOW_COLLECTION_ID", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_UPLOAD_PRESET"):
    if not os.getenv(var):
        logging.error(f"Environment variable {var} is not set.")
        exit(1)

# Cloudinary upload helper
def upload_image_to_cloudinary(image_path, page_id):
    logging.info(f"Uploading image {os.path.basename(image_path)} to Cloudinary in folder '{page_id}'")
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    for attempt in range(1, 4):
        try:
            with open(image_path, 'rb') as img_f:
                data = {"upload_preset": CLOUDINARY_UPLOAD_PRESET, "folder": str(page_id)}
                resp = requests.post(url, files={"file": img_f}, data=data)
            if resp.status_code == 200:
                secure_url = resp.json().get("secure_url")
                logging.info(f"Cloudinary upload succeeded: {secure_url}")
                return secure_url
            logging.error(f"Cloudinary upload failed (attempt {attempt}): {resp.status_code} {resp.text}")
        except Exception as e:
            logging.warning(f"Cloudinary upload attempt {attempt} error: {e}")
    logging.error(f"Cloudinary upload ultimately failed for {image_path}")
    return None

# Webflow upload helper
def upload_to_webflow(data):
    logging.info("Uploading item to Webflow...")
    headers = {
        "Authorization": f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Version": "1.0.0"
    }
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"
    payload = {
        "items": [
            {
                **data["fields"],
                "multi-image": data["fields"].get("multi-image", [])[:25]
            }
        ]
    }
    body = json.dumps(payload, ensure_ascii=False)
    logging.info(f"POSTing to Webflow with payload: {body}")
    try:
        resp = requests.post(url, headers=headers, data=body.encode("utf-8"))
        if resp.status_code in (200, 201):
            logging.info("Webflow upload succeeded.")
            return True
        logging.error(f"Webflow upload error {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logging.error(f"Exception during Webflow upload: {e}")
        return False

# Scrape function
def scrape_page(page_id, playwright):
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Starting scrape for page {page_id}: {url}")
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.goto(url)
        if page.url.rstrip('/') == HOMEPAGE_URL:
            logging.info(f"Page {page_id} redirected to homepage, skipping.")
            return False

        # Title & Description
        raw_title = page.query_selector('h1').inner_text().strip() if page.query_selector('h1') else ''
        title = translate(raw_title) or f"Property {page_id}"
        logging.info(f"Extracted title: {title}")

        raw_desc = page.query_selector('.description').inner_text().strip() if page.query_selector('.description') else ''
        desc = translate(raw_desc)
        logging.info(f"Extracted description (truncated): {desc[:60]}...")

        property_info, room_info = {}, {}
        # Parse tables for info
        for tbl in page.query_selector_all('table'):
            headers = [th.inner_text().strip() for th in tbl.query_selector_all('tr:nth-of-type(1) th')]
            if '種別' in headers:
                logging.info("Parsing property info table")
                row1 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(2) td')]
                parts = row1[2].splitlines() if len(row1) > 2 else ['']
                property_info = {
                    'property_type': translate(row1[0]) if len(row1) > 0 else '',
                    'location': translate(row1[1]) if len(row1) > 1 else '',
                    'structure': translate(parts[0]),
                    'floors': translate(parts[1]) if len(parts) > 1 else '',
                    'parking': translate(row1[3]) if len(row1) > 3 else ''
                }
                logging.info(f"Property info: {property_info}")
                row2 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(4) td')]
                if len(row2) >= 4:
                    property_info.update({
                        'layout': translate(row2[0]),
                        'elevator': translate(row2[1]),
                        'completion_date': translate(row2[2]),
                        'units': [translate(u) for u in row2[3].split()]
                    })
                    logging.info(f"Extended property info: {property_info}")
            if '家賃' in headers:
                logging.info("Parsing room info table")
                r1 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(2) td')]
                if len(r1) >= 4:
                    room_info = dict(zip(['rent','area','deposit','key_money'], [translate(v) for v in r1]))
                logging.info(f"Room basic info: {room_info}")
                r2 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(4) td')]
                if len(r2) >= 4:
                    room_info.update({
                        'water_fee': translate(r2[0]),
                        'common_service_fee': translate(r2[1]),
                        'year_built': translate(r2[2]),
                        'balcony_direction': translate(r2[3])
                    })
                logging.info(f"Extended room info: {room_info}")

        # Map link
        map_el = page.query_selector("a:has-text('大きな地図で見る')")
        map_link = map_el.get_attribute('href') if map_el else ''
        logging.info(f"Map link extracted: {map_link}")

        # Download & upload images
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        img_dir = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(img_dir, exist_ok=True)
        images = []
        for img in page.query_selector_all('img'):
            src = img.get_attribute('src') or ''
            filename = src.split('/')[-1]
            if not filename or not filename[0].isdigit():
                continue
            local_path = os.path.join(img_dir, f"MAIDO_{datetime.now().strftime('%Y%m%d')}_{len(images)+1}.jpg")
            with open(local_path, 'wb') as f:
                f.write(requests.get(src).content)
            logging.info(f"Downloaded image to {local_path}")
            url = upload_image_to_cloudinary(local_path, page_id)
            if url:
                images.append({'url': url})
        logging.info(f"Total images uploaded: {len(images)}")

        # Build and upload payload
        payload_fields = {
            'name': title,
            'slug': f"property-{page_id}-{int(datetime.now().timestamp())}",
            '_archived': False,
            '_draft': False,
            'description': f"<p>{desc}</p>",
            'multi-image': images,
            'map_link': map_link,
            'district': '6672b625a00e8f837e7b4e68',
            'category': '665b099bc0ffada56b489baf'
        }
        payload_fields.update(property_info)
        payload_fields.update(room_info)
        logging.info("Final payload fields ready for Webflow upload")
        if not upload_to_webflow({'fields': payload_fields}):
            logging.error(f"Failed to upload page {page_id} to Webflow")
            return False

        logging.info(f"Page {page_id} scraped and uploaded successfully.")
        return True
    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False
    finally:
        browser.close()

# Main loop
if __name__ == '__main__':
    try:
        current = int(open('last_page.txt').read().strip()) + 1
    except Exception:
        current = START_PAGE
    bad = 0
    with sync_playwright() as playwright:
        while bad < MAX_CONSECUTIVE_INVALID:
            if scrape_page(current, playwright):
                bad = 0
            else:
                bad += 1
            open('last_page.txt', 'w').write(str(current))
            current += 1
