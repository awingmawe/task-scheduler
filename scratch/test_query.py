import os
import requests
import datetime
from dotenv import load_dotenv

load_dotenv()

def test_notion_query():
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DB_ID")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {
        "filter": {
            "property": "Date",
            "date": {"equals": date_str}
        }
    }
    
    print(f"Testing query for date: {date_str}")
    resp = requests.post(url, headers=headers, json=payload)
    print(f"Status Code: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error Body: {resp.text}")
    else:
        print(f"Success! Found {len(resp.json().get('results', []))} results.")

if __name__ == "__main__":
    test_notion_query()
