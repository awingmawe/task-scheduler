import os
import google.generativeai as genai
from memory_tools import get_memory_config, save_memory, delete_memory
from notion_tools import (
    update_notion_task,
    mark_all_tasks,
    create_notion_task,
    delete_notion_task,
    add_to_routine,
    remove_from_routine
)
from gcal_tools import create_google_calendar_event, list_google_calendars
from telegram_tools import send_telegram_message
from reports import get_daily_report, get_weekly_report, get_monthly_report

def generate_ai_response(
    contents: list | str, 
    system_instruction: str = None, 
    tools: list = None
) -> str:
    """Helper to generate AI response with primary model and fallback chain."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    
    if isinstance(contents, str):
        contents = [contents]

    # Primary model
    try:
        model = genai.GenerativeModel(
            'gemini-3.1-flash-lite-preview',
            tools=tools,
            system_instruction=system_instruction
        )
        chat = model.start_chat(enable_automatic_function_calling=True if tools else False)
        response = chat.send_message(contents)
        return response.text
    except Exception as e:
        print(f"Primary model (gemini-3.1-flash-lite-preview) error: {e}")

    # FALLBACK CHAIN
    FALLBACK_MODELS = [
        "gemini-2.5-pro-preview-05-06",
        "gemini-3-flash-preview",
        "gemini-2.5-flash-preview-05-20",
    ]

    for fallback_id in FALLBACK_MODELS:
        try:
            print(f"Trying fallback model: {fallback_id}")
            fallback_model = genai.GenerativeModel(
                fallback_id,
                tools=tools,
                system_instruction=system_instruction
            )
            fallback_chat = fallback_model.start_chat(enable_automatic_function_calling=True if tools else False)
            fallback_response = fallback_model.generate_content(contents) if not tools else fallback_chat.send_message(contents)
            return fallback_response.text
        except Exception as fe:
            print(f"Fallback model {fallback_id} also failed: {fe}")
            continue

    return "Waduh, semua model AI lagi bermasalah nih! Coba lagi sebentar ya 🙏"

def process_with_ai(user_input: str, audio_data: dict = None) -> str:
    # Load AI memory dari Notion untuk dijadikan konteks persisten
    _, memory = get_memory_config()
    memory_context = ""
    if memory:
        memory_lines = "\n".join([f"- {k}: {v}" for k, v in memory.items()])
        memory_context = f"\n\n[MEMORI TENTANG USER]\n{memory_lines}\n"

    system_instruction = (
        "Kamu adalah asisten/teman akrab yang santai dan ceplas-ceplos. "
        "Tugasmu membantu mengelola jadwal dan tugas di Notion.\n"
        "ATURAN PALING PENTING: Jangan pernah bilang 'berhasil' sebelum BENAR-BENAR memanggil tool-nya!\n"
        "Gunakan 'create_notion_task' untuk buat task di tanggal TERTENTU (hari ini/besok/tanggal spesifik).\n"
        "Gunakan 'delete_notion_task' jika user minta HAPUS task tertentu.\n"
        "Gunakan 'add_to_routine' jika user minta tambah aktivitas ke rutinitas HARIAN.\n"
        "Gunakan 'remove_from_routine' jika user minta hapus dari rutinitas harian.\n"
        "Gunakan 'update_notion_task' untuk update status SATU task. "
        "PENTING: jika user kirim summary/resume aktivitas (via teks atau voice note), "
        "ekstrak nama task-nya dan simpan teks summary-nya di parameter 'summary'. "
        "Tandai status=True jika user menyatakan sudah selesai.\n"
        "Gunakan 'mark_all_tasks' jika user bilang 'semua selesai', 'tandai semua done', dsb.\n"
        "Gunakan 'get_daily_report' untuk laporan task hari ini. Report sudah include summary per task.\n"
        "Gunakan 'get_weekly_report' jika user tanya progress/recap minggu ini atau minggu lalu.\n"
        "Gunakan 'get_monthly_report' jika user tanya recap/laporan bulan ini atau bulan lalu.\n"
        "Gunakan 'create_google_calendar_event' untuk buat event dengan JAM SPESIFIK di Google Calendar. "
        "SELALU tampilkan link eventnya setelah berhasil.\n"
        "Gunakan 'list_google_calendars' jika user bingung kenapa jadwal tidak muncul.\n"
        "Jika user sebut JAM AKHIR (contoh: 'sampai jam 17'), WAJIB isi end_time (format HH:MM).\n"
        "Gunakan 'save_memory' jika user minta INGAT sesuatu tentang dirinya.\n"
        "Gunakan 'delete_memory' jika user minta LUPA/HAPUS dari ingatan.\n"
        "Jika ada voice note, transkripsikan dulu baru jalankan instruksinya.\n"
        "Jawab singkat, asik, pakai emoji, jangan kaku."
        f"{memory_context}"
    )

    tools_list = [
        update_notion_task, mark_all_tasks, create_notion_task, delete_notion_task,
        create_google_calendar_event, list_google_calendars,
        get_daily_report, get_weekly_report, get_monthly_report,
        add_to_routine, remove_from_routine,
        save_memory, delete_memory
    ]

    contents = []
    if audio_data:
        contents.append(audio_data)
    contents.append(user_input)

    return generate_ai_response(contents, system_instruction, tools_list)
