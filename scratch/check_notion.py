import os
import datetime
import json
import requests

WIB = datetime.timezone(datetime.timedelta(hours=7))

def _notion_headers():
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

def _today_wib():
    return datetime.datetime.now(WIB).strftime("%Y-%m-%d")

def check_notion():
    db_id = os.environ["NOTION_DB_ID"]
    today = _today_wib()
    print(f"Checking for date: {today}")
    
    # Check Master Routine
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {"filter": {"property": "Name", "title": {"equals": "[CONFIG] MASTER ROUTINE"}}}
    resp = requests.post(url, headers=_notion_headers(), json=payload).json()
    if resp.get("results"):
        routine_json = resp["results"][0]["properties"]["Notes / Summary"]["rich_text"][0]["text"]["content"]
        routine = json.loads(routine_json)
        print("MASTER ROUTINE CONFIG:")
        for t in routine:
            print(f"  - {t['name']} ({t.get('duration', 'N/A')})")
    else:
        print("MASTER ROUTINE NOT FOUND")

    # Check Today's Tasks
    payload = {"filter": {"property": "Date", "date": {"equals": today}}}
    resp = requests.post(url, headers=_notion_headers(), json=payload).json()
    print(f"\nTASKS FOR {today}:")
    for r in resp.get("results", []):
        name = r["properties"]["Name"]["title"][0]["text"]["content"]
        print(f"  - {name}")

if __name__ == "__main__":
    check_notion()
