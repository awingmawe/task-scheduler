# Project Constitution — Task Scheduler Bot

> **Baca file ini di awal setiap session baru.** Ini adalah satu-satunya sumber kebenaran tentang arsitektur, aturan, dan status project.

---

## 🧠 TL;DR — Konteks Cepat

Ini adalah **Telegram bot** yang terhubung ke **Notion** sebagai database task harian + **Google Calendar** untuk scheduling, dengan **Gemini AI** sebagai otak pengambil keputusan. Bot di-deploy di **Modal** (serverless). User bisa chat teks atau kirim voice note, bot akan menjalankan aksi yang sesuai di Notion/GCal.

- **Repo GitHub:** `awingmawe/task-scheduler`
- **Branch aktif:** `feature/daily-task-scheduler`
- **Deploy target:** Modal (serverless)
- **File utama:** `tools/main.py`
- **Bahasa:** Python 3.14

---

## 🏗️ Arsitektur — 3-Layer Design

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1: ARCHITECTURE  (Triggers & Endpoints)          │
│  - FastAPI webhook /webhook (menerima update Telegram)  │
│  - Cron jobs: morning_slap, noon_slap, afternoon_slap,  │
│    evening_slap (via modal.Cron)                        │
├─────────────────────────────────────────────────────────┤
│  LAYER 2: NAVIGATION  (AI Agent)                        │
│  - process_with_ai() — Gemini dengan function calling   │
│  - enable_automatic_function_calling = True             │
│  - Fallback chain model jika primary gagal              │
├─────────────────────────────────────────────────────────┤
│  LAYER 3: TOOLS  (Deterministic Logic)                  │
│  - Notion API (raw requests, bukan notion-client)       │
│  - Google Calendar API                                  │
│  - Telegram send message                                │
│  - AI Memory System (disimpan di Notion)                │
└─────────────────────────────────────────────────────────┘
```

**Flow lengkap:**
1. Telegram kirim webhook → FastAPI `/webhook`
2. Dedup check via `modal.Dict` (cross-container, TTL 120s)
3. `BackgroundTasks.add_task()` → `_process_and_reply_sync()`
4. Gemini decide tool mana yang dipanggil
5. Tool execute Notion/GCal/Memory operation
6. Reply dikirim balik ke Telegram user

---

## 📁 File Map

### Core (deployed ke Modal)
| File | Keterangan |
|------|------------|
| `tools/main.py` | **Entry point.** FastAPI webhook handler dan orkestrasi utama. |
| `tools/ai_agent.py` | **Otak AI.** Logic Gemini agent, function calling, dan centralized fallback chain. |
| `tools/notion_tools.py` | **Notion Tool.** Semua interaksi Notion API (tasks, routine, status). |
| `tools/gcal_tools.py` | **Calendar Tool.** Interaksi Google Calendar API. |
| `tools/cron_jobs.py` | **Scheduled Tasks.** Logic untuk morning, noon, afternoon, dan evening slaps. |
| `tools/reports.py` | **Reporting.** Generator laporan harian dan progres habit. |
| `tools/memory_tools.py` | **AI Memory.** CRUD memory AI yang disimpan di Notion. |
| `tools/config.py` | **Configuration.** Centralized environment variables dan Modal app setup. |
| `tools/telegram_tools.py` | **Messaging.** Utility untuk kirim pesan ke Telegram. |

### Setup Scripts (jalankan sekali secara lokal)
| File | Keterangan |
|------|------------|
| `tools/setup_gcal_auth.py` | OAuth flow untuk dapat Google Calendar refresh token |
| `tools/setup_notion_db.py` | Buat/update schema Notion DB |
| `tools/update_db_ui.py` | Rename properti Notion dengan emoji |
| `tools/test_gcal.py` | Tes koneksi Google Calendar |
| `tools/verify_connections.py` | Tes semua koneksi API |

### Testing
| File | Keterangan |
|------|------------|
| `tests/conftest.py` | Fixtures & mocking semua external deps. |
| `tests/test_webhook.py` | Test untuk FastAPI webhook dan AI orchestration. |
| `tests/test_notion_tools.py` | Test untuk semua tool Notion (CRUD tasks, etc). |
| `tests/test_reports.py` | Test untuk logic peritungan report dan habit. |
| `tests/test_cron_jobs.py` | Test untuk eksekusi cron jobs (morning/evening slaps). |
| `pyproject.toml` | Pytest config. |

### Config
| File | Keterangan |
|------|------------|
| `.env` | Local env vars (tidak di-commit ke Git!) |
| `requirements.txt` | Python dependencies (local) |
| `gemini.md` | **File ini** — Project constitution |

---

## 🛠️ Available AI Tools (Gemini function-calling)

| Tool | Kapan digunakan |
|------|-----------------|
| `update_notion_task(task_name, status, summary)` | Update status SATU task spesifik (selesai/belum) |
| `mark_all_tasks(status, date_str)` | Centang/uncentang SEMUA task sekaligus |
| `get_daily_report(date_str)` | Laporan task hari ini (mana yang selesai/belum) |
| `create_notion_task(task_name, duration, date_str, start_time)` | Buat task baru di Notion untuk tanggal tertentu |
| `add_to_routine(task_name, duration)` | Tambah aktivitas ke rutinitas harian master |
| `remove_from_routine(task_name)` | Hapus aktivitas dari rutinitas harian master |
| `create_google_calendar_event(title, date_str, start_time, end_time, duration_minutes, description)` | Buat event Google Calendar |
| `list_google_calendars()` | Lihat daftar kalender yang tersedia |
| `save_memory(key, value)` | Simpan fakta ke AI memory (persisten di Notion) |
| `delete_memory(key)` | Hapus fakta dari AI memory |

---

## 🤖 Model AI & Fallback Chain

Logic AI dipusatkan di `tools/ai_agent.py` menggunakan fungsi `generate_ai_response()`. Fungsi ini menjamin konsistensi fallback chain baik untuk chat user maupun automated cron jobs.

Primary model: `gemini-3.1-flash-lite-preview`

Jika primary gagal, coba secara berurutan:
```python
FALLBACK_MODELS = [
    "gemini-2.5-pro-preview-05-06",   # paling pintar
    "gemini-3-flash-preview",
    "gemini-2.5-flash-preview-05-20",
]
```

---

## ⏰ Cron Schedule (Modal)

| Waktu WIB | UTC | Function | Aksi |
|-----------|-----|----------|------|
| 05:00 | 22:00 (hari sebelumnya) | `morning_slap()` | Buat task harian dari Master Routine + kirim pesan motivasi keras |
| 12:00 | 05:00 | `noon_slap()` | Progress check siang |
| 15:00 | 08:00 | `afternoon_slap()` | Progress check sore |
| 18:00 | 11:00 | `evening_slap()` | Laporan akhir hari |

---

## 🔐 Secrets di Modal (nama group: `my-notion-secrets`)

| Key | Keterangan |
|-----|------------|
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_DB_ID` | ID database Notion utama |
| `TELEGRAM_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Default chat ID (untuk pesan cron) |
| `GEMINI_API_KEY` | Google AI (Gemini) API key |
| `GCAL_CLIENT_ID` | Google OAuth client ID |
| `GCAL_CLIENT_SECRET` | Google OAuth client secret |
| `GCAL_REFRESH_TOKEN` | Google OAuth refresh token |
| `GCAL_CALENDAR_ID` | ID Google Calendar (default: `primary`) |

---

## 📋 Data Schemas

### 1. Telegram Webhook Input
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {"id": 8344404871, "first_name": "Rafis", "username": "rafis"},
    "chat": {"id": 8344404871, "type": "private"},
    "date": 1690000000,
    "text": "Tolong summarize ini...",
    "voice": {
      "file_id": "AwADBAADbXXXXXXXXXXX",
      "duration": 5
    }
  }
}
```

### 2. Notion Task Row (properties)
```json
{
  "parent": { "database_id": "23b945edf4a980c48980f9190ea8b0cb" },
  "properties": {
    "Name":           { "title":     [{ "text": { "content": "Belajar SE dari Harvard Online" } }] },
    "Date":           { "date":      { "start": "2026-04-30" } },
    "Time":           { "rich_text": [{ "text": { "content": "07:00 - 07:45" } }] },
    "Status":         { "checkbox":  true },
    "Notes / Summary":{ "rich_text": [{ "text": { "content": "Mempelajari struktur data dasar." } }] }
  }
}
```

### 3. Notion Special Pages (config tersimpan di DB yang sama)
| Nama Page | Fungsi |
|-----------|--------|
| `[CONFIG] MASTER ROUTINE` | List rutinitas harian, disimpan sebagai JSON di `Notes / Summary` |
| `[CONFIG] AI MEMORY` | Key-value memory AI, disimpan sebagai JSON di `Notes / Summary` |

### 4. Master Routine Format (JSON di Notion)
```json
[
  {"name": "Praktik AI Engineer", "duration": "2 Jam"},
  {"name": "Belajar SE dari Harvard Online", "duration": "45 Menit"},
  {"name": "Baca Buku tentang SE", "duration": "30 Menit"},
  {"name": "Manage & Membangun Bisnis Wedding", "duration": "1 Jam"},
  {"name": "Belajar Claude Academy", "duration": "45 Menit"},
  {"name": "Belajar Interview", "duration": "30 Menit"},
  {"name": "Belajar Bahasa Inggris", "duration": "15 Menit"}
]
```

---

## 🎭 Behavioral Rules (Tone & Personality)

- **Tone:** Seperti teman akrab, kasual, santai, ceplas-ceplos. Sesuaikan gaya bahasa dengan cara user nulis.
- **Reminders (05:00 & 18:00):** Pakai kalimat "tamparan" motivasi keras, contoh:
  - *"Katanya mau konsisten, mana buktinya?"*
  - *"Mau rebahan aja nih?"*
  - *"Bangun woi, mimpi lo gak bakal kecapai kalau lo cuma tiduran!"*
- **Konfirmasi sukses:** SELALU sertakan emoji ✅ kalau aksi di Notion berhasil.
- **Jangan bilang "berhasil" sebelum tool dipanggil:** Gemini tidak boleh claim sukses sebelum benar-benar execute tool-nya.
- **GCal link:** Jika buat Google Calendar event, SELALU tampilkan link event-nya ke user.
- **Voice note:** Jika ada input suara, transkripsikan dulu baru eksekusi instruksinya.

---

## 🏛️ Architectural Invariants (Jangan Dilanggar)

1. **3-Layer Separation:** Jangan mix logic antar layer. Webhook (Layer 1) tidak boleh langsung manggil Notion. Harus lewat AI agent (Layer 2) atau via background task ke tool (Layer 3).
2. **No `notion-client` di Modal container:** `main.py` pakai raw `requests` untuk Notion API. `notion-client` (Client class) hanya boleh dipakai di setup scripts lokal.
3. **Async safety di Modal:** Modal Dict operations dalam async handler HARUS pakai `.aio()` variant.
4. **Background tasks, bukan asyncio.create_task:** Gunakan FastAPI `BackgroundTasks` untuk processing, bukan `asyncio.create_task`. Lebih reliable di Modal serverless.
5. **Dedup wajib:** Setiap webhook request HARUS dicek via `_is_duplicate()` sebelum diproses, untuk cegah Telegram retry menyebabkan double-reply.
6. **Memory cache:** `get_memory_config()` punya cache 5 menit. Saat write (save/delete), selalu `skip_cache=True` dan invalidasi cache setelahnya.

---

## 🧪 Testing

```bash
# Jalankan semua test
python -m pytest tests/ -v

# Jalankan dengan HTML report
python -m pytest tests/ -v --html=test_report.html --self-contained-html
```

**Status test saat ini:** 18/18 PASSED ✅  
**Jalankan test sebelum setiap `modal deploy`**

---

## 🚀 CI/CD (GitHub Actions)

Project ini menggunakan GitHub Actions untuk testing otomatis dan deployment ke Modal.

| Workflow | Trigger | Aksi |
|----------|---------|------|
| `CI` | Push ke `main` & `feature/*`, PR ke `main` | Menjalankan `pytest` |
| `CD` | Push ke `main` | Deploy ke Modal (`modal deploy`) |

**GitHub Secrets yang diperlukan:**
- `MODAL_TOKEN_ID`: Diambil dari `modal token new` (dijalankan lokal)
- `MODAL_TOKEN_SECRET`: Diambil dari `modal token new`

---

## 🚀 Deployment

```powershell
# Windows — set encoding dulu
$env:PYTHONIOENCODING='utf-8'
modal deploy tools/main.py
```

```bash
# Set Telegram webhook (sekali saja)
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<MODAL_URL>/webhook"
```

---

## 📌 Development Rules

1. **Issue Logging:** Setiap kali ada bug/issue ditemukan dan diperbaiki, WAJIB update bagian "Known Issues & Fixes" di bawah.
2. **Git Push:** Setiap perubahan code/config yang valid, langsung commit dan push ke `awingmawe/task-scheduler`.
3. **Test dulu sebelum push:** Jalankan `pytest tests/` dan pastikan semua pass.
4. **Data-First:** Jangan mulai coding fitur baru sebelum shape payload-nya dikonfirmasi.
5. **Powershell syntax:** Di Windows, gunakan `;` bukan `&&` untuk chain commands di terminal.
6. **Git Branching & Sync:** Setiap kali mengerjakan issue di GitHub, WAJIB buat branch baru dari `main` dengan nama branch sesuai nama issue. Selalu jalankan `git fetch origin` sebelum melakukan `git pull`.

---

## 🐛 Known Issues & Fixes

### 1. AsyncUsageWarning: Blocking Modal interface in async context
- **Tanggal:** 2026-05-02
- **Gejala:** Warning `AsyncUsageWarning` di Modal log saat chat Telegram masuk.
- **Penyebab:** `dedup_store.get(key)` dan `dedup_store[key] = now` adalah blocking calls yang dipanggil di dalam async handler (`telegram_webhook`).
- **Solusi:** Ubah `_is_duplicate()` jadi `async def` dan pakai `await dedup_store.get.aio(key)` serta `await dedup_store.put.aio(key, now)`. Caller di webhook di-update jadi `await _is_duplicate(...)`.
- **Status:** ✅ **FIXED** — 2026-05-02.

### 2. `get_daily_report()` — checkbox lookup bisa return 0%
- **Tanggal:** 2026-05-02
- **Gejala:** Jika nama property Notion berubah atau tidak cocok, semua task dilaporkan belum selesai.
- **Penyebab:** Code lookup `props["Status"]["checkbox"]` — jika key `"Status"` tidak ada, default ke `False`.
- **Solusi:** Sudah ada guard `if "Status" in props else False`. Pastikan nama property di Notion DB tetap `"Status"`.
- **Status:** Mitigated.

### 3. `notion-client` dipakai di Modal container
- **Tanggal:** 2026-05-02
- **Gejala:** `from notion_client import Client` di-import di `main.py`.
- **Penyebab:** `Client` masih dipakai di `create_notion_task()`, `get_master_routine_config()`, `update_master_routine_config()`.
- **Solusi:** Refactor fungsi-fungsi ini ke raw `requests`, lalu hapus `notion-client` dari Modal image.
- **Status:** ✅ **FIXED** — 2026-05-02. Seluruh codebase telah direfactor menggunakan raw `requests`.

### 4. Hardcoded Notion token di `update_db_ui.py`
- **Tanggal:** 2026-05-02
- **Gejala:** Token Notion terekspos di source code.
- **Penyebab:** Default value di `os.environ.get()` berisi token asli.
- **Solusi:** Hapus hardcoded token, gunakan `os.environ.get("NOTION_TOKEN", "")`.
- **Status:** Fix diperlukan sebelum repo publik.

### 5. `Background processing error: 'id'` — KeyError saat buat AI MEMORY page
- **Tanggal:** 2026-05-02
- **Gejala:** Log Modal menampilkan `Background processing error: 'id'`.
- **Penyebab:** Saat page `[CONFIG] AI MEMORY` belum ada, code akses `create_resp["id"]` tanpa cek apakah request berhasil.
- **Solusi:** Tambahkan guard `if "id" not in create_resp` dan log body response error. Tambah full traceback logging di `_process_and_reply_sync`.
- **Status:** Teridentifikasi. Belum dipatch.

### 6. API Error 400: Databases with multiple data sources
- **Tanggal:** 2026-05-02
- **Gejala:** `validation_error` saat query database Notion.
- **Penyebab:** Header `Notion-Version: 2022-06-28` sudah outdated.
- **Solusi:** Update semua `Notion-Version` header ke `"2025-09-03"`.
- **Status:** ✅ **FIXED** — 2026-05-02.

### 11. `ModuleNotFoundError: No module named 'requests'` saat CI/CD (GitHub Actions)
- **Tanggal:** 2026-05-04
- **Gejala:** GitHub Action job `deploy` gagal dengan error `ModuleNotFoundError: No module named 'requests'`.
- **Penyebab:** Saat menjalankan `modal deploy tools/main.py`, CLI Modal mencoba meng-import script `main.py` di environment runner (GitHub Actions) untuk memvalidasi/mencari objek app. Karena job `deploy` di `cd.yml` hanya menginstall `modal` dan tidak menginstall dependensi project (`requests`, dll), import gagal.
- **Solusi:** Update `.github/workflows/cd.yml` untuk menginstall `requirements.txt` di dalam job `deploy` sebelum menjalankan perintah `modal deploy`.
- **Status:** ✅ **FIXED** — 2026-05-04.

### 12. `Token missing. Could not authenticate client.` saat CI/CD
- **Tanggal:** 2026-05-04
- **Gejala:** GitHub Action job `deploy` gagal saat menjalankan `modal deploy` dengan pesan error "Token missing" atau "Token validation failed".
- **Penyebab:** Environment runner GitHub Actions tidak memiliki kredensial Modal (token ID & secret) yang valid atau format pengisian di GitHub Secrets salah (termasuk tanda petik/prefix).
- **Solusi:** Ambil token dari `~/.modal.toml` (lokal) atau jalankan `modal token new`. Masukkan ke GitHub Repository Secrets (`MODAL_TOKEN_ID` & `MODAL_TOKEN_SECRET`) **TANPA tanda petik** dan **TANPA prefix** `token_id =`.
- **Status:** ✅ **FIXED** — 2026-05-04.

### 13. `FutureWarning: All support for the google.generativeai package has ended`
- **Tanggal:** 2026-05-04
- **Gejala:** Muncul warning saat deploy/menjalankan bot bahwa library `google-generativeai` sudah deprecated.
- **Penyebab:** Google telah merilis SDK baru `google-genai` dan menghentikan support untuk SDK lama.
- **Solusi:** Migrasi codebase dari `import google.generativeai` ke library baru `google-genai`.
- **Status:** ✅ **FIXED** — 2026-05-04. Codebase telah sepenuhnya dimigrasi ke SDK `google-genai`.

### 14. `API Error 400: Bad Request` saat query database Notion via Cron
- **Tanggal:** 2026-05-04
- **Gejala:** Cron jobs (morning_slap, etc.) gagal dengan error 400 saat memanggil `get_daily_report()`.
- **Penyebab:** Kemungkinan payload filter query tidak sesuai dengan schema Notion DB atau `Notion-Version` header tidak konsisten.
- **Solusi:** Sedang diinvestigasi. Lacak di [GitHub Issue #11](https://github.com/awingmawe/task-scheduler/issues/11).
- **Status:** 🔴 **OPEN**

### 7. `create_notion_task()` — `Client()` instantiation tidak di-wrap try/except
- **Tanggal:** 2026-05-02
- **Gejala:** Jika `notion_client.Client()` throw exception (misal auth error), exception **tidak tertangkap**.
- **Penyebab:** `notion = Client(auth=...)` berada di LUAR blok `try:`.
- **Solusi:** Refactor `create_notion_task()` ke raw `requests.post` (tidak perlu `Client` sama sekali).
- **Status:** ✅ **FIXED** — 2026-05-02. `create_notion_task()` dan fungsi lainnya sekarang pakai raw requests.

### 8. Timezone bug — task dibuat dengan date UTC bukan WIB
- **Tanggal:** 2026-05-02
- **Gejala:** `morning_slap` berjalan jam 22:00 UTC (= 05:00 WIB). Task dibuat dengan date UTC (misal `2026-05-01`), tapi user query setelah midnight UTC (jam 07:00+ WIB = setelah 00:00 UTC) mendapat date `2026-05-02` → tidak ketemu task.
- **Penyebab:** Semua `datetime.datetime.now()` di Modal return UTC, bukan WIB.
- **Solusi:** Buat helper `_today_wib()` yang pakai `datetime.timezone(timedelta(hours=7))`. Replace semua `datetime.datetime.now().strftime()` dengan `_today_wib()` di: `update_notion_task`, `mark_all_tasks`, `create_notion_task`, `get_daily_report`, `delete_notion_task`.
- **Status:** ✅ **FIXED** — 2026-05-02.

### 9. `morning_slap()` — task duplikat jika cron dijalankan >1x sehari
- **Tanggal:** 2026-05-02
- **Gejala:** Jika `morning_slap` dijalankan manual atau retry, task dari rutinitas dibuat dobel di Notion.
- **Penyebab:** Tidak ada cek existing task sebelum `create_notion_task()` dipanggil.
- **Solusi:** Tambah helper `_task_exists_for_date(task_name, date_str)` yang query Notion dengan filter `Name equals` + `Date equals`. Di `morning_slap`, skip task yang sudah ada dan log `[SKIP DEDUP]`.
- **Status:** ✅ **FIXED** — 2026-05-02.

### 10. Monolithic `main.py` and `test_main.py` maintenance burden
- **Tanggal:** 2026-05-02
- **Gejala:** Codebase sulit dimaintain karena semua logic ada di satu file, dan `test_main.py` menjadi sangat besar (500+ baris) serta mudah broken saat ada perubahan struktur.
- **Penyebab:** Desain awal yang menggabungkan triggers, tools, dan AI agent dalam satu file.
- **Solusi:** Refactor codebase menjadi modular (`ai_agent.py`, `notion_tools.py`, `cron_jobs.py`, dll) dan split `test_main.py` menjadi specialized test files sesuai modulnya. Centralized AI fallback logic dalam `generate_ai_response`.
- **Status:** ✅ **FIXED** — 2026-05-02.
### 15. `Task not found` — Bug timing di malam hari/dini hari
- **Tanggal:** 2026-05-04
- **Gejala:** AI melaporkan "task tidak ditemukan" saat user mencoba update task di malam hari (sebelum tidur) atau dini hari.
- **Penyebab:** (1) Context `today` di AI agent stale karena container reuse. (2) Database query hanya mencari tanggal hari kalender saat ini, padahal secara logis user masih mengerjakan task "kemarin".
- **Solusi:** (1) Pindahkan kalkulasi `today` ke dalam fungsi `process_with_ai` agar selalu fresh. (2) Implementasi **Grace Period** hingga jam 04:00 WIB di `notion_tools.py` dan `reports.py`; jika task hari ini tidak ketemu, otomatis cari task kemarin.
- **Status:** ✅ **FIXED** — 2026-05-04.
