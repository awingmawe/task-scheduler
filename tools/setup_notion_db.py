import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def setup_notion_db():
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DB_ID")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2025-09-03"
    }
    
    print("Updating Notion Database Schema...")
    try:
        url = f"https://api.notion.com/v1/databases/{db_id}"
        properties = {
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Time": {"rich_text": {}},
            "Status": {"checkbox": {}},
            "Notes / Summary": {"rich_text": {}},
            "🔥 Streak": {"number": {}},
            "🤖 Refleksi AI": {"rich_text": {}}
        }
        
        resp = requests.patch(url, headers=headers, json={"properties": properties})
        resp.raise_for_status()
        print("✅ Notion Database Schema updated successfully!")
    except Exception as e:
        print(f"❌ Error updating Notion Database: {e}")
        if 'resp' in locals():
            print(f"Response: {resp.text}")

if __name__ == "__main__":
    setup_notion_db()
