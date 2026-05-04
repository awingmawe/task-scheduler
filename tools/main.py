import os
import modal
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from config import _is_duplicate
from ai_agent import process_with_ai
from telegram_tools import send_telegram_message
from cron_jobs import (
    execute_morning_slap,
    execute_noon_slap,
    execute_afternoon_slap,
    execute_evening_slap,
    execute_weekly_report_slap
)

# Modal Image with dependencies and local tools
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "google-genai",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "requests",
    "python-dotenv"
).add_local_dir(os.path.dirname(os.path.abspath(__file__)), remote_path="/root")

app = modal.App("notion-telegram-scheduler")
web_app = FastAPI()

# ---------------------------------------------------------
# LAYER 1: ARCHITECTURE (TRIGGERS & ENDPOINTS)
# ---------------------------------------------------------

def _process_and_reply_sync(chat_id: int, user_text: str, audio_data: dict | None):
    """Sync background task: proses AI dan kirim balik ke Telegram."""
    try:
        ai_reply = process_with_ai(user_text, audio_data)
        send_telegram_message(ai_reply, chat_id)
    except Exception as e:
        print(f"Background processing error: {e}")
        send_telegram_message("Ada masalah internal, coba lagi ya!", chat_id)

@web_app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print("INCOMING WEBHOOK DATA:", data)

    update_id = data.get("update_id")
    if update_id and await _is_duplicate(int(update_id)):
        print(f"[DEDUP] Duplicate update_id {update_id} blocked.")
        return {"status": "ok"}

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        user_text = ""
        audio_data = None

        if "text" in message:
            user_text = message["text"]
        elif "voice" in message:
            token = os.environ["TELEGRAM_TOKEN"]
            file_id = message["voice"]["file_id"]
            file_resp = requests.get(
                f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
            ).json()
            if file_resp.get("ok"):
                file_path = file_resp["result"]["file_path"]
                audio_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                audio_bytes = requests.get(audio_url).content
                audio_data = {"mime_type": "audio/ogg", "data": audio_bytes}
                user_text = "Tolong dengarkan pesan suara ini dan jalankan instruksinya."
            else:
                send_telegram_message("Gagal mendownload Voice Note.", chat_id)
                return {"status": "ok"}

        if user_text or audio_data:
            background_tasks.add_task(_process_and_reply_sync, chat_id, user_text, audio_data)

    return {"status": "ok"}

@app.function(image=image, secrets=[modal.Secret.from_name("my-notion-secrets")])
@modal.asgi_app()
def fastapi_app():
    return web_app

# ---------------------------------------------------------
# CRON JOBS (Triggered by Modal)
# ---------------------------------------------------------

@app.function(image=image, schedule=modal.Cron("0 22 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def morning_slap():
    """Triggered at 05:00 WIB (22:00 UTC previous day)."""
    execute_morning_slap()

@app.function(image=image, schedule=modal.Cron("0 5 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def noon_slap():
    """Triggered at 12:00 WIB (05:00 UTC)."""
    execute_noon_slap()

@app.function(image=image, schedule=modal.Cron("0 8 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def afternoon_slap():
    """Triggered at 15:00 WIB (08:00 UTC)."""
    execute_afternoon_slap()

@app.function(image=image, schedule=modal.Cron("0 11 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def evening_slap():
    """Triggered at 18:00 WIB (11:00 UTC)."""
    execute_evening_slap()

@app.function(image=image, schedule=modal.Cron("0 11 * * 0"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def weekly_report_slap():
    """Triggered every Sunday at 18:00 WIB (11:00 UTC)."""
    execute_weekly_report_slap()
