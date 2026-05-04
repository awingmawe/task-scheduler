import os
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def _build_gcal_service():
    """Build Google Calendar API service dari Modal secrets.
    Token di-refresh secara eksplisit karena Modal serverless tidak persist token cache.
    """
    from google.auth.transport.requests import Request as GoogleRequest
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GCAL_REFRESH_TOKEN"],
        client_id=os.environ["GCAL_CLIENT_ID"],
        client_secret=os.environ["GCAL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    # Wajib: force refresh token sebelum dipakai
    creds.refresh(GoogleRequest())
    return build("calendar", "v3", credentials=creds)

def create_google_calendar_event(
    title: str,
    date_str: str,
    start_time: str,
    end_time: str = "",
    duration_minutes: int = 60,
    description: str = ""
) -> str:
    """Buat event di Google Calendar.
    Gunakan ini saat user menyebut nama kegiatan DAN jam spesifik.
    """
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        service = _build_gcal_service()
        calendar_id = os.environ.get("GCAL_CALENDAR_ID", "primary")
        tz = "Asia/Jakarta"

        start_dt = datetime.datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")

        if end_time:
            end_dt = datetime.datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
            if end_dt <= start_dt:
                end_dt += datetime.timedelta(days=1)
        else:
            end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": tz},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 15}]
            }
        }

        print(f"[GCAL DEBUG] Creating event in calendar: {calendar_id}")
        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        event_id = created.get("id", "?")
        link = created.get("htmlLink", "")
        
        print(f"[GCAL SUCCESS] ID: {event_id}, Title: {title}, Time: {start_dt}-{end_dt}")
        
        return (
            f"✅ Event '{title}' berhasil dibuat di Google Calendar!\n"
            f"📅 {start_dt.strftime('%d %b %Y %H:%M')} - {end_dt.strftime('%H:%M')} WIB\n"
            f"🔗 {link}"
        )
    except Exception as e:
        error_msg = f"Gagal membuat GCal event: {str(e)}"
        print(f"[GCAL ERROR] {error_msg}")
        return error_msg

def list_google_calendars() -> str:
    """Melihat daftar kalender yang tersedia di akun Google kamu."""
    try:
        service = _build_gcal_service()
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        if not calendars:
            return "Tidak ditemukan kalender di akun ini."
            
        result = "Daftar Kalender Google kamu:\n"
        for cal in calendars:
            primary_mark = " (PRIMARY)" if cal.get('primary') else ""
            result += f"- {cal['summary']} (ID: {cal['id']}){primary_mark}\n"
        
        result += "\n💡 Jika 'primary' bukan kalender yang kamu mau, silakan set GCAL_CALENDAR_ID dengan ID di atas."
        return result
    except Exception as e:
        return f"Gagal list kalender: {str(e)}"
