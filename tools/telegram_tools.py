import os
import requests

def send_telegram_message(text: str, chat_id: int = None):
    token = os.environ["TELEGRAM_TOKEN"]
    if not chat_id:
        # Fallback to env var or the hardcoded bot ID
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", 8344404871)
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    resp = requests.post(url, json=payload)
    print(f"TELEGRAM RESP to {chat_id}: {resp.text}")
