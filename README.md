# 🚀 Notion AI Task Scheduler

Asisten pribadi cerdas berbasis AI yang mengelola jadwal harian lo di Notion, Google Calendar, dan Telegram. Gak cuma nyatet, bot ini juga bisa ngomel kalo lo males! 😂

## ✨ Fitur Utama

- **🧠 AI-Powered Task Management**: Pake Gemini (2.5-Flash & Fallbacks) buat ngerti bahasa santai lo.
- **📅 Google Calendar Sync**: Otomatis bikin event di kalender kalo lo sebut jam spesifik.
- **🔄 Auto-Daily Routine**: Jam 5 pagi otomatis bikinin target harian lo di Notion biar gak lupa.
- **🗣️ Voice Note Support**: Males ngetik? Kirim VN aja, AI bakal transkripsi dan jalanin perintah lo.
- **⚡ Parallel Execution**: Update banyak task di Notion sekaligus dalam hitungan detik.
- **📝 AI Memory System**: Bot bisa "ingat" fakta atau preferensi lo (disimpen langsung di Notion).
- **💥 Motivational Reminders ("Slap")**: Notifikasi berkala (Pagi, Siang, Sore, Malam) buat mastiin lo gak cuma rebahan.

## 🛠️ Tech Stack

- **Framework**: [Modal](https://modal.com/) (Serverless & Cron)
- **API**: [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: [Notion API](https://developers.notion.com/)
- **LLM**: [Google Gemini API](https://aistudio.google.com/)
- **Integration**: Telegram Bot API & Google Calendar API

## 🚀 Cara Install

1.  **Clone Repo**:
    ```bash
    git clone <url-repo-lo>
    cd task-scheduler
    ```

2.  **Setup Environment**:
    Buat file `.env` (jangan di-push!) dan isi:
    ```env
    NOTION_TOKEN=...
    NOTION_DB_ID=...
    TELEGRAM_TOKEN=...
    GEMINI_API_KEY=...
    GCAL_CLIENT_ID=...
    GCAL_CLIENT_SECRET=...
    GCAL_REFRESH_TOKEN=...
    ```

3.  **Deploy ke Modal**:
    ```bash
    modal deploy tools/main.py
    ```

## 📂 Struktur Folder

- `tools/main.py`: Core logic (AI Agent, Tools, Webhook, Cron).
- `tools/setup_gcal_auth.py`: Script buat dapetin refresh token Google.
- `tools/setup_notion_db.py`: Inisialisasi database Notion.
- `architecture/`: Dokumentasi sistem & SOP.

---
*Dibuat dengan ❤️ buat lo yang pengen produktif tapi butuh ditampol biar gerak.*
