"""
Script test Google Calendar credentials dan list kalender yang tersedia.
Jalankan: python tools/test_gcal.py
"""
import os
import sys
from dotenv import load_dotenv

# Load .env kalau ada
load_dotenv()

# Set credentials manual dari .env (atau hardcode sementara untuk test)
GCAL_CLIENT_ID     = os.environ.get("GCAL_CLIENT_ID", "")
GCAL_CLIENT_SECRET = os.environ.get("GCAL_CLIENT_SECRET", "")
GCAL_REFRESH_TOKEN = os.environ.get("GCAL_REFRESH_TOKEN", "")

if not all([GCAL_CLIENT_ID, GCAL_CLIENT_SECRET, GCAL_REFRESH_TOKEN]):
    print("ERROR: Set environment variables GCAL_CLIENT_ID, GCAL_CLIENT_SECRET, GCAL_REFRESH_TOKEN")
    print("Atau jalankan: python tools/setup_gcal_auth.py untuk generate dulu.")
    sys.exit(1)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build
except ImportError:
    print("ERROR: Library belum diinstall. Jalankan:")
    print("  python -m pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)

def main():
    print("="*60)
    print("TEST GOOGLE CALENDAR CREDENTIALS")
    print("="*60)

    print("\n[1] Membangun credentials dari refresh_token...")
    creds = Credentials(
        token=None,
        refresh_token=GCAL_REFRESH_TOKEN,
        client_id=GCAL_CLIENT_ID,
        client_secret=GCAL_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar"]
    )

    print("[2] Refreshing token...")
    try:
        creds.refresh(GoogleRequest())
        print(f"   OK! Access token valid: {creds.token[:30]}...")
    except Exception as e:
        print(f"   FAILED! Error: {e}")
        print("\n[!] Kemungkinan refresh_token expired atau invalid.")
        print("    Coba jalankan ulang: python tools/setup_gcal_auth.py")
        return

    print("\n[3] Membangun Google Calendar service...")
    service = build("calendar", "v3", credentials=creds)
    print("   OK!")

    print("\n[4] Listing semua kalender di akun ini...")
    calendar_list = service.calendarList().list().execute()
    calendars = calendar_list.get("items", [])
    
    if not calendars:
        print("   Tidak ada kalender ditemukan!")
        return
    
    print(f"\n   Ditemukan {len(calendars)} kalender:\n")
    for cal in calendars:
        primary = " <-- PRIMARY (ini yang dipakai bot)" if cal.get("primary") else ""
        print(f"   - {cal['summary']}")
        print(f"     ID    : {cal['id']}")
        print(f"     Akses : {cal.get('accessRole', '?')}{primary}")
        print()

    print("\n[5] Test membuat event...")
    import datetime
    now = datetime.datetime.now()
    test_event = {
        "summary": "[TEST] Cek dari bot - HAPUS",
        "start": {"dateTime": now.isoformat(), "timeZone": "Asia/Jakarta"},
        "end":   {"dateTime": (now + datetime.timedelta(minutes=30)).isoformat(), "timeZone": "Asia/Jakarta"},
    }
    created = service.events().insert(calendarId="primary", body=test_event).execute()
    print(f"   OK! Event ID  : {created['id']}")
    print(f"   Link          : {created.get('htmlLink', '?')}")
    print("\n   Cek Google Calendar kamu sekarang!")
    print("   Kalau event '[TEST] Cek dari bot' muncul, berarti credentials BENAR.")
    print("   Kalau tidak muncul, periksa akun Google yang kamu buka di browser.")
    print("="*60)

if __name__ == "__main__":
    main()
