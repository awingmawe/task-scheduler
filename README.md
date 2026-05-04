# 🚀 Notion AI Task Scheduler — V2 (Daily Rows)

Asisten pribadi cerdas berbasis AI yang mengelola jadwal harian lo di Notion, Google Calendar, dan Telegram. Bot ini bukan cuma sekadar *logger*, tapi "manajer" harian yang bakal bikinin list tugas tiap pagi dan nagih progresnya tiap sore!

## ✨ Fitur Utama

- **🧠 Advanced AI Agent**: Menggunakan **Gemini 3.1 Flash Lite** dengan sistem *function-calling* yang presisi. Bisa ngerti perintah bahasa manusia (VN atau teks).
- **🔄 Auto-Generation (05:00 WIB)**: Tiap pagi otomatis narik daftar rutinitas dari **Master Routine** dan bikinin baris tugas individu di Notion.
- **📅 Google Calendar Sync**: Bikin event kalender otomatis lewat chat. Gak perlu buka app GCal lagi.
- **⚡ Individual Task System**: Satu aktivitas, satu baris di Notion. Status tinggal centang, lebih rapi dan gampang di-filter.
- **🗣️ Voice Note Transcription**: Males ngetik? Kirim VN, AI transkripsi instruksinya, langsung eksekusi tool Notion/GCal.
- **💥 Motivational Slaps**: Pengingat berkala (Pagi, Siang, Sore, Malam) dengan gaya bahasa "tamparan" motivasi keras khas pertemanan akrab.
- **📝 AI Memory (Persistent)**: Bot punya memori buat simpan fakta tentang lo (misal: "Gue lagi diet rendah gula") yang disimpen aman di Notion.

## 🛠️ Tech Stack

- **Framework**: [Modal](https://modal.com/) (Serverless Cloud & Cron Jobs)
- **Engine**: [FastAPI](https://fastapi.tiangolo.com/) & [Python 3.12+](https://www.python.org/)
- **LLM**: Google Gemini API (`gemini-3.1-flash-lite-preview`)
- **Database**: Notion API (Direct Integration)
- **Messaging**: Telegram Bot API

## 📂 Struktur Project (Modular)

```
task-scheduler/
├── tools/
│   ├── main.py            # Entry point (Webhook & Modal App)
│   ├── ai_agent.py        # Logika otak AI & Fallback Chain
│   ├── notion_tools.py    # CRUD Operasi ke Notion
│   ├── gcal_tools.py      # Integrasi Google Calendar
│   ├── memory_tools.py    # Sistem Memori AI (Key-Value)
│   ├── reports.py         # Generator laporan harian & progres
│   ├── telegram_tools.py  # Utility pengiriman pesan Telegram
│   ├── cron_jobs.py       # Logic scheduled tasks (Slaps)
│   └── setup_notion_db.py # Script inisialisasi schema DB
├── tests/                 # Unit testing suite (Pytest)
└── gemini.md              # Project Constitution (SOP AI)
```

## 🚀 Setup & Deployment

1.  **Inisialisasi Database**:
    Jalankan script setup buat bikin database Notion yang sesuai schema:
    ```powershell
    python tools/setup_notion_db.py
    ```

2.  **Setup Secrets di Modal**:
    Pastikan lo udah punya Modal account, lalu buat secret group `my-notion-secrets`:
    ```bash
    modal secret create my-notion-secrets \
      NOTION_TOKEN=... \
      NOTION_DB_ID=... \
      TELEGRAM_TOKEN=... \
      GEMINI_API_KEY=...
    ```

3.  **Deploy**:
    ```powershell
    modal deploy tools/main.py
    ```

---
*Dibuat dengan ❤️ untuk lo yang pengen mimpi lo tercapai, bukan cuma jadi rencana.*
