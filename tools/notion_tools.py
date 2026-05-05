import os
import requests
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import _notion_headers, _today_wib
from gcal_tools import create_google_calendar_event
from memory_tools import get_memory_config, _update_memory_config

# --- DATABASE TEMPLATES ---
DB_TEMPLATES = {
    "Finance": {
        "properties": {
            "Name": {"title": {}},
            "Amount": {"number": {"format": "number"}},
            "Date": {"date": {}},
            "Category": {"select": {"options": [
                {"name": "Food", "color": "orange"},
                {"name": "Transport", "color": "blue"},
                {"name": "Entertainment", "color": "purple"},
                {"name": "Shopping", "color": "pink"},
                {"name": "Others", "color": "gray"}
            ]}},
            "Type": {"select": {"options": [
                {"name": "Income", "color": "green"},
                {"name": "Expense", "color": "red"}
            ]}},
            "Receipt": {"files": {}}
        }
    },
    "Journal": {
        "properties": {
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Mood": {"select": {"options": [
                {"name": "Happy", "color": "yellow"},
                {"name": "Neutral", "color": "gray"},
                {"name": "Sad", "color": "blue"},
                {"name": "Productive", "color": "green"},
                {"name": "Tired", "color": "purple"}
            ]}},
            "Entry": {"rich_text": {}}
        }
    },
    "Projects": {
        "properties": {
            "Name": {"title": {}},
            "Status": {"status": {}},
            "Deadline": {"date": {}},
            "Priority": {"select": {"options": [
                {"name": "High", "color": "red"},
                {"name": "Medium", "color": "orange"},
                {"name": "Low", "color": "blue"}
            ]}}
        }
    }
}

def _task_exists_for_date(task_name: str, date_str: str) -> bool:
    """Cek apakah task dengan nama persis sudah ada di Notion untuk tanggal tertentu."""
    db_id = os.environ["NOTION_DB_ID"]
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Date", "date": {"equals": date_str}},
                {"property": "Name", "title": {"equals": task_name}}
            ]
        }
    }
    try:
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        results = resp.get("results", [])
        return any(
            r["properties"]["Name"]["title"][0]["text"]["content"] == task_name
            for r in results
            if r["properties"]["Name"]["title"]
        )
    except:
        return False

def _get_task_streak(task_name: str, date_str: str) -> int:
    """Hitung streak sebuah task dengan melihat hari sebelumnya (WIB)."""
    try:
        dt = datetime.date.fromisoformat(date_str)
        yesterday = (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        db_id = os.environ["NOTION_DB_ID"]
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"equals": yesterday}},
                    {"property": "Name", "title": {"equals": task_name}}
                ]
            }
        }
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        results = resp.get("results", [])
        if results:
            props = results[0]["properties"]
            status = props.get("Status", {}).get("checkbox", False)
            if status:
                prev_streak = props.get("🔥 Streak", {}).get("number") or 0
                return int(prev_streak) + 1
    except Exception as e:
        print(f"[STREAK DEBUG] Error calculating streak for {task_name}: {e}")
    return 1

def _get_all_streaks_for_yesterday(date_str: str) -> dict:
    """Kembalikan dict {task_name: streak_count} dari hari kemarin."""
    try:
        dt = datetime.date.fromisoformat(date_str)
        yesterday = (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        db_id = os.environ["NOTION_DB_ID"]
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {"filter": {"property": "Date", "date": {"equals": yesterday}}}
        streaks = {}
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        for r in resp.get("results", []):
            props = r["properties"]
            name_list = props["Name"]["title"]
            if not name_list: continue
            name = name_list[0]["text"]["content"]
            status = props.get("Status", {}).get("checkbox", False)
            streak = props.get("🔥 Streak", {}).get("number") or 0
            streaks[name] = int(streak) if status else 0
        return streaks
    except:
        return {}

def update_notion_task(task_name: str, status: bool, summary: str = "") -> str:
    """Update status dan catatan sebuah task di Notion untuk hari ini (dengan grace period dini hari)."""
    db_id = os.environ["NOTION_DB_ID"]
    
    # Timezone WIB
    wib_tz = datetime.timezone(datetime.timedelta(hours=7))
    now_wib = datetime.datetime.now(wib_tz)
    today_str = now_wib.strftime("%Y-%m-%d")

    def _query_notion(date_val: str):
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {"property": "Name", "title": {"contains": task_name}},
                    {"property": "Date", "date": {"equals": date_val}}
                ]
            }
        }
        resp = requests.post(url, headers=_notion_headers(), json=payload)
        return resp

    try:
        # 1. Coba hari ini
        resp = _query_notion(today_str)
        if resp.status_code != 200:
            return f"❌ Error Notion API ({resp.status_code}): {resp.text}"
            
        results = resp.json().get("results", [])

        # 2. Grace Period: Jika tidak ketemu dan masih dini hari (< 04:00 WIB), coba kemarin
        target_date = today_str
        if not results and now_wib.hour < 4:
            yesterday_str = (now_wib - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"[GRACE PERIOD] Task '{task_name}' not found for {today_str}. Checking {yesterday_str}...")
            resp = _query_notion(yesterday_str)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    target_date = yesterday_str

        if not results:
            return f"Task '{task_name}' untuk {today_str} tidak ditemukan. Pastikan nama task sesuai atau cek di Notion."

        page_id = results[0]["id"]
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        update_payload: dict = {
            "properties": {
                "Status": {"checkbox": status}
            }
        }
        
        if status:
            streak = _get_task_streak(task_name, today_str)
            update_payload["properties"]["🔥 Streak"] = {"number": streak}
        else:
            update_payload["properties"]["🔥 Streak"] = {"number": 0}
            
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
    """Update status SEMUA task sekaligus untuk hari ini (atau tanggal tertentu)."""
    db_id = os.environ["NOTION_DB_ID"]
    
    # Timezone WIB
    wib_tz = datetime.timezone(datetime.timedelta(hours=7))
    now_wib = datetime.datetime.now(wib_tz)

    if not date_str:
        date_str = now_wib.strftime("%Y-%m-%d")
        is_auto_date = True
    else:
        is_auto_date = False

    def _fetch_all(d_str):
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"equals": d_str}},
                    {"property": "Name", "title": {"does_not_contain": "[CONFIG]"}}
                ]
            }
        }
        return requests.post(url, headers=_notion_headers(), json=payload)

    try:
        resp = _fetch_all(date_str)
        if resp.status_code != 200:
            return f"❌ Error Notion API ({resp.status_code}): {resp.text}"
            
        results = resp.json().get("results", [])

        # Grace Period: Jika tgl hari ini kosong & masih dini hari, coba kemarin
        if not results and is_auto_date and now_wib.hour < 4:
            yesterday_str = (now_wib - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"[MARK ALL GRACE] No tasks for {date_str}, checking {yesterday_str}...")
            resp = _fetch_all(yesterday_str)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    date_str = yesterday_str

        if not results:
            return f"Tidak ada task untuk tanggal {date_str}."

        pages = []
        for page in results:
            name_parts = page["properties"]["Name"]["title"]
            name = name_parts[0]["text"]["content"] if name_parts else "Untitled"
            pages.append((page["id"], name))

        yesterday_streaks = _get_all_streaks_for_yesterday(date_str)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for pid, nm in pages:
                streak = yesterday_streaks.get(nm, 0) + 1 if status else 0
                futures.append(executor.submit(_patch_one_task, pid, status, streak))
            
            updated = []
            for i, future in enumerate(as_completed([f for f in futures])):
                try:
                    future.result()
                    updated.append(pages[i][1])
                except Exception as e:
                    print(f"Failed to update task: {e}")

        status_str = "selesai ✅" if status else "belum selesai"
        task_lines = "\n".join([f"- {t}" for t in updated])
        return f"✅ {len(updated)} task berhasil diupdate jadi {status_str}:\n{task_lines}"
    except Exception as e:
        return f"Error bulk update: {str(e)}"

def _patch_one_task(page_id: str, status: bool, streak: int = 0) -> str:
    """Helper untuk patch satu page — dipanggil secara paralel."""
    update_url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Status": {"checkbox": status},
            "🔥 Streak": {"number": streak}
        }
    }
    requests.patch(update_url, headers=_notion_headers(), json=payload)
    return page_id

def create_notion_task(task_name: str, duration: str = "", date_str: str = "", start_time: str = "") -> str:
    """Buat task baru di Notion untuk tanggal tertentu. Opsional sync ke Google Calendar."""
    db_id = os.environ["NOTION_DB_ID"]
    if not date_str:
        date_str = _today_wib()

    streak = _get_task_streak(task_name, date_str)
    
    properties = {
        "Name": {"title": [{"text": {"content": task_name}}]},
        "Date": {"date": {"start": date_str}},
        "Status": {"checkbox": False},
        "🔥 Streak": {"number": streak}
    }
    if duration:
        properties["Time"] = {"rich_text": [{"text": {"content": duration}}]}

    if _task_exists_for_date(task_name, date_str):
        return f"Task '{task_name}' sudah ada untuk {date_str}. Skip create."

    try:
        url = "https://api.notion.com/v1/pages"
        payload = {"parent": {"database_id": db_id}, "properties": properties}
        resp = requests.post(url, headers=_notion_headers(), json=payload)
        resp.raise_for_status()
        result = f"Task baru '{task_name}' berhasil dibuat untuk {date_str} (Streak: {streak})."

        if start_time:
            duration_minutes = 60
            if duration:
                dur_lower = duration.lower()
                try:
                    if "jam" in dur_lower:
                        duration_minutes = int(float(dur_lower.replace("jam", "").strip()) * 60)
                    elif "menit" in dur_lower:
                        duration_minutes = int(dur_lower.replace("menit", "").strip())
                except ValueError:
                    pass
            gcal_result = create_google_calendar_event(
                title=task_name, date_str=date_str,
                start_time=start_time, duration_minutes=duration_minutes
            )
            result += f"\n{gcal_result}"
        return result
    except Exception as e:
        return f"Gagal membuat task: {str(e)}"

def delete_notion_task(task_name: str, date_str: str = "") -> str:
    """Hapus sebuah task dari Notion berdasarkan nama dan tanggal (dengan grace period)."""
    db_id = os.environ["NOTION_DB_ID"]
    
    # Timezone WIB
    wib_tz = datetime.timezone(datetime.timedelta(hours=7))
    now_wib = datetime.datetime.now(wib_tz)

    if not date_str:
        date_str = now_wib.strftime("%Y-%m-%d")
        is_auto_date = True
    else:
        is_auto_date = False

    def _query(d_str):
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {"property": "Name", "title": {"contains": task_name}},
                    {"property": "Date", "date": {"equals": d_str}},
                    {"property": "Name", "title": {"does_not_contain": "[CONFIG]"}}
                ]
            }
        }
        return requests.post(url, headers=_notion_headers(), json=payload)

    try:
        resp = _query(date_str)
        if resp.status_code != 200:
            return f"❌ Error Notion API ({resp.status_code}): {resp.text}"
            
        results = resp.json().get("results", [])

        # Grace Period: Jika tidak ketemu & dini hari, coba kemarin
        if not results and is_auto_date and now_wib.hour < 4:
            yesterday_str = (now_wib - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"[DELETE GRACE] Task '{task_name}' not found for {date_str}. Checking {yesterday_str}...")
            resp = _query(yesterday_str)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    date_str = yesterday_str

        if not results:
            return f"Task '{task_name}' untuk tanggal {date_str} tidak ditemukan."
        page_id = results[0]["id"]
        del_url = f"https://api.notion.com/v1/pages/{page_id}"
        requests.patch(del_url, headers=_notion_headers(), json={"archived": True})
        return f"Task '{task_name}' ({date_str}) berhasil dihapus."
    except Exception as e:
        return f"Gagal hapus task: {str(e)}"

def get_master_routine_config() -> tuple[str, list]:
    db_id = os.environ["NOTION_DB_ID"]
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {"filter": {"property": "Name", "title": {"equals": "[CONFIG] MASTER ROUTINE"}}}
    resp = requests.post(url, headers=_notion_headers(), json=payload).json()
    results = resp.get("results", [])

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
        page_resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_notion_headers(),
            json={
                "parent": {"database_id": db_id},
                "properties": {
                    "Name": {"title": [{"text": {"content": "[CONFIG] MASTER ROUTINE"}}]},
                    "Notes / Summary": {"rich_text": [{"text": {"content": json.dumps(default_routine)}}]}
                }
            }
        ).json()
        
        if "id" not in page_resp:
            print(f"[ERROR] Gagal membuat [CONFIG] MASTER ROUTINE: {page_resp}")
            return None, default_routine

        return page_resp["id"], default_routine

    page = results[0]
    page_id = page["id"]
    try:
        content = page["properties"]["Notes / Summary"]["rich_text"][0]["text"]["content"]
        return page_id, json.loads(content)
    except:
        return page_id, []

def update_master_routine_config(page_id: str, new_routine: list):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    requests.patch(
        url, headers=_notion_headers(),
        json={"properties": {"Notes / Summary": {"rich_text": [{"text": {"content": json.dumps(new_routine)}}]}}}
    )

def add_to_routine(task_name: str, duration: str = "") -> str:
    """Tambahkan aktivitas baru ke dalam rutinitas harian master."""
    try:
        page_id, routine = get_master_routine_config()
        for t in routine:
            if t["name"].lower() == task_name.lower():
                return f"Aktivitas '{task_name}' sudah ada di rutinitas!"
        routine.append({"name": task_name, "duration": duration})
        update_master_routine_config(page_id, routine)
        
        today = _today_wib()
        create_res = create_notion_task(task_name, duration=duration, date_str=today)
        
        return f"✅ Sukses menambahkan '{task_name}' ke rutinitas harian! ({create_res})"
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

# --- DYNAMIC DATABASE TOOLS (Issue #15 & #16) ---

def _get_parent_page() -> dict:
    """Ambil parent page ID dari database utama (NOTION_DB_ID)."""
    db_id = os.environ["NOTION_DB_ID"]
    url = f"https://api.notion.com/v1/databases/{db_id}"
    try:
        resp = requests.get(url, headers=_notion_headers())
        resp.raise_for_status()
        parent = resp.json().get("parent", {})
        
        # FIX (PR #17): Notion API prohibits creating a DB with a workspace parent.
        if parent.get("type") == "workspace":
            print("[WARN] Parent is workspace. Notion API prohibits direct DB creation under workspace.")
            # Fallback to a secondary env var if available, else return error info
            parent_page_id = os.environ.get("PARENT_PAGE_ID")
            if parent_page_id:
                return {"type": "page_id", "page_id": parent_page_id}
            return {"error": "workspace_parent_not_supported"}
            
        return parent
    except Exception as e:
        print(f"[ERROR] _get_parent_page: {e}")
        return {}

def _check_database_exists(db_name: str) -> bool:
    """Cek apakah database dengan nama tersebut sudah ada di workspace (with pagination)."""
    url = "https://api.notion.com/v1/search"
    has_more = True
    next_cursor = None
    
    try:
        while has_more:
            payload = {
                "query": db_name,
                "filter": {"property": "object", "value": "database"},
                "page_size": 100
            }
            if next_cursor:
                payload["start_cursor"] = next_cursor
                
            resp = requests.post(url, headers=_notion_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            results = data.get("results", [])
            for res in results:
                titles = res.get("title", [])
                if titles:
                    actual_name = titles[0].get("plain_text", "")
                    if actual_name.lower() == db_name.lower():
                        return True
            
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
            
        return False
    except Exception as e:
        print(f"[ERROR] _check_database_exists: {e}")
        return False

def create_notion_database(db_name: str, template_type: str) -> str:
    """
    Buat database baru di Notion berdasarkan template.
    HANYA dijalankan setelah konfirmasi user.
    """
    if template_type not in DB_TEMPLATES:
        return f"Gagal: Template '{template_type}' tidak tersedia. Pilih: Finance, Journal, atau Projects."

    # 1. Cek Duplikasi
    if _check_database_exists(db_name):
        return f"Gagal: Database dengan nama '{db_name}' sudah ada di Notion. Coba nama lain."

    # 2. Dapatkan Parent
    parent = _get_parent_page()
    if not parent:
        return "Gagal: Tidak bisa menemukan Parent Page untuk membuat database baru."
    
    if parent.get("error") == "workspace_parent_not_supported":
        return "❌ Gagal: Database utama Anda berada di level 'Workspace'. Notion API tidak mengizinkan pembuatan database baru langsung di bawah Workspace. Silakan tentukan 'PARENT_PAGE_ID' di environment variables atau pindahkan database utama ke dalam sebuah Page."

    # 3. Susun Payload
    template = DB_TEMPLATES[template_type]
    payload = {
        "parent": parent,
        "title": [{"type": "text", "text": {"content": db_name}}],
        "properties": template["properties"]
    }

    # 4. Hit API
    try:
        url = "https://api.notion.com/v1/databases"
        resp = requests.post(url, headers=_notion_headers(), json=payload)
        
        if resp.status_code != 200:
            return f"❌ Gagal membuat database ({resp.status_code}): {resp.text}"
            
        res_json = resp.json()
        db_id = res_json.get("id")
        db_url = res_json.get("url")

        # 5. Simpan ke Registry (AI MEMORY)
        registry_success = True
        reg_error_msg = ""
        try:
            page_id, memory = get_memory_config(skip_cache=True)
            registry = memory.get("_DATABASE_REGISTRY", {})
            registry[db_name] = {
                "id": db_id,
                "template": template_type,
                "created_at": _today_wib()
            }
            memory["_DATABASE_REGISTRY"] = registry
            _update_memory_config(page_id, memory)
        except Exception as reg_err:
            registry_success = False
            reg_error_msg = str(reg_err)
            print(f"[REGISTRY ERROR] Gagal mencatat DB ke memori: {reg_err}")

        if not registry_success:
            return f"⚠️ Database '{db_name}' ({template_type}) telah dibuat di Notion, tetapi GAGAL disimpan ke Registry AI Memory: {reg_error_msg}. Database ini tidak akan bisa digunakan oleh tool AI lainnya sebelum didaftarkan manual."

        return f"✅ Berhasil! Database '{db_name}' ({template_type}) telah dibuat.\n🔗 Link: {db_url}"
        
    except Exception as e:
        return f"Gagal membuat database: {str(e)}"

def insert_into_dynamic_db(db_name: str, properties: dict) -> str:
    """
    Masukkan data ke database dinamis yang sudah pernah dibuat.
    Properties harus sesuai dengan schema template-nya.
    """
    try:
        _, memory = get_memory_config()
        registry = memory.get("_DATABASE_REGISTRY", {})
        
        db_info = None
        for name, info in registry.items():
            if name.lower() == db_name.lower():
                db_info = info
                break
        
        if not db_info:
            return f"Database '{db_name}' tidak ditemukan di Registry AI. Silakan buat dulu pakai 'create_notion_database'."

        db_id = db_info["id"]
        url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": db_id},
            "properties": properties
        }
        
        resp = requests.post(url, headers=_notion_headers(), json=payload)
        if resp.status_code == 200:
            return f"✅ Data berhasil dimasukkan ke '{db_name}'."
        else:
            # FIX (PR #17): Return a more user-friendly error message from Notion API
            try:
                error_data = resp.json()
                error_msg = error_data.get("message", resp.text)
                return f"❌ Gagal masukkan data ke '{db_name}': {error_msg}"
            except:
                return f"❌ Gagal masukkan data ke '{db_name}': {resp.text}"
            
    except Exception as e:
        return f"Error insert dynamic db: {str(e)}"
