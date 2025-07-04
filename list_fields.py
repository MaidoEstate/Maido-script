import os, requests, json

TOKEN = os.environ["WEBFLOW_API_TOKEN"]
COLL  = os.environ["WEBFLOW_COLLECTION_ID"]
URL   = f"https://api.webflow.com/v1/collections/{COLL}/fields"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept-Version": "1.0.0",
}

resp = requests.get(URL, headers=headers)
resp.raise_for_status()
fields = resp.json().get("fields", [])

print("slug           | name                         | required")
print("-"*60)
for f in fields:
    print(f"{f['slug']:<15} | {f['name']:<28} | {f['required']}")
