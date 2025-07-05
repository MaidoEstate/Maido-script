import os
import json
import time
import logging
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright
from googletrans import Translator  # pip install googletrans

# ── Config ────────────────────────────────────────────────────────────────────
START_PAGE               = int(os.getenv("START_PAGE", 12453))
BASE_URL                 = "https://www.designers-osaka-chintai.info/detail/id/"
HOMEPAGE_URL             = "https://www.designers-osaka-chintai.info"
OUTPUT_DIR               = os.getenv("OUTPUT_DIR", "./scraped_data")
WEBFLOW_API_TOKEN        = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID    = os.getenv("WEBFLOW_COLLECTION_ID")
CLOUDINARY_CLOUD_NAME    = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_UPLOAD_PRESET = os.getenv("CLOUDINARY_UPLOAD_PRESET")
MAX_CONSECUTIVE_INVALID  = 10

# ── Translator ───────────────────────────────────────────────────────────────
t = Translator()
def translate(text: str) -> str:
    if not text: return ""
    try:
        return t.translate(text, dest="en").text
    except Exception:
        return text

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")

# ── Env‐var check ────────────────────────────────────────────────────────────
for v in ("WEBFLOW_API_TOKEN","WEBFLOW_COLLECTION_ID","CLOUDINARY_CLOUD_NAME","CLOUDINARY_UPLOAD_PRESET"):
    if not os.getenv(v):
        logging.error(f"Missing env-var: {v}")
        exit(1)

# ── Cloudinary upload ────────────────────────────────────────────────────────
def upload_image_to_cloudinary(local_path, page_id):
    logging.info(f"Uploading image {os.path.basename(local_path)} → Cloudinary/{page_id}")
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    for attempt in range(1,4):
        try:
            with open(local_path,"rb") as f:
                resp = requests.post(
                    url,
                    files={"file":f},
                    data={"upload_preset":CLOUDINARY_UPLOAD_PRESET,"folder":str(page_id)},
                )
            if resp.status_code == 200:
                secure_url = resp.json().get("secure_url")
                logging.info(f"✔ Cloudinary: {secure_url}")
                return secure_url
            logging.warning(f"Cloudinary failed (#{attempt}): {resp.status_code}")
        except Exception as e:
            logging.warning(f"Cloudinary error #{attempt}: {e}")
    logging.error(f"✘ Cloudinary upload gave up: {local_path}")
    return None

# ── Webflow upload (v2) ─────────────────────────────────────────────────────
def upload_to_webflow(data):
    """
    Uses v2 endpoint: POST /v2/collections/{COLL_ID}/items
    Payload: { "items":[ { "fields": { … } } ] }
    """
    logging.info("Uploading to Webflow v2…")
    url = f"https://api.webflow.com/v2/collections/{WEBFLOW_COLLECTION_ID}/items"
    headers = {
        "Authorization":  f"Bearer {WEBFLOW_API_TOKEN}",
        "Content-Type":   "application/json; charset=utf-8",
        "Accept-Version": "1.0.0",
    }

    payload = {"items":[{"fields": data["fields"]}]}
    logging.info("⟳ Payload → %s", json.dumps(payload, ensure_ascii=False))

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code in (200,201):
        logging.info("✔ Webflow v2 success.")
        return True

    logging.error("✘ Webflow v2 error %s: %s", resp.status_code, resp.text)
    return False

# ── Scrape a single page ────────────────────────────────────────────────────
def scrape_page(page_id, pw):
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Scraping {page_id}: {url}")
    browser = pw.chromium.launch(headless=True)
    page    = browser.new_context().new_page()
    try:
        page.goto(url)
        if page.url.rstrip("/") == HOMEPAGE_URL:
            logging.info("→ Redirected to homepage; skipping.")
            return False

        # 1) Title & description
        raw_title = page.query_selector("h1").inner_text().strip() \
                    if page.query_selector("h1") else ""
        title     = translate(raw_title) or f"Property {page_id}"
        raw_desc  = page.query_selector(".description").inner_text().strip() \
                    if page.query_selector(".description") else ""
        desc      = translate(raw_desc)

        # 2) Scrape property & room tables (if you need them, otherwise skip)
        prop, room = {}, {}
        for tbl in page.query_selector_all("table"):
            hdrs = [th.inner_text().strip() for th in tbl.query_selector_all("tr:nth-of-type(1) th")]
            if "種別" in hdrs:
                vals  = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(2) td")]
                parts = vals[2].splitlines() if len(vals)>2 else [""]
                prop.update({
                    "layout":          translate(vals[0] if len(vals)>0 else ""),
                    "elevator":        translate(vals[1] if len(vals)>1 else ""),
                    "completion_date": translate(vals[2] if len(vals)>2 else ""),
                    "units":           vals[3].split() if len(vals)>3 else [],
                })
            if "家賃" in hdrs:
                r1 = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(2) td")]
                if len(r1)>=4:
                    room.update(dict(zip(
                        ["rent","area","deposit","key_money"],
                        [translate(v) for v in r1]
                    )))

        # 3) Map link
        map_el    = page.query_selector("a:has-text('大きな地図で見る')")
        map_link  = map_el.get_attribute("href") if map_el else ""

        # 4) Images
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        folder    = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(folder, exist_ok=True)
        images    = []
        for img in page.query_selector_all("img"):
            src = img.get_attribute("src") or ""
            fn  = src.split("/")[-1]
            if not fn or not fn[0].isdigit(): continue
            lp = os.path.join(folder, f"MAIDO_{datetime.now():%Y%m%d}_{len(images)+1}.jpg")
            with open(lp,"wb") as f:
                f.write(requests.get(src).content)
            cu = upload_image_to_cloudinary(lp, page_id)
            if cu:
                images.append({"url":cu})

        # 5) Build final fields — include *only* the slugs your CMS expects:
        ts = int(time.time())
        fields = {
            # required
            "name":        title,
            "slug":        f"property-{page_id}-{ts}",
            "district":    "6672b625a00e8f837e7b4e68",
            "category":    "665b099bc0ffada56b489baf",
            # optional extras
            "description": f"<p>{desc}</p>",
            "multi-image": images,
            "map_link":    map_link,
        }

        # 6) Upload & return
        if not upload_to_webflow({"fields": fields}):
            logging.error(f"Failed to upload page {page_id}")
            return False

        logging.info(f"Page {page_id} done.")
        return True

    except Exception as e:
        logging.error(f"Scrape error {page_id}: {e}")
        return False

    finally:
        browser.close()

# ── Main Loop ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        current = int(open("last_page.txt").read().strip())+1
    except:
        current = START_PAGE

    bad = 0
    with sync_playwright() as pw:
        while bad < MAX_CONSECUTIVE_INVALID:
            if scrape_page(current, pw):
                bad = 0
            else:
                bad += 1
            open("last_page.txt","w").write(str(current))
            current += 1
