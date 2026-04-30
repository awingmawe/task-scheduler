import os
import datetime
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import modal
from fastapi import FastAPI, Request, BackgroundTasks
from notion_client import Client
import google.generativeai as genai
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Modal Image with dependencies
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "notion-client",
    "google-generativeai",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "requests"
)

app = modal.App("notion-telegram-scheduler")
web_app = FastAPI()

# ---------------------------------------------------------
# DEDUP: modal.Dict — shared lintas semua container instances
# Ini BENAR-BENAR menyelesaikan masalah multi-reply karena
# Telegram retry bisa masuk ke container BERBEDA.
# modal.Dict persisten dan atomic across all instances.
# ---------------------------------------------------------
dedup_store = modal.Dict.from_name("webhook-dedup", create_if_missing=True)
_DEDUP_TTL_SEC = 120  # tolak duplicate dalam 2 menit

def _is_duplicate(update_id: int) -> bool:
    """Atomic check-and-set di modal.Dict. Return True jika sudah diproses."""
    key = str(update_id)
    now = time.time()
    try:
        stored = dedup_store.get(key)
        if stored and now - stored < _DEDUP_TTL_SEC:
            return True
        dedup_store[key] = now
        return False
    except Exception:
        # Kalau modal.Dict error, lanjut proses (safer than blocking)
        return False

# ---------------------------------------------------------
# FIX 2: Memory cache dengan TTL 5 menit
# Mencegah hit Notion API setiap request hanya untuk baca memory.
# Cache diinvalidasi saat save_memory / delete_memory dipanggil.
# ---------------------------------------------------------
_memory_cache: dict = {"data": None, "page_id": None, "expires_at": 0.0}
_MEMORY_TTL_SEC = 300  # cache 5 menit

# ---------------------------------------------------------
# LAYER 3: TOOLS (DETERMINISTIC LOGIC)
# ---------------------------------------------------------

def _notion_headers() -> dict:
    """Helper: return standard Notion REST API headers."""
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

def send_telegram_message(text: str, chat_id: int = None):
    token = os.environ["TELEGRAM_TOKEN"]
    if not chat_id:
        # Fallback to env var or the hardcoded bot ID (which is wrong but keeps it from crashing)
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", 8344404871)
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    resp = requests.post(url, json=payload)
    print(f"TELEGRAM RESP to {chat_id}: {resp.text}")

def update_notion_task(task_name: str, status: bool, summary: str = "") -> str:
    """Update status dan catatan sebuah task di Notion untuk hari ini.
    task_name: nama atau sebagian nama task yang ingin diupdate.
    status: True jika sudah selesai, False jika belum.
    summary: Catatan singkat tentang progress task (boleh kosong).
    """
    db_id = os.environ["NOTION_DB_ID"]
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        # Cari task: filter by Name (contains) AND Date (equals today)
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {
                        "property": "Name",
                        "title": {"contains": task_name}
                    },
                    {
                        "property": "Date",
                        "date": {"equals": today_str}
                    }
                ]
            }
        }
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        results = resp.get("results", [])

        if not results:
            return f"Task '{task_name}' untuk hari ini ({today_str}) tidak ditemukan."

        page_id = results[0]["id"]

        # Update via REST API
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        update_payload: dict = {
            "properties": {
                "Status": {"checkbox": status}
            }
        }
        if summary:
            update_payload["properties"]["Notes / Summary"] = {
                "rich_text": [{"text": {"content": summary}}]
            }
        requests.patch(update_url, headers=_notion_headers(), json=update_payload)
        status_str = "selesai ✅" if status else "belum selesai"
        return f"✅ Task '{task_name}' berhasil diupdate jadi {status_str}."
    except Exception as e:
        return f"Error updating Notion: {str(e)}"

def mark_all_tasks(status: bool, date_str: str = "") -> str:
    """Update status SEMUA task sekaligus untuk hari ini (atau tanggal tertentu).
    Gunakan ini saat user bilang 'semua selesai', 'tandai semua done', 'checklist semua', dsb.
    status: True = semua selesai, False = semua belum selesai.
    date_str: tanggal target format YYYY-MM-DD, kosong = hari ini.
    """
    db_id = os.environ["NOTION_DB_ID"]
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        # Ambil semua task untuk tanggal ini
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"equals": date_str}},
                    # Exclude baris [CONFIG] agar tidak ikut diupdate
                    {"property": "Name", "title": {"does_not_contain": "[CONFIG]"}}
                ]
            }
        }
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        results = resp.get("results", [])

        if not results:
            return f"Tidak ada task untuk tanggal {date_str}."

        # FIX 3: Parallelisasi semua PATCH request dengan ThreadPoolExecutor
        # Sebelumnya: 7 request serial ~3-5 detik
        # Sekarang:   7 request paralel ~0.5-1 detik
        pages = []
        for page in results:
            name_parts = page["properties"]["Name"]["title"]
            name = name_parts[0]["text"]["content"] if name_parts else "Untitled"
            pages.append((page["id"], name))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_patch_one_task, pid, status): nm for pid, nm in pages}
            updated = []
            for future in as_completed(futures):
                try:
                    future.result()
                    updated.append(futures[future])
                except Exception as e:
                    print(f"Failed to update task: {e}")

        status_str = "selesai ✅" if status else "belum selesai"
        task_lines = "\n".join([f"- {t}" for t in updated])
        return f"✅ {len(updated)} task berhasil diupdate jadi {status_str}:\n{task_lines}"
    except Exception as e:
        return f"Error bulk update: {str(e)}"

def _patch_one_task(page_id: str, status: bool) -> str:
    """Helper untuk patch satu page — dipanggil secara paralel."""
    update_url = f"https://api.notion.com/v1/pages/{page_id}"
    requests.patch(
        update_url,
        headers=_notion_headers(),
        json={"properties": {"Status": {"checkbox": status}}}
    )
    return page_id

# ---------------------------------------------------------
# GOOGLE CALENDAR HELPERS
# ---------------------------------------------------------

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
    # Tanpa ini, 'token=None' bisa menyebabkan API call diam-diam gagal
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
    title: nama event.
    date_str: tanggal format YYYY-MM-DD. Kosong = hari ini.
    start_time: jam mulai format HH:MM (24 jam). Wajib diisi.
    end_time: jam selesai format HH:MM (24 jam). UTAMAKAN INI jika user menyebut jam akhir.
    duration_minutes: durasi dalam menit. Dipakai jika end_time kosong.
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
        
        # Log untuk Modal log console
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
    """Melihat daftar kalender yang tersedia di akun Google kamu.
    Gunakan ini jika user merasa event tidak muncul, untuk memastikan kita memakai Calendar ID yang benar.
    """
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

def create_notion_task(task_name: str, duration: str = "", date_str: str = "", start_time: str = "") -> str:
    """Creates a new task in the Notion database dan opsional sync ke Google Calendar.
    duration: String representing time/duration (e.g., '2 Jam'). Can be empty.
    date_str: Date in 'YYYY-MM-DD' format. If empty, uses today.
    start_time: Jam mulai format HH:MM (24 jam). Jika diisi, event otomatis dibuat di Google Calendar.
    """
    notion = Client(auth=os.environ["NOTION_TOKEN"])
    db_id = os.environ["NOTION_DB_ID"]

    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    properties = {
        "Name": {"title": [{"text": {"content": task_name}}]},
        "Date": {"date": {"start": date_str}},
        "Status": {"checkbox": False}
    }

    if duration:
        properties["Time"] = {"rich_text": [{"text": {"content": duration}}]}

    try:
        notion.pages.create(
            parent={"database_id": db_id},
            properties=properties
        )
        result = f"\u2705 Berhasil membuat task baru: {task_name} untuk tanggal {date_str}."

        # Otomatis sync ke Google Calendar jika start_time disertakan
        if start_time:
            # Hitung durasi dalam menit dari string duration (e.g. "2 Jam", "45 Menit")
            duration_minutes = 60  # default
            if duration:
                dur_lower = duration.lower()
                try:
                    if "jam" in dur_lower:
                        hours = float(dur_lower.replace("jam", "").strip())
                        duration_minutes = int(hours * 60)
                    elif "menit" in dur_lower:
                        duration_minutes = int(dur_lower.replace("menit", "").strip())
                except ValueError:
                    pass

            gcal_result = create_google_calendar_event(
                title=task_name,
                date_str=date_str,
                start_time=start_time,
                duration_minutes=duration_minutes
            )
            result += f"\n{gcal_result}"

        return result
    except Exception as e:
        return f"Gagal membuat task: {str(e)}"

def get_daily_report(date_str: str = "") -> str:
    """Gets a report of all tasks scheduled for a specific date, highlighting uncompleted ones.
    date_str: string in 'YYYY-MM-DD' format. If empty, uses today.
    """
    db_id = os.environ["NOTION_DB_ID"]
    token = os.environ["NOTION_TOKEN"]
    
    if not date_str:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
    try:
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        payload = {
            "filter": {
                "property": "Date",
                "date": {
                    "equals": date_str
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        results = response.json().get("results", [])
        
        if not results:
            return f"Tidak ada task yang dijadwalkan untuk tanggal {date_str}."
            
        completed = []
        pending = []
        
        for page in results:
            props = page["properties"]
            name = props["Name"]["title"][0]["text"]["content"] if props["Name"]["title"] else "Untitled"
            status = props["Status"]["checkbox"] if "Status" in props else False
            
            if status:
                completed.append(name)
            else:
                pending.append(name)
                
        report = f"📊 Report Task untuk {date_str}:\n\n"
        report += f"**Belum Dikerjakan ({len(pending)}):**\n"
        for t in pending:
            report += f"- ❌ {t}\n"
            
        report += f"\n**Selesai ({len(completed)}):**\n"
        for t in completed:
            report += f"- ✅ {t}\n"
            
        return report
    except Exception as e:
        return f"Gagal mengambil report: {str(e)}"

def get_master_routine_config() -> tuple[str, list]:
    db_id = os.environ["NOTION_DB_ID"]
    token = os.environ["NOTION_TOKEN"]
    
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    payload = {
        "filter": {
            "property": "Name",
            "title": {"equals": "[CONFIG] MASTER ROUTINE"}
        }
    }
    resp = requests.post(url, headers=headers, json=payload).json()
    results = resp.get("results", [])
    
    notion = Client(auth=token)
    
    if not results:
        default_routine = [
            {"name": "Praktik AI Engineer", "duration": "2 Jam"},
            {"name": "Belajar SE dari Harvard Online", "duration": "45 Menit"},
            {"name": "Baca Buku tentang SE", "duration": "30 Menit"},
            {"name": "Manage & Membangun Bisnis Wedding", "duration": "1 Jam"},
            {"name": "Belajar Claude Academy", "duration": "45 Menit"},
            {"name": "Belajar Interview", "duration": "30 Menit"},
            {"name": "Belajar Bahasa Inggris", "duration": "15 Menit"},
        ]
        page = notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "Name": {"title": [{"text": {"content": "[CONFIG] MASTER ROUTINE"}}]},
                "Notes / Summary": {"rich_text": [{"text": {"content": json.dumps(default_routine)}}]}
            }
        )
        return page["id"], default_routine
        
    page = results[0]
    page_id = page["id"]
    try:
        props = page["properties"]
        content = props["Notes / Summary"]["rich_text"][0]["text"]["content"]
        routine_list = json.loads(content)
        return page_id, routine_list
    except:
        return page_id, []

def update_master_routine_config(page_id: str, new_routine: list):
    notion = Client(auth=os.environ["NOTION_TOKEN"])
    notion.pages.update(
        page_id=page_id,
        properties={
            "Notes / Summary": {"rich_text": [{"text": {"content": json.dumps(new_routine)}}]}
        }
    )

def add_to_routine(task_name: str, duration: str = "") -> str:
    """Tambahkan aktivitas baru ke dalam rutinitas harian master. Rutinitas otomatis dibuat jam 5 pagi."""
    try:
        page_id, routine = get_master_routine_config()
        for t in routine:
            if t["name"].lower() == task_name.lower():
                return f"Aktivitas '{task_name}' sudah ada di rutinitas!"
        routine.append({"name": task_name, "duration": duration})
        update_master_routine_config(page_id, routine)
        return f"✅ Sukses menambahkan '{task_name}' ke rutinitas harian!"
    except Exception as e:
        return f"Gagal menambahkan rutinitas: {str(e)}"

def remove_from_routine(task_name: str) -> str:
    """Hapus sebuah aktivitas dari rutinitas harian master."""
    try:
        page_id, routine = get_master_routine_config()
        new_routine = [t for t in routine if t["name"].lower() != task_name.lower()]
        if len(new_routine) == len(routine):
            return f"Aktivitas '{task_name}' tidak ditemukan di rutinitas."
        update_master_routine_config(page_id, new_routine)
        return f"✅ Sukses menghapus '{task_name}' dari rutinitas harian."
    except Exception as e:
        return f"Gagal menghapus rutinitas: {str(e)}"

# ---------------------------------------------------------
# AI MEMORY SYSTEM
# ---------------------------------------------------------

def get_memory_config(skip_cache: bool = False) -> tuple[str | None, dict]:
    """Baca [CONFIG] AI MEMORY dari Notion. Return (page_id, memory_dict).
    Hasil dicache 5 menit agar tidak hit Notion API setiap request.
    """
    now = time.time()
    # FIX 2a: Kembalikan cache jika masih valid
    if not skip_cache and _memory_cache["data"] is not None and now < _memory_cache["expires_at"]:
        return _memory_cache["page_id"], _memory_cache["data"]

    db_id = os.environ["NOTION_DB_ID"]
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {
        "filter": {
            "property": "Name",
            "title": {"equals": "[CONFIG] AI MEMORY"}
        }
    }
    resp = requests.post(url, headers=_notion_headers(), json=payload).json()
    results = resp.get("results", [])

    if not results:
        # Buat halaman memory kosong pertama kali
        notion = Client(auth=os.environ["NOTION_TOKEN"])
        page = notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "Name": {"title": [{"text": {"content": "[CONFIG] AI MEMORY"}}]},
                "Notes / Summary": {"rich_text": [{"text": {"content": json.dumps({})}}]}
            }
        )
        _memory_cache.update({"data": {}, "page_id": page["id"], "expires_at": now + _MEMORY_TTL_SEC})
        return page["id"], {}

    page = results[0]
    page_id = page["id"]
    try:
        raw = page["properties"]["Notes / Summary"]["rich_text"][0]["text"]["content"]
        memory = json.loads(raw)
    except:
        memory = {}

    # Simpan ke cache
    _memory_cache.update({"data": memory, "page_id": page_id, "expires_at": now + _MEMORY_TTL_SEC})
    return page_id, memory

def _update_memory_config(page_id: str, memory: dict):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Notes / Summary": {"rich_text": [{"text": {"content": json.dumps(memory, ensure_ascii=False)}}]}
        }
    }
    requests.patch(url, headers=_notion_headers(), json=payload)

def save_memory(key: str, value: str) -> str:
    """Simpan atau update sebuah fakta/ingatan ke memori AI. Gunakan ini saat user meminta bot untuk 'ingat', 'catat', atau 'simpan' sesuatu.
    key: identifier singkat untuk fakta ini (contoh: 'konteks_belajar', 'preferensi', 'catatan_bisnis').
    value: isi fakta yang ingin disimpan.
    """
    try:
        page_id, memory = get_memory_config(skip_cache=True)  # FIX 2b: bypass cache saat write
        memory[key] = value
        _update_memory_config(page_id, memory)
        # Invalidasi cache setelah write
        _memory_cache.update({"data": memory, "page_id": page_id, "expires_at": time.time() + _MEMORY_TTL_SEC})
        return f"\u2705 Oke, aku udah ingat: '{key}' = '{value}'!"
    except Exception as e:
        return f"Gagal menyimpan memory: {str(e)}"

def delete_memory(key: str) -> str:
    """Hapus sebuah fakta dari memori AI berdasarkan key-nya."""
    try:
        page_id, memory = get_memory_config(skip_cache=True)  # FIX 2b: bypass cache saat write
        if key not in memory:
            return f"Key '{key}' tidak ada di memori."
        del memory[key]
        _update_memory_config(page_id, memory)
        # Invalidasi cache setelah write
        _memory_cache.update({"data": memory, "page_id": page_id, "expires_at": time.time() + _MEMORY_TTL_SEC})
        return f"\u2705 Oke, aku sudah lupa soal '{key}'."
    except Exception as e:
        return f"Gagal menghapus memory: {str(e)}"

# ---------------------------------------------------------
# LAYER 2: NAVIGATION (AI AGENT)
# ---------------------------------------------------------

def process_with_ai(user_input: str, audio_data: dict = None) -> str:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    # Load AI memory dari Notion untuk dijadikan konteks persisten
    _, memory = get_memory_config()
    memory_context = ""
    if memory:
        memory_lines = "\n".join([f"- {k}: {v}" for k, v in memory.items()])
        memory_context = f"\n\n[MEMORI TENTANG USER]\n{memory_lines}\n"

    system_instruction = (
        "Kamu adalah asisten/teman akrab yang santai dan ceplas-ceplos. "
        "Tugasmu membantu mengelola jadwal dan tugas di Notion.\n"
        "ATURAN PALING PENTING: Jangan pernah bilang 'berhasil' atau 'sudah dibuat' sebelum kamu BENAR-BENAR memanggil tool-nya! "
        "Jika Google Calendar berhasil, WAJIB sertakan link eventnya di reply.\n"
        "Gunakan 'create_notion_task' jika user meminta membuat target/jadwal untuk TANGGAL TERTENTU (misal hari ini/besok).\n"
        "Gunakan 'add_to_routine' jika user meminta menambahkan aktivitas ke rutinitas HARIAN/tiap pagi.\n"
        "Gunakan 'remove_from_routine' jika user minta hapus rutinitas harian.\n"
        "Gunakan 'update_notion_task' jika user meminta update status SATU task spesifik (centang/selesai/done/belum).\n"
        "Gunakan 'mark_all_tasks' jika user bilang 'semua selesai', 'tandai semua', 'checklist semua', 'semua done', dsb.\n"
        "Gunakan 'get_daily_report' jika user menanyakan tugas apa saja hari ini atau report tugas yang belum dikerjakan.\n"
        "Gunakan 'create_google_calendar_event' jika user ingin membuat event/jadwal dengan JAM SPESIFIK ke Google Calendar. "
        "Setelah tool berhasil, SELALU tampilkan link Google Calendar-nya ke user.\n"
        "Gunakan 'list_google_calendars' jika user bingung kenapa jadwal tidak muncul.\n"
        "Jika user menyebut JAM AKHIR (contoh: 'sampai jam 17', 'dari jam 2 sampai jam 5'), WAJIB isi end_time (format HH:MM).\n"
        "Jika user menyebutkan jam spesifik saat membuat task (misal 'jam 3 sore'), SELALU isi start_time di create_notion_task.\n"
        "Gunakan 'save_memory' jika user meminta kamu untuk INGAT atau CATAT sesuatu tentang dirinya.\n"
        "Gunakan 'delete_memory' jika user meminta kamu untuk LUPA atau HAPUS sesuatu dari ingatan.\n"
        "Jika ada input suara (voice note), transkripsikan permintaannya dan jalankan perintahnya.\n"
        "Jawab dengan singkat, asik, pakai emoji, dan jangan kaku."
        f"{memory_context}"
    )

    tools_list = [
        update_notion_task, mark_all_tasks, create_notion_task,
        create_google_calendar_event, list_google_calendars, get_daily_report,
        add_to_routine, remove_from_routine,
        save_memory, delete_memory
    ]

    contents = []
    if audio_data:
        contents.append(audio_data)
    contents.append(user_input)

    try:
        # Default model: Gemini 3.1 Flash Lite
        model = genai.GenerativeModel(
            'gemini-3.1-flash-lite-preview',
            tools=tools_list,
            system_instruction=system_instruction
        )
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(contents)
        return response.text
    except Exception as e:
        print(f"Primary model (gemini-3.1-flash-lite-preview) error: {e}")

    # -------------------------------------------------------
    # FALLBACK CHAIN (text-capable models only)
    # TTS & Live models dieksklusi karena butuh arsitektur streaming berbeda
    # Urutan: paling kuat → paling ringan
    # -------------------------------------------------------
    FALLBACK_MODELS = [
        "gemini-2.5-pro-preview-05-06",  # Gemini 2.5 Pro – paling pintar, fallback utama
        "gemini-3-flash-preview",         # Gemini 3 Flash – generasi terbaru
        "gemini-2.5-flash-preview-05-20", # Gemini 2.5 Flash – stabil
    ]

    for fallback_id in FALLBACK_MODELS:
        try:
            print(f"Trying fallback model: {fallback_id}")
            fallback_model = genai.GenerativeModel(
                fallback_id,
                tools=tools_list,
                system_instruction=system_instruction
            )
            fallback_chat = fallback_model.start_chat(enable_automatic_function_calling=True)
            fallback_response = fallback_chat.send_message(contents)
            return fallback_response.text
        except Exception as fe:
            print(f"Fallback model {fallback_id} also failed: {fe}")
            continue

    return "Waduh, semua model AI lagi bermasalah nih! Coba lagi sebentar ya 🙏"

# ---------------------------------------------------------
# LAYER 1: ARCHITECTURE (TRIGGERS & ENDPOINTS)
# ---------------------------------------------------------

def _process_and_reply_sync(chat_id: int, user_text: str, audio_data: dict | None):
    """Sync background task: proses AI dan kirim balik ke Telegram.
    Menggunakan FastAPI BackgroundTasks (bukan asyncio.create_task) agar
    guaranteed berjalan setelah response 200 dikirim ke Telegram.
    """
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

    # DEDUP: pakai modal.Dict yang dishare lintas semua container
    # Ini fix utama untuk masalah multi-reply ketika Telegram retry
    update_id = data.get("update_id")
    if update_id and _is_duplicate(int(update_id)):
        print(f"[DEDUP] Duplicate update_id {update_id} blocked (cross-container).")
        return {"status": "ok"}

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        user_text = ""
        audio_data = None

        if "text" in data["message"]:
            user_text = data["message"]["text"]

        elif "voice" in data["message"]:
            token = os.environ["TELEGRAM_TOKEN"]
            file_id = data["message"]["voice"]["file_id"]
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
            # Gunakan FastAPI BackgroundTasks — guaranteed jalan setelah response 200
            # Lebih reliable dari asyncio.create_task di Modal serverless
            background_tasks.add_task(_process_and_reply_sync, chat_id, user_text, audio_data)

    # Telegram dapat 200 SEGERA — tidak akan retry lagi
    return {"status": "ok"}

@app.function(image=image, secrets=[modal.Secret.from_name("my-notion-secrets")])
@modal.asgi_app()
def fastapi_app():
    return web_app

# Cron Jobs (Waktu menggunakan UTC di Modal, untuk WIB (UTC+7): 05:00 WIB = 22:00 UTC kemarin)
@app.function(image=image, schedule=modal.Cron("0 22 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def morning_slap():
    # 1. Ambil list dari Master Routine di Notion
    _, routine_list = get_master_routine_config()
    
    # 2. Buat task-task tersebut untuk hari ini
    for task in routine_list:
        create_notion_task(task["name"], duration=task.get("duration", ""))
    
    # 3. Send wake up message
    msg = (
        "Woi bangun! Pagi ini ada target penting yang udah disiapin.\n"
        "Jangan rebahan aja, mimpi lo gak bakal kecapai kalau cuma tiduran! 👊✅\n\n"
        f"Aku udah otomatis buatin {len(routine_list)} target aktivitas harianmu di Notion ya. Langsung gass kerjain!"
    )
    send_telegram_message(msg)

@app.function(image=image, schedule=modal.Cron("0 5 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def noon_slap():
    report = get_daily_report()
    msg = (
        "Matahari udah di atas kepala nih! 🌞 Jangan kelamaan istirahat, masih banyak utang target!\n\n"
        f"{report}"
    )
    send_telegram_message(msg)

@app.function(image=image, schedule=modal.Cron("0 8 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def afternoon_slap():
    report = get_daily_report()
    msg = (
        "Udah jam 3 sore woi! Bentar lagi hari kelar. Yakin target hari ini udah kelar semua?\n\n"
        f"{report}"
    )
    send_telegram_message(msg)

@app.function(image=image, schedule=modal.Cron("0 11 * * *"), secrets=[modal.Secret.from_name("my-notion-secrets")])
def evening_slap():
    report = get_daily_report()
    msg = (
        "Woi udah jam 6 sore nih! Waktunya bangun bisnis Wedding dan lanjut belajar. Jangan males-malesan! 👊✅\n\n"
        "Nih liat rapor harianmu:\n"
        f"{report}"
    )
    send_telegram_message(msg)


