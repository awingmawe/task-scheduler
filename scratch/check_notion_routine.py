import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def check_routine():
    db_id = os.environ.get("NOTION_DB_ID")
    token = os.environ.get("NOTION_TOKEN")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {
        "filter": {
            "property": "Name",
            "title": {"equals": "[CONFIG] MASTER ROUTINE"}
        }
    }
    
    resp = requests.post(url, headers=headers, json=payload).json()
    results = resp.get("results", [])
    
    if results:
        props = results[0]["properties"]
        rich_text = props.get("Notes / Summary", {}).get("rich_text", [])
        if rich_text:
            content = rich_text[0]["text"]["content"]
            print("Master Routine Content:")
            print(json.dumps(json.loads(content), indent=2))
        else:
            print("Notes / Summary is empty")
    else:
        print("[CONFIG] MASTER ROUTINE page not found")

if __name__ == "__main__":
    check_routine()
