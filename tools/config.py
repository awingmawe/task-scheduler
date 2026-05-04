import os
import datetime
import time
import modal

# ---------------------------------------------------------
# DEDUP: modal.Dict — shared lintas semua container instances
# ---------------------------------------------------------
dedup_store = modal.Dict.from_name("webhook-dedup", create_if_missing=True)
_DEDUP_TTL_SEC = 120  # tolak duplicate dalam 2 menit

async def _is_duplicate(update_id: int) -> bool:
    """Async check-and-set di modal.Dict. Return True jika sudah diproses."""
    key = str(update_id)
    now = time.time()
    try:
        stored = await dedup_store.get.aio(key)
        if stored and now - stored < _DEDUP_TTL_SEC:
            return True
        await dedup_store.put.aio(key, now)
        return False
    except Exception:
        # Kalau modal.Dict error, lanjut proses (safer than blocking)
        return False

# ---------------------------------------------------------
# Memory cache dengan TTL 5 menit
# ---------------------------------------------------------
_memory_cache: dict = {"data": None, "page_id": None, "expires_at": 0.0}
_MEMORY_TTL_SEC = 300  # cache 5 menit

# ---------------------------------------------------------
# COMMON HELPERS
# ---------------------------------------------------------
def _notion_headers() -> dict:
    """Helper: return standard Notion REST API headers."""
    return {
        "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

WIB = datetime.timezone(datetime.timedelta(hours=7))

def _today_wib() -> str:
    """Return tanggal hari ini dalam timezone WIB (UTC+7) — format YYYY-MM-DD."""
    return datetime.datetime.now(WIB).strftime("%Y-%m-%d")
