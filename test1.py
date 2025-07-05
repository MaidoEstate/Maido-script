import os, requests, json

# 1) load your secrets
TOKEN = os.getenv("WEBFLOW_API_TOKEN")
COLL  = os.getenv("WEBFLOW_COLLECTION_ID")

# 2) hit the v1 fields endpoint
url = f"https://api.webflow.com/v1/collections/{COLL}/fields"
headers = {
    "Authorization":  f"Bearer {TOKEN}",
    "Accept-Version": "1.0.0",
}

resp = requests.get(url, headers=headers)
print("Status:", resp.status_code)
print("Body:", resp.text)

# 3) if it’s 200, pretty-print the slugs + whether they’re required
if resp.status_code == 200:
    fields = resp.json().get("fields", [])
    print("\nslug".ljust(20), "name".ljust(30), "required")
    print("-"*60)
    for f in fields:
        print(f"{f['slug']:<20} {f['name']:<30} {f['required']}")
