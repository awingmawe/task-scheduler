import os
import sys
from dotenv import load_dotenv

# Tambahkan folder tools ke sys.path agar import lokal berfungsi
sys.path.append(os.path.join(os.getcwd(), "tools"))

# Load environment variables dari .env
load_dotenv()

from cron_jobs import execute_morning_slap, execute_noon_slap, execute_evening_slap
from ai_agent import process_with_ai
from telegram_tools import send_telegram_message
from reports import get_daily_report

def test_ai_processing():
    print("\n--- Testing AI Processing ---")
    test_text = "Halo bot, apa kabar? Coba buatkan task 'Belajar Modal' untuk hari ini jam 10 malam."
    print(f"Input: {test_text}")
    response = process_with_ai(test_text)
    print(f"AI Response: {response}")

def test_morning_slap():
    print("\n--- Testing Morning Slap Logic ---")
    # Ini akan membuat task di Notion jika belum ada
    execute_morning_slap()
    print("Morning slap logic executed.")

def test_daily_report():
    print("\n--- Testing Daily Report ---")
    from config import _today_wib
    today = _today_wib()
    report = get_daily_report(today)
    print(f"Daily Report for {today}:\n{report}")

if __name__ == "__main__":
    print("Starting Manual Tests...")
    
    # Pilih test yang mau dijalankan
    try:
        test_ai_processing()
        # test_morning_slap() # Hati-hati, ini beneran nulis ke Notion
        test_daily_report()
        print("\nAll manual tests completed successfully!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nManual test failed with error: {e}")
