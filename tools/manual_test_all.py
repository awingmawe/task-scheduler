import os
import sys
import json
import datetime
from dotenv import load_dotenv

# Add tools to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load env
load_dotenv()

from verify_connections import verify_telegram, verify_gemini, verify_notion, verify_gcal
from notion_tools import (
    create_notion_task, 
    update_notion_task, 
    delete_notion_task,
    add_to_routine,
    remove_from_routine,
    mark_all_tasks
)
from memory_tools import save_memory, delete_memory, get_memory_config
from reports import get_daily_report
from config import _today_wib

def test_connections():
    print("\n=== [1] TESTING CONNECTIONS ===")
    verify_telegram()
    verify_gemini()
    verify_notion()
    verify_gcal()

def test_memory():
    print("\n=== [2] TESTING AI MEMORY ===")
    key = "test_key_123"
    val = "test_value_abc"
    
    print(f"Saving memory: {key} -> {val}")
    res_save = save_memory(key, val)
    print(f"Result: {res_save}")
    
    _, mem = get_memory_config(skip_cache=True)
    if mem.get(key) == val:
        print(f"✅ Memory verified in Notion.")
    else:
        print(f"❌ Memory NOT found in Notion! Got: {mem}")
        
    print(f"Deleting memory: {key}")
    res_del = delete_memory(key)
    print(f"Result: {res_del}")
    
    _, mem2 = get_memory_config(skip_cache=True)
    if key not in mem2:
        print(f"✅ Delete verified.")
    else:
        print(f"❌ Key still exists in memory!")

def test_routine():
    print("\n=== [3] TESTING MASTER ROUTINE ===")
    task_name = "TEST ROUTINE TASK"
    
    print(f"Adding '{task_name}' to routine...")
    res_add = add_to_routine(task_name, "10 Menit")
    print(f"Result: {res_add}")
    
    print(f"Removing '{task_name}' from routine...")
    res_rem = remove_from_routine(task_name)
    print(f"Result: {res_rem}")
    
    # Cleanup task created by add_to_routine
    delete_notion_task(task_name)

def test_task_crud():
    print("\n=== [4] TESTING TASK CRUD ===")
    task_name = "MANUAL TEST TASK"
    today = _today_wib()
    
    print(f"Creating task '{task_name}' for {today}...")
    res_create = create_notion_task(task_name, duration="30 Menit")
    print(f"Result: {res_create}")
    
    print(f"Updating task '{task_name}' to DONE...")
    res_upd = update_notion_task(task_name, status=True, summary="Testing summary")
    print(f"Result: {res_upd}")
    
    print(f"Generating Daily Report...")
    report = get_daily_report(today)
    print(f"Report Output:\n{report}")
    
    if task_name in report and "✅" in report:
         print(f"✅ Task found in report with completed status.")
    else:
         print(f"❌ Task not found or status incorrect in report.")
         
    print(f"Deleting task '{task_name}'...")
    res_del = delete_notion_task(task_name)
    print(f"Result: {res_del}")

def test_bulk_update():
    print("\n=== [5] TESTING BULK UPDATE ===")
    t1 = "BULK TEST 1"
    t2 = "BULK TEST 2"
    
    create_notion_task(t1)
    create_notion_task(t2)
    
    print("Marking all tasks as DONE...")
    res = mark_all_tasks(True)
    print(f"Result: {res}")
    
    print("Marking all tasks as NOT DONE...")
    res2 = mark_all_tasks(False)
    print(f"Result: {res2}")
    
    delete_notion_task(t1)
    delete_notion_task(t2)

if __name__ == "__main__":
    print("Starting Comprehensive Manual Tests...")
    print("WARNING: This will perform real API calls to Notion, Gemini, and GCal.")
    
    steps = [
        ("Connections", test_connections),
        ("Memory", test_memory),
        ("Routine", test_routine),
        ("Task CRUD", test_task_crud),
        ("Bulk Update", test_bulk_update)
    ]
    
    for name, func in steps:
        try:
            func()
        except Exception as e:
            print(f"\n❌ Step '{name}' failed: {e}")
            
    print("\n✨ ALL COMPREHENSIVE TESTS COMPLETED! ✨")
