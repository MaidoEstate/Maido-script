import os, time, json, requests

# ——— CONFIG ———————————————————————————————————————————————————————
TOKEN = os.getenv("WEBFLOW_API_TOKEN")           # set this in your shell or Actions secret
COLL  = os.getenv("WEBFLOW_COLLECTION_ID")       # same here
# Replace with your actual District/Category reference IDs
DIST  = "6672b625a00e8f837e7b4e68"  
CATS  = "665b099bc0ffada56b489baf"

# ——— BUILD A MINIMAL PAYLOAD ———————————————————————————————————————
timestamp = int(time.time())
payload = {
  "fields": {
    "name":     f"Test item {timestamp}",
    "slug":     f"test-{timestamp}",
    "district": DIST,
    "category": CATS
  }
}

# ——— SEND THE REQUEST —————————————————————————————————————————————
url = f"https://api.webflow.com/collections/{COLL}/items"
headers = {
    "Authorization":  f"Bearer {TOKEN}",
    "Accept-Version": "1.0.0",
    "Content-Type":   "application/json; charset=utf-8",
}

print("POST", url)
print("Payload:", json.dumps(payload, ensure_ascii=False, indent=2))
resp = requests.post(url, headers=headers, json=payload)
print("Status:", resp.status_code)
print("Response:", resp.text)
