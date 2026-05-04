"""
create_notion_db.py — Script satu kali untuk buat database baru
di bawah Notion page MENUJU_1T, lalu update .env dengan DB ID baru.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
PARENT_PAGE_ID = "354945edf4a98001948ed7bc9f21684f"  # MENUJU_1T page

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2025-09-03"
}

payload = {
    "parent": {
        "type": "page_id",
        "page_id": PARENT_PAGE_ID
    },
    "title": [
        {
            "type": "text",
            "text": {
                "content": "📅 Task Scheduler"
            }
        }
    ],
    "properties": {
        "Name": {
            "title": {}
        },
        "Date": {
            "date": {}
        },
        "Time": {
            "rich_text": {}
        },
        "Status": {
            "checkbox": {}
        },
        "Notes / Summary": {
            "rich_text": {}
        }
    }
}

print("[*] Membuat database baru di Notion...")
resp = requests.post(
    "https://api.notion.com/v1/databases",
    headers=headers,
    json=payload
)

data = resp.json()

if resp.status_code == 200:
    db_id = data["id"].replace("-", "")
    db_id_formatted = data["id"]
    db_url = data.get("url", "")
    print("[OK] Database berhasil dibuat!")
    print(f"   ID     : {db_id_formatted}")
    print(f"   URL    : {db_url}")
    print()

    # Update .env
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    env_path = os.path.abspath(env_path)

    with open(env_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    found = False
    for line in lines:
        if line.startswith("NOTION_DB_ID="):
            new_lines.append(f"NOTION_DB_ID={db_id}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"NOTION_DB_ID={db_id}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    print(f"[OK] .env diupdate: NOTION_DB_ID={db_id}")
    print(f"   (raw ID: {db_id_formatted})")
else:
    print("[ERROR] Gagal membuat database!")
    print(f"   Status: {resp.status_code}")
    print(f"   Error : {json.dumps(data, indent=2)}")
