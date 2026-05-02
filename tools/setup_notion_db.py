import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

def setup_notion_db():
    notion = Client(auth=os.getenv("NOTION_TOKEN"))
    db_id = os.getenv("NOTION_DB_ID")
    
    print("Updating Notion Database Schema...")
    try:
        # We define the required properties
        properties = {
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Time": {"rich_text": {}},
            "Status": {"checkbox": {}},
            "Notes / Summary": {"rich_text": {}},
            "🔥 Streak": {"number": {}},
            "🤖 Refleksi AI": {"rich_text": {}}
        }
        
        response = notion.databases.update(
            database_id=db_id,
            properties=properties
        )
        print("✅ Notion Database Schema updated successfully!")
    except Exception as e:
        print("❌ Error updating Notion Database:", str(e))

if __name__ == "__main__":
    setup_notion_db()
