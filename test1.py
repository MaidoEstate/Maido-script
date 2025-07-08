import os, json, time, logging, requests
from datetime import datetime
from playwright.sync_api import sync_playwright
from googletrans import Translator

# ── Config ───────────────────────────
START_PAGE = int(os.getenv("START_PAGE", 12453))
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
HOMEPAGE_URL = "https://www.designers-osaka-chintai.info"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
WEBFLOW_API_TOKEN = os.getenv("WEBFLOW_API_TOKEN")
WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_UPLOAD_PRESET = os.getenv("CLOUDINARY_UPLOAD_PRESET")
MAX_CONSECUTIVE_INVALID = 10

CATEGORY_ID = "665b099bc0ffada56b489baf"  # Rent a Home
AGENT_NAME = "Alan"

DISTRICT_MAP = {
    "Abeno-ku":         "686cb5e4bb8a11a7adbdc77f",
    "Asahi-ku":         "686cb6556136ad1eee337af3",
    "Chuo-ku":          "6673aded99fc584815a8c785",  # default
    "Fukushima-ku":     "686cb66c622705ab1dc0e1fd",
    "Higashi Yodogawa-ku": "6674dab2dadf97990df2165e",
    "Higashinari-ku":   "686cb67c0e7ac6d9e8be0eae",
    "Higashisumiyoshi-ku":"686cb68bd189427bc8abc385",
    "Higashiyodogawa-ku":"686cb6962f1728bde14385ff",
    "Hirano-ku":        "686cb6a1586de2a8427b4295",
    "Ikuno-ku":         "686cb6ac04605a0c64e5171a",
    "Joto-ku":          "686cb6ddaaf6c72eb2c5af83",
    "Kita-ku":          "686cb58ebf82de1e638878b5",
    "Konohana-ku":      "686cb6f6064bb19e41fa2bc5",
    "Minato-ku":        "686cb70401d054bb433b16b0",
    "Miyakojima-ku":    "686cb70f382b5b2f1db7632e",
    "Naniwa-ku":        "6672b625a00e8f837e7b4e68",
    "Nishi-ku":         "6674e7ac8a17bd3ba8a796ff",
    "Nishinari-ku":     "686cb73626e6df8dace19637",
    "Nishiyodogawa-ku": "686cb7772eb3d5f63b1f0f1c",
    "Suminoe-ku":       "686cb7874e68bde70087c9aa",
    "Sumiyoshi-ku":     "686cb79ca5f44d7d38c344d1",
    "Taisho-ku":        "686cb7ae7a8f0c99ced350ae",
    "Tennoji-ku":       "686cb7f19671962810e590fa",
    "Tsurumi-ku":       "686cb801f928cc2fa20ab9cf",
}
DEFAULT_DISTRICT_ID = DISTRICT_MAP["Chuo-ku"]

translator = Translator()
def translate(text: str) -> str:
    if not text: return ""
    try: return translator.translate(text, dest="en").text
    except Exception: return text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
for v in ("WEBFLOW_API_TOKEN","WEBFLOW_COLLECTION_ID","CLOUDINARY_CLOUD_NAME","CLOUDINARY_UPLOAD_PRESET"):
    if not os.getenv(v): logging.error(f"Missing env-var: {v}"); exit(1)

def upload_image_to_cloudinary(path, page_id):
    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload"
    for attempt in range(1,4):
        try:
            with open(path,"rb") as fd:
                resp = requests.post(
                    url,
                    files={"file": fd},
                    data={"upload_preset": CLOUDINARY_UPLOAD_PRESET,"folder":str(page_id)}
                )
            if resp.status_code == 200:
                return resp.json()["secure_url"]
        except Exception: pass
    logging.error("Cloudinary failed for %s", path)
    return None

def upload_to_webflow(fields: dict) -> bool:
    url = f"https://api.webflow.com/collections/{WEBFLOW_COLLECTION_ID}/items"
    headers = {
        "Authorization":  f"Bearer {WEBFLOW_API_TOKEN}",
        "Accept-Version": "1.0.0",
        "Content-Type":   "application/json",
    }
    payload = {"items": [fields]}  # <--- FIX HERE!
    logging.info("Webflow payload:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code in (200,201): return True
    logging.error("Webflow error %s: %s", r.status_code, r.text)
    return False

def infer_district(location: str) -> str:
    low = location.lower()
    for ward, did in DISTRICT_MAP.items():
        if ward.lower() in low: return did
    return DEFAULT_DISTRICT_ID

def parse_transport(transport_raw: str):
    first_line = transport_raw.split("\n")[0]
    parts = first_line.split("/")
    after_slash = parts[1].strip() if len(parts)>=2 else first_line
    toks = after_slash.rsplit(" ", 2)
    if len(toks)==3: return toks[0], " ".join(toks[1:])
    return after_slash, ""

def scrape_page(page_id, pw) -> bool:
    url = f"{BASE_URL}{page_id}"
    logging.info("Scraping %s …", url)
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    try:
        page.goto(url)
        if page.url.rstrip("/") == HOMEPAGE_URL:
            logging.info("Redirected → homepage; skipping.")
            return False
        raw_title = page.query_selector("h1").inner_text().strip() if page.query_selector("h1") else ""
        title = translate(raw_title) or f"Property {page_id}"
        raw_desc = page.query_selector(".description").inner_text().strip() if page.query_selector(".description") else ""
        desc = translate(raw_desc)
        prop_info, room_info = {}, {}
        for tbl in page.query_selector_all("table"):
            headers = [th.inner_text().strip() for th in tbl.query_selector_all("tr:nth-of-type(1) th")]
            if "種別" in headers:
                vals = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(2) td")]
                prop_info["location"] = translate(vals[1]) if len(vals)>1 else ""
                trn_td = tbl.query_selector("tr:has-text('交通') td")
                transport_raw = trn_td.inner_text().strip() if trn_td else ""
                prop_info["nearest_station"], prop_info["walk_to_station"] = parse_transport(translate(transport_raw))
            if "家賃" in headers:
                r1 = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(2) td")]
                if len(r1)>=4:
                    room_info["price"] = translate(r1[0])
                    room_info["sqf"] = translate(r1[1])
                    room_info["deposit"] = translate(r1[2])
                    room_info["key_money"] = translate(r1[3])
                r2 = [td.inner_text().strip() for td in tbl.query_selector_all("tr:nth-of-type(4) td")]
                if len(r2)>=2:
                    room_info["management_fee"] = translate(r2[1])
        map_el = page.query_selector("a:has-text('大きな地図で見る')")
        map_link = map_el.get_attribute("href") if map_el else ""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        img_dir = os.path.join(OUTPUT_DIR, str(page_id))
        os.makedirs(img_dir, exist_ok=True)
        image_urls = []
        for img in page.query_selector_all("img"):
            src = img.get_attribute("src") or ""
            fname = src.split("/")[-1]
            if not fname or not fname[0].isdigit(): continue
            local_path = os.path.join(img_dir, f"MAIDO_{datetime.now():%Y%m%d}_{len(image_urls)+1}.jpg")
            with open(local_path,"wb") as f:
                f.write(requests.get(src).content)
            cu = upload_image_to_cloudinary(local_path, page_id)
            if cu: image_urls.append(cu)
        ts = int(time.time())
        fields = {
            "name": title,
            "slug": f"property-{page_id}-{ts}",
            "location": prop_info.get("location", ""),
            "link_location": map_link,
            "district": infer_district(prop_info.get("location","")),
            "property_title": title,
            "nearest_station": prop_info.get("nearest_station",""),
            "walk_to_station": prop_info.get("walk_to_station",""),
            "sqf": room_info.get("sqf",""),
            "type": "",
            "key_money": room_info.get("key_money",""),
            "price": room_info.get("price",""),
            "management_fee": room_info.get("management_fee",""),
            "short_description": desc.split(".")[0] + "." if "." in desc else desc,
            "description": desc,
            "category": CATEGORY_ID,
            "agent": AGENT_NAME,
            "multi-image": image_urls[:25],
        }
        success = upload_to_webflow(fields)
        if not success: logging.error("Failed to upload page %s", page_id)
        return success
    except Exception as e:
        logging.error("Error scraping %s: %s", page_id, e)
        return False
    finally:
        browser.close()

if __name__ == "__main__":
    try: current = int(open("last_page.txt").read()) + 1
    except Exception: current = START_PAGE
    bad = 0
    with sync_playwright() as pw:
        while bad < MAX_CONSECUTIVE_INVALID:
            if scrape_page(current, pw): bad = 0
            else: bad += 1
            with open("last_page.txt","w") as f: f.write(str(current))
            current += 1
