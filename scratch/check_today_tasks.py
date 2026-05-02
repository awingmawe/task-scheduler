import os
import requests
import json
import datetime
from dotenv import load_dotenv

load_dotenv()

def _today_wib():
    # Helper to get current date in WIB (UTC+7)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_wib = now_utc + datetime.timedelta(hours=7)
    return now_wib.strftime("%Y-%m-%d")

def check_today_tasks():
    db_id = os.environ.get("NOTION_DB_ID")
    token = os.environ.get("NOTION_TOKEN")
    today = _today_wib()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"equals": today}},
                {"property": "Name", "title": {"does_not_contain": "[CONFIG]"}}
            ]
        }
    }
    
    resp = requests.post(url, headers=headers, json=payload).json()
    results = resp.get("results", [])
    
    print(f"Tasks for {today}:")
    for page in results:
        name = page["properties"]["Name"]["title"][0]["text"]["content"]
        print(f"- {name}")

if __name__ == "__main__":
    check_today_tasks()
