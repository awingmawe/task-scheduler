import os
from dotenv import load_dotenv
import requests
import google.generativeai as genai
from notion_client import Client

load_dotenv()

def verify_telegram():
    print("Testing Telegram...")
    token = os.getenv("TELEGRAM_TOKEN")
    url = f"https://api.telegram.org/bot{token}/getMe"
    resp = requests.get(url)
    if resp.status_code == 200:
        print(f"✅ Telegram OK: {resp.json()['result']['username']}")
    else:
        print("❌ Telegram Error:", resp.text)

def verify_gemini():
    print("Testing Gemini...")
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content("Reply with just the word 'OK'")
        print(f"✅ Gemini OK: {response.text.strip()}")
    except Exception as e:
        print("❌ Gemini Error:", str(e))

def verify_notion():
    print("Testing Notion...")
    notion = Client(auth=os.getenv("NOTION_TOKEN"))
    try:
        db = notion.databases.retrieve(database_id=os.getenv("NOTION_DB_ID"))
        print(f"✅ Notion OK: Connected to DB '{db['title'][0]['plain_text'] if db['title'] else 'Untitled'}'")
    except Exception as e:
        print("❌ Notion Error:", str(e))

if __name__ == "__main__":
    print("--- STARTING HANDSHAKE ---")
    verify_telegram()
    verify_gemini()
    verify_notion()
    print("--- HANDSHAKE COMPLETE ---")
