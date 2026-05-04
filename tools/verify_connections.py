import os
from dotenv import load_dotenv
import requests
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build

load_dotenv()

def verify_telegram():
    print("Testing Telegram...")
    token = os.getenv("TELEGRAM_TOKEN")
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            print(f"✅ Telegram OK: {resp.json()['result']['username']}")
        else:
            print("❌ Telegram Error:", resp.text)
    except Exception as e:
        print("❌ Telegram Exception:", str(e))

def verify_gemini():
    print("Testing Gemini...")
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        # Use a more common model name for verification
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content("Reply with just the word 'OK'")
        print(f"✅ Gemini OK: {response.text.strip()}")
    except Exception as e:
        print("❌ Gemini Error:", str(e))

def verify_notion():
    print("Testing Notion...")
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DB_ID")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    try:
        url = f"https://api.notion.com/v1/databases/{db_id}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            title = data['title'][0]['plain_text'] if data.get('title') else 'Untitled'
            print(f"✅ Notion OK: Connected to DB '{title}'")
        else:
            print("❌ Notion Error:", resp.text)
    except Exception as e:
        print("❌ Notion Exception:", str(e))

def verify_gcal():
    print("Testing Google Calendar...")
    try:
        refresh_token = os.getenv("GCAL_REFRESH_TOKEN")
        client_id = os.getenv("GCAL_CLIENT_ID")
        client_secret = os.getenv("GCAL_CLIENT_SECRET")
        
        if not all([refresh_token, client_id, client_secret]):
            print("❌ GCal Error: GCAL_REFRESH_TOKEN, GCAL_CLIENT_ID, or GCAL_CLIENT_SECRET missing in .env")
            return

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        creds.refresh(GoogleRequest())
        service = build("calendar", "v3", credentials=creds)
        calendar_list = service.calendarList().list().execute()
        print(f"✅ GCal OK: Found {len(calendar_list.get('items', []))} calendars")
    except Exception as e:
        print("❌ GCal Error:", str(e))

if __name__ == "__main__":
    print("--- STARTING HANDSHAKE ---")
    verify_telegram()
    verify_gemini()
    verify_notion()
    verify_gcal()
    print("--- HANDSHAKE COMPLETE ---")
