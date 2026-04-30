"""
Script otorisasi Google Calendar — jalankan SEKALI secara lokal.

Cara pakai:
1. Taruh file credentials.json di folder tools/ (download dari Google Cloud Console)
2. Jalankan: python tools/setup_gcal_auth.py
3. Login di browser yang terbuka
4. Copy output refresh_token → simpan ke Modal secrets sebagai GCAL_REFRESH_TOKEN

Dependensi (install lokal dulu):
    pip install google-auth-oauthlib google-auth google-api-python-client
"""

import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Scope minimal: hanya bisa buat/edit events di calendar
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

CREDENTIALS_FILE = os.path.join(
    os.path.dirname(__file__),
    "client_secret_303099869444-icmsfojc927qse3vgpgcjh4qg5154eu5.apps.googleusercontent.com.json"
)

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print("❌ ERROR: File credentials.json tidak ditemukan di folder tools/")
        print("   Download dari: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs")
        return

    print(">> Membuka browser untuk otorisasi Google Calendar...")
    print("   Login dengan akun Google yang mau kamu pakai untuk bot ini.\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    # Parse credentials untuk extract nilai yang dibutuhkan
    with open(CREDENTIALS_FILE) as f:
        client_info = json.load(f)

    client_id = client_info["installed"]["client_id"]
    client_secret = client_info["installed"]["client_secret"]
    refresh_token = creds.refresh_token

    print("\n" + "="*60)
    print("[OK] OTORISASI BERHASIL! Simpan nilai berikut ke Modal secrets:")
    print("="*60)
    print(f"\nGCAL_CLIENT_ID     = {client_id}")
    print(f"\nGCAL_CLIENT_SECRET = {client_secret}")
    print(f"\nGCAL_REFRESH_TOKEN = {refresh_token}")
    print(f"\nGCAL_CALENDAR_ID   = primary")
    print("\n" + "="*60)
    print("[INFO] JANGAN commit refresh_token ke Git!")

if __name__ == "__main__":
    main()
