import os
import requests
import datetime
from config import _notion_headers, _today_wib

def _format_report_section(title: str, done: list, pending: list, total_days: int = None) -> str:
    """Helper: format blok report rapih dengan % completion."""
    total = len(done) + len(pending)
    pct = int(len(done) / total * 100) if total > 0 else 0
    bar_filled = int(pct / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)
    lines = [f"{title}", f"Progress: [{bar}] {pct}% ({len(done)}/{total})"]
    if pending:
        lines.append("Belum selesai:")
        for t in pending:
            lines.append(f"  - {t}")
    if done:
        lines.append("Selesai:")
        for t in done:
            lines.append(f"  - {t}")
    return "\n".join(lines)

def get_daily_report(date_str: str = "") -> str:
    """Gets a report of all tasks scheduled for a specific date, highlighting uncompleted ones."""
    db_id = os.environ["NOTION_DB_ID"]
    
    # Timezone WIB
    wib_tz = datetime.timezone(datetime.timedelta(hours=7))
    now_wib = datetime.datetime.now(wib_tz)

    if not date_str:
        date_str = now_wib.strftime("%Y-%m-%d")
        is_auto_date = True
    else:
        is_auto_date = False
        
    try:
        def _fetch(d_str):
            url = f"https://api.notion.com/v1/databases/{db_id}/query"
            payload = {
                "filter": {
                    "property": "Date",
                    "date": {"equals": d_str}
                }
            }
            return requests.post(url, headers=_notion_headers(), json=payload)

        response = _fetch(date_str)
        if response.status_code != 200:
            print(f"[REPORT ERROR] Notion API {response.status_code}: {response.text}")
            return f"❌ Gagal mengambil report Notion ({response.status_code}): {response.text}"
            
        resp_json = response.json()
        results = resp_json.get("results", [])

        # Grace Period: Jika tgl hari ini kosong & masih dini hari, coba kemarin
        if not results and is_auto_date and now_wib.hour < 4:
            yesterday_str = (now_wib - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            print(f"[REPORT GRACE] No tasks for {date_str}, checking {yesterday_str}...")
            response = _fetch(yesterday_str)
            if response.status_code == 200:
                results = response.json().get("results", [])
                if results:
                    date_str = yesterday_str
        
        print(f"[REPORT DEBUG] Found {len(results)} pages for {date_str}")
        
        if not results:
            return f"Tidak ada task yang dijadwalkan untuk tanggal {date_str}."
            
        completed = []
        pending = []
        reflection_from_db = ""
        
        for page in results:
            props = page["properties"]
            name_list = props["Name"]["title"]
            name = name_list[0]["text"]["content"] if name_list else "Untitled"
            
            # Special Row Handling
            if "[CONFIG]" in name:
                continue
            if "[REPORT]" in name:
                refl_list = props.get("🤖 Refleksi AI", {}).get("rich_text", [])
                if refl_list:
                    reflection_from_db = refl_list[0]["text"]["content"]
                continue

            status = props.get("Status", {}).get("checkbox", False)
            streak = props.get("🔥 Streak", {}).get("number", 0)
            summary_list = props.get("Notes / Summary", {}).get("rich_text", [])
            summary = summary_list[0]["text"]["content"] if summary_list else ""
            
            streak_str = f" 🔥{int(streak)}" if streak else ""
            display_name = f"{name}{streak_str}"
            
            if status:
                completed.append((display_name, summary))
            else:
                pending.append((display_name, summary))
                
        report_lines = [
            f"📊 DAILY REPORT \u2014 {date_str}",
            f"Progress: {len(completed)}/{len(completed)+len(pending)} task selesai",
            ""
        ]
        
        if reflection_from_db:
            report_lines.append("\u2728 REFLEKSI AI (Notion):")
            report_lines.append(reflection_from_db)
            report_lines.append("")
        if pending:
            report_lines.append(f"❌ Belum selesai ({len(pending)}):")
            for name, summary in pending:
                report_lines.append(f"  - {name}")
                if summary:
                    report_lines.append(f"    📝 {summary}")
        if completed:
            report_lines.append(f"\n✅ Selesai ({len(completed)}):")
            for name, summary in completed:
                report_lines.append(f"  - {name}")
                if summary:
                    report_lines.append(f"    📝 {summary}")
        return "\n".join(report_lines)
    except Exception as e:
        return f"Gagal mengambil report: {str(e)}"

def get_weekly_report(week_offset: int = 0) -> str:
    """Buat laporan mingguan: berapa task selesai per hari, habit mana paling sering dilewat."""
    db_id = os.environ["NOTION_DB_ID"]
    today = datetime.datetime.now().date()
    # Hitung Senin dan Minggu dari minggu target
    days_since_monday = today.weekday()
    monday = today - datetime.timedelta(days=days_since_monday) + datetime.timedelta(weeks=week_offset)
    sunday = monday + datetime.timedelta(days=6)
    try:
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"on_or_after": str(monday)}},
                    {"property": "Date", "date": {"on_or_before": str(sunday)}},
                    {"property": "Name", "title": {"does_not_contain": "[CONFIG]"}}
                ]
            },
            "sorts": [{"property": "Date", "direction": "ascending"}]
        }
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        results = resp.get("results", [])
        if not results:
            return f"Tidak ada task minggu {monday} s/d {sunday}."

        by_date: dict = {}
        habit_stats: dict = {}
        for page in results:
            props = page["properties"]
            name_list = props["Name"]["title"]
            name = name_list[0]["text"]["content"] if name_list else "Untitled"
            date_val = props.get("Date", {}).get("date", {})
            date_str = date_val.get("start", "") if date_val else ""
            status = props.get("Status", {}).get("checkbox", False)
            if not date_str:
                continue
            by_date.setdefault(date_str, {"done": [], "pending": []})
            by_date[date_str]["done" if status else "pending"].append(name)
            habit_stats.setdefault(name, {"done": 0, "total": 0})
            habit_stats[name]["total"] += 1
            if status:
                habit_stats[name]["done"] += 1

        total_done = sum(len(v["done"]) for v in by_date.values())
        total_all = sum(len(v["done"]) + len(v["pending"]) for v in by_date.values())
        pct = int(total_done / total_all * 100) if total_all > 0 else 0

        lines = [
            f"📊 LAPORAN MINGGUAN",
            f"📅 {monday.strftime('%d %b')} — {sunday.strftime('%d %b %Y')}",
            f"Overall: {total_done}/{total_all} task selesai ({pct}%)",
            ""
        ]

        DAY_NAMES = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
        for d in sorted(by_date.keys()):
            dt = datetime.date.fromisoformat(d)
            day_name = DAY_NAMES[dt.weekday()]
            done_n = len(by_date[d]["done"])
            total_n = done_n + len(by_date[d]["pending"])
            status_emoji = "✅" if done_n == total_n else ("⚠️" if done_n > 0 else "❌")
            lines.append(f"{status_emoji} {day_name} {dt.strftime('%d/%m')}: {done_n}/{total_n} task selesai")

        missed = [(k, v) for k, v in habit_stats.items() if v["done"] < v["total"]]
        missed.sort(key=lambda x: x[1]["done"] / max(x[1]["total"], 1))
        if missed:
            lines.append("")
            lines.append("🔴 Habit yang sering dilewat minggu ini:")
            for name, stat in missed[:3]:
                h_pct = int(stat["done"] / stat["total"] * 100)
                lines.append(f"  - {name}: {stat['done']}/{stat['total']} hari ({h_pct}%)")

        return "\n".join(lines)
    except Exception as e:
        return f"Gagal buat weekly report: {str(e)}"

def get_monthly_report(month_offset: int = 0) -> str:
    """Buat laporan bulanan: konsistensi per habit selama sebulan."""
    db_id = os.environ["NOTION_DB_ID"]
    today = datetime.datetime.now().date()
    target = today.replace(day=1) + datetime.timedelta(days=32 * month_offset)
    first_day = target.replace(day=1)
    next_month = (first_day.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    last_day = next_month - datetime.timedelta(days=1)
    try:
        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        payload = {
            "filter": {
                "and": [
                    {"property": "Date", "date": {"on_or_after": str(first_day)}},
                    {"property": "Date", "date": {"on_or_before": str(last_day)}},
                    {"property": "Name", "title": {"does_not_contain": "[CONFIG]"}}
                ]
            },
            "sorts": [{"property": "Date", "direction": "ascending"}]
        }
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        results = resp.get("results", [])
        if not results:
            return f"Tidak ada task untuk bulan {first_day.strftime('%B %Y')}."

        habit_stats: dict = {}
        dates_with_tasks: set = set()
        for page in results:
            props = page["properties"]
            name_list = props["Name"]["title"]
            name = name_list[0]["text"]["content"] if name_list else "Untitled"
            date_val = props.get("Date", {}).get("date", {})
            date_str = date_val.get("start", "") if date_val else ""
            status = props.get("Status", {}).get("checkbox", False)
            if not date_str:
                continue
            dates_with_tasks.add(date_str)
            habit_stats.setdefault(name, {"done": 0, "total": 0})
            habit_stats[name]["total"] += 1
            if status:
                habit_stats[name]["done"] += 1

        total_days = len(dates_with_tasks)
        total_done = sum(v["done"] for v in habit_stats.values())
        total_all = sum(v["total"] for v in habit_stats.values())
        pct = int(total_done / total_all * 100) if total_all > 0 else 0

        lines = [
            f"📊 LAPORAN BULANAN — {first_day.strftime('%B %Y').upper()}",
            f"📅 Total hari aktif: {total_days} hari",
            f"Overall: {total_done}/{total_all} task selesai ({pct}%)",
            ""
        ]

        lines.append("Konsistensi per habit:")
        for name, stat in sorted(habit_stats.items(), key=lambda x: -x[1]["done"] / max(x[1]["total"], 1)):
            h_pct = int(stat["done"] / stat["total"] * 100) if stat["total"] > 0 else 0
            bar_filled = int(h_pct / 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            emoji = "🟢" if h_pct >= 80 else ("🟡" if h_pct >= 50 else "🔴")
            lines.append(f"{emoji} {name}")
            lines.append(f"   [{bar}] {h_pct}% ({stat['done']}/{stat['total']} hari)")

        return "\n".join(lines)
    except Exception as e:
        return f"Gagal buat monthly report: {str(e)}"
