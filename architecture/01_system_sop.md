# SOP: Notion AI Scheduler (Modal + Telegram)

## 1. Goals
Menyediakan asisten Telegram 24/7 (via Modal Serverless) yang mampu mencatat tugas, memperbarui status, dan mengingatkan jadwal secara proaktif berdasarkan perintah teks/suara dan *cron schedule*.

## 2. Inputs
- **Webhook Input:** JSON payload dari Telegram (`update_id`, `message.text`, `message.voice`).
- **Cron Input:** Trigger waktu dari infrastruktur Modal (05:00 WIB dan 18:00 WIB).

## 3. Tool Logic & Workflows

### A. Telegram Webhook Handler (`POST /webhook`)
1. Autentikasi asal request (opsional via Telegram Secret Token).
2. Ekstrak teks atau unduh *file* audio dari pesan.
3. Kirim ke Gemini 2.5 Pro menggunakan mode `Function Calling`.
4. Gemini mem-parsing perintah dan mengeksekusi alat (Tools) ke Notion.
5. Kirim balasan ke pengguna via API `sendMessage` Telegram (selalu sertakan ✅ jika sukses).

### B. Gemini Function Calls (Tools)
1. `add_new_task(name, time, date)` -> Menambahkan _row_ baru ke Notion DB.
2. `update_task_status(name, status, summary)` -> Mencari _row_ hari ini yang cocok dengan nama, mencentang status, dan mengisi _Notes/Summary_.

### C. Proactive Reminder (Modal Cron)
1. Aktif pada jam `05:00` dan `18:00`.
2. Menjalankan skrip Python yang langsung menembak API `sendMessage` Telegram.
3. Berisi kalimat tamparan (e.g. "Katanya mau konsisten bangun pagi!").

## 4. Edge Cases & Error Handling
- **API Limit:** Jika Gemini 2.5 Pro gagal, tangkap `Exception` dan coba *fallback* ringan atau kirim pesan *"Maaf, otak AI lagi penuh, coba sebentar lagi."*
- **Tugas Tidak Ditemukan:** Jika pengguna berkata "Centang tugas masak", padahal di tabel tidak ada tugas masak hari ini, Gemini harus menolak secara sopan.
- **Audio File Terlalu Besar:** Telegram membatasi bot mengunduh file > 20MB. Beri peringatan jika VN terlalu panjang.

> **Golden Rule:** Jika logika aplikasi (`tools/main.py`) akan diubah, ubah dokumen SOP ini terlebih dahulu.
