# Project Constitution

## Data Schemas

### 1. Telegram Webhook Input (from Telegram API)
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

### 2. LLM Tool Calling Payload (Output from Gemini)
```json
{
  "action": "update_task",
  "task_name": "Belajar SE dari Harvard Online",
  "status": true,
  "summary": "Mempelajari struktur data dasar dan algoritma sorting."
}
```

### 3. Notion API Payload (Output to Notion)
```json
{
  "parent": { "database_id": "23b945edf4a980c48980f9190ea8b0cb" },
  "properties": {
    "Name": { "title": [{ "text": { "content": "Belajar SE dari Harvard Online" } }] },
    "Date": { "date": { "start": "2026-04-30" } },
    "Time": { "rich_text": [{ "text": { "content": "07:00 - 07:45" } }] },
    "Status": { "checkbox": true },
    "Notes / Summary": { "rich_text": [{ "text": { "content": "Mempelajari struktur data dasar." } }] }
  }
}
```

## Behavioral Rules
- **Tone:** Seperti teman akrab, menggunakan bahasa yang menyesuaikan dengan gaya chat pengguna (kasual, santai, ceplas-ceplos).
- **Reminders (05:00 & 18:00):** Gunakan kalimat "tamparan" yang memotivasi secara keras (contoh: "Katanya mau konsisten", "Mau rebahan aja nih?", "Bangun woi, mimpi lo gak bakal kecapai kalau lo cuma tiduran!").
- **Delivery:** Selalu sertakan emoji ✅ jika aksi di Notion berhasil dilakukan.
- **Model Fallback:** Utamakan model `gemini-2.5-pro`. Jika limit/habis, fallback ke model yang tersedia (misal: `gemini-1.5-pro` atau `gemini-1.5-flash`).

## Architectural Invariants
- 3-Layer Architecture (Architecture, Navigation, Tools)
- Data-First Rule: Coding only begins once the "Payload" shape is confirmed.
- Self-Annealing Loop
