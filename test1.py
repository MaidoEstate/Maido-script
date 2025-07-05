import os, requests, json

# 1) Load your secrets
TOKEN = os.getenv("WEBFLOW_API_TOKEN")
COLL  = os.getenv("WEBFLOW_COLLECTION_ID")

# 2) Build the “list fields” URL and headers
url = f"https://api.webflow.com/collections/{COLL}/fields"
headers = {
    "Authorization":  f"Bearer {TOKEN}",
    "Accept-Version": "1.0.0",
}

# 3) Fire the request
resp = requests.get(url, headers=headers)
print("Status:", resp.status_code)
print("Body:", resp.text)

# 4) If it’s a 200, pretty-print the fields
if resp.status_code == 200:
    data = resp.json().get("fields", [])
    print("\nSlug".ljust(20), "Name".ljust(30), "Required")
    print("-"*60)
    for f in data:
        print(f"{f['slug']:<20} {f['name']:<30} {f['required']}")
