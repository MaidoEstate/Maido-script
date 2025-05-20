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
    except Exception:
        return text

# Logging setup: show only INFO and above
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

# Validate environment variables
for var in ("WEBFLOW_API_TOKEN", "WEBFLOW_COLLECTION_ID", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_UPLOAD_PRESET"):
    if not os.getenv(var):
        logging.error(f"Environment variable {var} is not set.")
        exit(1)

# Cloudinary upload helper
def upload_image_to_cloudinary(image_path, page_id):
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    for _ in range(3):
        try:
            with open(image_path, 'rb') as img_f:
                data = {"upload_preset": CLOUDINARY_UPLOAD_PRESET, "folder": str(page_id)}
                resp = requests.post(url, files={"file": img_f}, data=data)
            if resp.status_code == 200:
                return resp.json().get("secure_url")
        except Exception as e:
            logging.warning(f"Cloudinary upload attempt failed: {e}")
    logging.error(f"Cloudinary upload failed for {image_path}")
    return None

# Webflow upload helper
def upload_to_webflow(data):
    headers = {"Authorization": f"Bearer {WEBFLOW_API_TOKEN}", "Content-Type": "application/json; charset=utf-8"}
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"
    payload = {"items": [{**data['fields'], 'multi-image': data['fields'].get('multi-image', [])[:25]}]}
    body = json.dumps(payload, ensure_ascii=False)
    try:
        resp = requests.post(url, headers=headers, data=body.encode('utf-8'))
        if resp.status_code not in (200, 201):
            logging.error(f"Webflow upload failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logging.error(f"Error uploading to Webflow: {e}")

# Scrape function
def scrape_page(page_id, playwright):
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Scraping {page_id}")
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.goto(url)
        if page.url.rstrip('/') == HOMEPAGE_URL:
            logging.info(f"Page {page_id} skipped (redirect)")
            return False

        # Title & Description
        raw_title = page.query_selector('h1').inner_text().strip() if page.query_selector('h1') else ''
        title = translate(raw_title) or f"Property {page_id}"

        raw_desc = page.query_selector('.description').inner_text().strip() if page.query_selector('.description') else ''
        desc = translate(raw_desc)

        property_info, room_info = {}, {}
        # Parse tables
        for tbl in page.query_selector_all('table'):
            hdrs = [th.inner_text().strip() for th in tbl.query_selector_all('tr:nth-of-type(1) th')]
            if '種別' in hdrs:
                vals1 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(2) td')]
                parts = vals1[2].splitlines() if len(vals1) > 2 else ['']
                property_info = {
                    'property_type': translate(vals1[0]) if vals1 else '',
                    'location': translate(vals1[1]) if len(vals1) > 1 else '',
                    'structure': translate(parts[0]),
                    'floors': translate(parts[1]) if len(parts) > 1 else '',
                    'parking': translate(vals1[3]) if len(vals1) > 3 else ''
                }
                vals2 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(4) td')]
                if len(vals2) >= 4:
                    property_info.update({
                        'layout': translate(vals2[0]),
                        'elevator': translate(vals2[1]),
                        'completion_date': translate(vals2[2]),
                        'units': [translate(u) for u in vals2[3].split()]
                    })
                eq = tbl.query_selector("tr:has-text('物件設備') td")
                property_info['property_equipment'] = [translate(x) for x in eq.inner_text().split()] if eq else []
                trn = tbl.query_selector("tr:has-text('交通') td")
                property_info['transportation'] = translate(trn.inner_text().strip()) if trn else ''
            if '家賃' in hdrs:
                r1 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(2) td')]
                if len(r1) >= 4:
                    room_info = {k: translate(v) for k, v in zip(['rent','area','deposit','key_money'], r1)}
                r2 = [td.inner_text().strip() for td in tbl.query_selector_all('tr:nth-of-type(4) td')]
                if len(r2) >= 4:
                    room_info.update({
                        'water_fee': translate(r2[0]),
                        'common_service_fee': translate(r2[1]),
                        'year_built': translate(r2[2]),
                        'balcony_direction': translate(r2[3])
                    })
                re = tbl.query_selector("tr:has-text('部屋設備') td")
                room_info['room_equipment'] = [translate(x) for x in re.inner_text().split()] if re else []

        # Map link
        map_el = page.query_selector("a:has-text('大きな地図で見る')")
        map_link = map_el.get_attribute('href') if map_el else ''

        # Images
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        img_dir = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(img_dir, exist_ok=True)
        images = []
        for img in page.query_selector_all('img'):
            src = img.get_attribute('src') or ''
            fn = src.split('/')[-1]
            if not fn or not fn[0].isdigit(): continue
            lp = os.path.join(img_dir, f"MAIDO_{datetime.now().strftime('%Y%m%d')}_{len(images)+1}.jpg")
            with open(lp,'wb') as f: f.write(requests.get(src).content)
            cu = upload_image_to_cloudinary(lp, page_id)
            if cu: images.append({'url': cu})

        # Build payload
        fields = {
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
        fields.update(property_info)
        fields.update(room_info)
        upload_to_webflow({'fields': fields})
        logging.info(f"Page {page_id} done")
        return True
    except Exception as e:
        logging.error(f"Error {page_id}: {e}")
        return False
    finally:
        browser.close()

# Main loop
if __name__ == '__main__':
    try: current = int(open('last_page.txt').read().strip()) + 1
    except: current = START_PAGE
    bad = 0
    with sync_playwright() as p:
        while bad < MAX_CONSECUTIVE_INVALID:
            if scrape_page(current, p): bad = 0
            else: bad += 1
            open('last_page.txt','w').write(str(current))
            current += 1
