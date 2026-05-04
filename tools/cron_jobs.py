import os
import json
import requests
from config import _notion_headers, _today_wib
from telegram_tools import send_telegram_message
from notion_tools import (
    get_master_routine_config,
    _task_exists_for_date,
    create_notion_task
)
from reports import get_daily_report, get_weekly_report
from ai_agent import generate_ai_response

def execute_morning_slap():
    """Logic for morning_slap cron job."""
    # 1. Ambil list dari Master Routine di Notion
    _, routine_list = get_master_routine_config()
    today = _today_wib()

    # 2. Buat task — skip jika sudah ada (prevent duplikat)
    created, skipped = 0, 0
    for task in routine_list:
        if _task_exists_for_date(task["name"], today):
            print(f"[SKIP DEDUP] Task '{task['name']}' sudah ada untuk {today}")
            skipped += 1
            continue
        create_notion_task(task["name"], duration=task.get("duration", ""), date_str=today)
        created += 1

    # 3. Send wake up message
    skip_note = f" ({skipped} task dilewati karena sudah ada)" if skipped else ""
    msg = (
        "Woi bangun! Pagi ini ada target penting yang udah disiapin.\n"
        "Jangan rebahan aja, mimpi lo gak bakal kecapai kalau cuma tiduran! 👊✅\n\n"
        f"Aku udah otomatis buatin {created} target aktivitas harianmu di Notion ya{skip_note}. Langsung gass kerjain!"
    )
    send_telegram_message(msg)

def execute_noon_slap():
    """Logic for noon_slap cron job."""
    report = get_daily_report()
    msg = (
        "Matahari udah di atas kepala nih! 🌞 Jangan kelamaan istirahat, masih banyak utang target!\n\n"
        f"{report}"
    )
    send_telegram_message(msg)

def execute_afternoon_slap():
    """Logic for afternoon_slap cron job."""
    report = get_daily_report()
    msg = (
        "Udah jam 3 sore woi! Bentar lagi hari kelar. Yakin target hari ini udah kelar semua?\n\n"
        f"{report}"
    )
    send_telegram_message(msg)

def execute_evening_slap():
    """Logic for evening_slap cron job."""
    report = get_daily_report()
    
    # Generate AI Reflection using central helper (includes fallbacks)
    prompt = (
        "Kamu adalah asisten asik yang ceplas-ceplos. Berikan refleksi singkat (1-2 paragraf) "
        "berdasarkan laporan task user hari ini. Jika banyak bolong, kasih tamparan motivasi. "
        "Jika sukses, kasih pujian tapi ingatkan untuk tidak jemawa. "
        f"Data hari ini:\n{report}"
    )
    reflection = generate_ai_response(prompt)

    # Save reflection to Notion (Dedicated [REPORT] row)
    try:
        today = _today_wib()
        db_id = os.environ["NOTION_DB_ID"]
        # Cek apakah sudah ada [REPORT] untuk hari ini
        query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
        query_payload = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"equals": today}},
                    {"property": "Name", "title": {"equals": f"[REPORT] {today}"}}
                ]
            }
        }
        q_resp = requests.post(query_url, headers=_notion_headers(), json=query_payload).json()
        
        report_props = {
            "Name": {"title": [{"text": {"content": f"[REPORT] {today}"}}]},
            "Date": {"date": {"start": today}},
            "🤖 Refleksi AI": {"rich_text": [{"text": {"content": reflection}}]}
        }
        
        if q_resp.get("results"):
            # Update existing
            page_id = q_resp["results"][0]["id"]
            requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=_notion_headers(), json={"properties": report_props})
        else:
            # Create new
            requests.post("https://api.notion.com/v1/pages", headers=_notion_headers(), json={"parent": {"database_id": db_id}, "properties": report_props})
    except Exception as ne:
        print(f"Error saving reflection to Notion: {ne}")

    msg = (
        "Woi udah jam 6 sore nih! Waktunya bangun bisnis Wedding dan lanjut belajar. Jangan males-malesan! \U0001f44a\u2705\n\n"
        "Nih liat rapor harianmu:\n"
        f"{report}\n\n"
        "📝 REFLEKSI HARI INI:\n"
        f"{reflection}"
    )
    send_telegram_message(msg)

def execute_weekly_report_slap():
    """Logic for weekly_report_slap cron job."""
    report = get_weekly_report(week_offset=0)
    msg = (
        "Nih recap minggu ini, jujur aja liat sendiri ya udah konsisten apa belum!\n\n"
        f"{report}\n\n"
        "Minggu depan harus lebih baik! Kalau ada yang sering dilewat, fix rutinitas lo sekarang!"
    )
    send_telegram_message(msg)
