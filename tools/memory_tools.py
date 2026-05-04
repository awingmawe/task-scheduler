import os
import requests
import json
import time
from config import _notion_headers, _memory_cache, _MEMORY_TTL_SEC

def get_memory_config(skip_cache: bool = False) -> tuple[str | None, dict]:
    """Baca [CONFIG] AI MEMORY dari Notion. Return (page_id, memory_dict).
    Hasil dicache 5 menit agar tidak hit Notion API setiap request.
    """
    now = time.time()
    if not skip_cache and _memory_cache["data"] is not None and now < _memory_cache["expires_at"]:
        return _memory_cache["page_id"], _memory_cache["data"]

    db_id = os.environ["NOTION_DB_ID"]
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {
        "filter": {
            "property": "Name",
            "title": {"equals": "[CONFIG] AI MEMORY"}
        }
    }
    resp = requests.post(url, headers=_notion_headers(), json=payload).json()
    results = resp.get("results", [])

    if not results:
        url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {"title": [{"text": {"content": "[CONFIG] AI MEMORY"}}]},
                "Notes / Summary": {"rich_text": [{"text": {"content": json.dumps({})}}]}
            }
        }
        resp = requests.post(url, headers=_notion_headers(), json=payload).json()
        
        if "id" not in resp:
            print(f"[ERROR] Gagal membuat [CONFIG] AI MEMORY. Response: {json.dumps(resp)}")
            return None, {}

        _memory_cache.update({"data": {}, "page_id": resp["id"], "expires_at": now + _MEMORY_TTL_SEC})
        return resp["id"], {}

    page = results[0]
    page_id = page["id"]
    try:
        raw = page["properties"]["Notes / Summary"]["rich_text"][0]["text"]["content"]
        memory = json.loads(raw)
    except:
        memory = {}

    _memory_cache.update({"data": memory, "page_id": page_id, "expires_at": now + _MEMORY_TTL_SEC})
    return page_id, memory

def _update_memory_config(page_id: str, memory: dict):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Notes / Summary": {"rich_text": [{"text": {"content": json.dumps(memory, ensure_ascii=False)}}]}
        }
    }
    requests.patch(url, headers=_notion_headers(), json=payload)

def save_memory(key: str, value: str) -> str:
    """Simpan atau update sebuah fakta/ingatan ke memori AI."""
    try:
        page_id, memory = get_memory_config(skip_cache=True)
        memory[key] = value
        _update_memory_config(page_id, memory)
        _memory_cache.update({"data": memory, "page_id": page_id, "expires_at": time.time() + _MEMORY_TTL_SEC})
        return f"\u2705 Oke, aku udah ingat: '{key}' = '{value}'!"
    except Exception as e:
        return f"Gagal menyimpan memory: {str(e)}"

def delete_memory(key: str) -> str:
    """Hapus sebuah fakta dari memori AI berdasarkan key-nya."""
    try:
        page_id, memory = get_memory_config(skip_cache=True)
        if key not in memory:
            return f"Key '{key}' tidak ada di memori."
        del memory[key]
        _update_memory_config(page_id, memory)
        _memory_cache.update({"data": memory, "page_id": page_id, "expires_at": time.time() + _MEMORY_TTL_SEC})
        return f"\u2705 Oke, aku sudah lupa soal '{key}'."
    except Exception as e:
        return f"Gagal menghapus memory: {str(e)}"
