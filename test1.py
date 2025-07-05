import os, requests, json

TOKEN = os.getenv("WEBFLOW_API_TOKEN")
COLL  = os.getenv("WEBFLOW_COLLECTION_ID")

url = f"https://api.webflow.com/collections/{COLL}/fields"
headers = {
    "Authorization":  f"Bearer {TOKEN}",
    "Accept-Version": "1.0.0",
}

resp = requests.get(url, headers=headers)
print("Status:", resp.status_code)
print("Body:", resp.text)

if resp.status_code == 200:
    fields = resp.json().get("fields", [])
    print("\nSlug".ljust(20), "Name".ljust(30), "Required")
    print("-"*60)
    for f in fields:
        print(f"{f['slug']:<20} {f['name']:<30} {f['required']}")
