"""
test_main.py — Unit tests untuk tools/main.py (task-scheduler)
Semua external API (Notion, Telegram, Gemini, GCal, modal) di-mock.

Test Coverage:
    - _notion_headers()
    - _is_duplicate()
    - send_telegram_message()
    - update_notion_task()
    - mark_all_tasks()
    - get_daily_report()
    - create_notion_task()
    - add_to_routine() / remove_from_routine()
    - save_memory() / delete_memory()
    - get_memory_config() (cache & no-cache path)
    - Webhook endpoint /webhook (via FastAPI TestClient)
"""
import sys
import os
import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
from fastapi.testclient import TestClient


# -------------------------------------------------------
# Import modul utama (conftest.py sudah mock semua deps)
# -------------------------------------------------------
# Tambahkan root project ke sys.path supaya import tools.main bisa jalan
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import importlib
import tools.main as main_module
from tools.main import (
    _notion_headers,
    _is_duplicate,
    send_telegram_message,
    update_notion_task,
    mark_all_tasks,
    get_daily_report,
    create_notion_task,
    add_to_routine,
    remove_from_routine,
    save_memory,
    delete_memory,
    get_memory_config,
    _memory_cache,
    web_app,
)

client = TestClient(web_app)


# ======================================================
# 1. TEST _notion_headers()
# ======================================================
class TestNotionHeaders:
    def test_returns_correct_keys(self):
        """Pastikan header Notion punya key yang benar."""
        headers = _notion_headers()
        assert "Authorization" in headers
        assert "Content-Type" in headers
        assert "Notion-Version" in headers

    def test_authorization_format(self):
        """Authorization header harus dimulai dengan 'Bearer'."""
        headers = _notion_headers()
        assert headers["Authorization"].startswith("Bearer ")

    def test_content_type_is_json(self):
        headers = _notion_headers()
        assert headers["Content-Type"] == "application/json"

    def test_notion_version_present(self):
        headers = _notion_headers()
        # Versi Notion harus ada (format YYYY-MM-DD)
        assert len(headers["Notion-Version"]) == 10


# ======================================================
# 2. TEST _is_duplicate()
# ======================================================
class TestIsDuplicate:
    def test_first_call_not_duplicate(self):
        """Update ID baru bukan duplikat."""
        sys.modules['modal'].Dict.from_name.return_value.get.aio = AsyncMock(return_value=None)
        sys.modules['modal'].Dict.from_name.return_value.put.aio = AsyncMock()
        import asyncio
        result = asyncio.run(_is_duplicate(99999))
        assert result is False

    def test_second_call_within_ttl_is_duplicate(self):
        """Update ID yang sudah ada dalam TTL adalah duplikat."""
        recent_ts = time.time()
        sys.modules['modal'].Dict.from_name.return_value.get.aio = AsyncMock(return_value=recent_ts)
        sys.modules['modal'].Dict.from_name.return_value.put.aio = AsyncMock()
        import asyncio
        result = asyncio.run(_is_duplicate(99999))
        assert result is True

    def test_expired_entry_not_duplicate(self):
        """Update ID yang sudah expired (> 120 detik) bukan duplikat."""
        old_ts = time.time() - 200  # 200 detik yang lalu
        sys.modules['modal'].Dict.from_name.return_value.get.aio = AsyncMock(return_value=old_ts)
        sys.modules['modal'].Dict.from_name.return_value.put.aio = AsyncMock()
        import asyncio
        result = asyncio.run(_is_duplicate(99999))
        assert result is False

    def test_modal_dict_error_returns_false(self):
        """Jika modal.Dict error, jangan block request (return False)."""
        sys.modules['modal'].Dict.from_name.return_value.get.aio = AsyncMock(
            side_effect=Exception("Modal error")
        )
        import asyncio
        result = asyncio.run(_is_duplicate(12345))
        assert result is False


# ======================================================
# 3. TEST send_telegram_message()
# ======================================================
class TestSendTelegramMessage:
    def test_sends_correct_payload(self):
        """Pastikan payload yang dikirim ke Telegram API benar."""
        with patch('tools.main.requests.post') as mock_post:
            mock_post.return_value = MagicMock(text='{"ok": true}')
            send_telegram_message("Hello Test!", chat_id=8344404871)

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            payload = call_kwargs[1]['json']  # kwarg 'json'
            assert payload['chat_id'] == 8344404871
            assert payload['text'] == "Hello Test!"
            assert payload['parse_mode'] == "Markdown"

    def test_fallback_chat_id_from_env(self):
        """Kalau chat_id tidak diberikan, pakai dari env TELEGRAM_CHAT_ID."""
        with patch('tools.main.requests.post') as mock_post:
            mock_post.return_value = MagicMock(text='{"ok": true}')
            send_telegram_message("Fallback test")
            mock_post.assert_called_once()


# ======================================================
# 4. TEST update_notion_task()
# ======================================================
class TestUpdateNotionTask:
    def _make_notion_results(self, task_name="Test Task", page_id="page-123"):
        return {
            "results": [{
                "id": page_id,
                "properties": {
                    "Name": {"title": [{"text": {"content": task_name}}]},
                    "Status": {"checkbox": False}
                }
            }]
        }

    def test_task_found_and_updated(self):
        """Task ditemukan, status dan summary diupdate."""
        mock_response = MagicMock()
        mock_response.json.return_value = self._make_notion_results()
        mock_patch = MagicMock()

        with patch('tools.main.requests.post', return_value=mock_response) as mock_post, \
             patch('tools.main.requests.patch', return_value=mock_patch):
            result = update_notion_task("Test Task", True, "Test summary")

        assert "berhasil" in result.lower() or "✅" in result

    def test_task_not_found(self):
        """Jika task tidak ditemukan, return pesan tidak ditemukan."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}

        with patch('tools.main.requests.post', return_value=mock_response):
            result = update_notion_task("Nonexistent Task", True)

        assert "tidak ditemukan" in result.lower()

    def test_notion_api_error(self):
        """Jika Notion API throw exception, return pesan error."""
        with patch('tools.main.requests.post', side_effect=Exception("Connection error")):
            result = update_notion_task("Any Task", True)

        assert "Error" in result


# ======================================================
# 5. TEST mark_all_tasks()
# ======================================================
class TestMarkAllTasks:
    def _make_multi_results(self):
        return {
            "results": [
                {"id": "p1", "properties": {"Name": {"title": [{"text": {"content": "Task A"}}]}}},
                {"id": "p2", "properties": {"Name": {"title": [{"text": {"content": "Task B"}}]}}},
            ]
        }

    def test_marks_all_done(self):
        """Semua task berhasil diupdate jadi selesai."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._make_multi_results()

        with patch('tools.main.requests.post', return_value=mock_resp), \
             patch('tools.main.requests.patch', return_value=MagicMock()):
            result = mark_all_tasks(True)

        assert "✅" in result
        assert "2" in result  # 2 task diupdate

    def test_no_tasks_found(self):
        """Tidak ada task untuk tanggal itu."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}

        with patch('tools.main.requests.post', return_value=mock_resp):
            result = mark_all_tasks(True, "2020-01-01")

        assert "tidak ada" in result.lower()

    def test_api_error_handled(self):
        """Exception saat bulk update ditangani dengan baik."""
        with patch('tools.main.requests.post', side_effect=Exception("Notion down")):
            result = mark_all_tasks(False)

        assert "Error" in result


# ======================================================
# 6. TEST get_daily_report()
# ======================================================
class TestGetDailyReport:
    def _make_report_results(self):
        return {
            "results": [
                {
                    "properties": {
                        "Name": {"title": [{"text": {"content": "Task Selesai"}}]},
                        "Status": {"checkbox": True}
                    }
                },
                {
                    "properties": {
                        "Name": {"title": [{"text": {"content": "Task Belum"}}]},
                        "Status": {"checkbox": False}
                    }
                }
            ]
        }

    def test_report_format_correct(self):
        """Report harus punya section selesai dan belum."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = self._make_report_results()
        mock_resp.raise_for_status = MagicMock()

        with patch('tools.main.requests.post', return_value=mock_resp):
            report = get_daily_report("2026-05-02")

        assert "Task Selesai" in report
        assert "Task Belum" in report
        assert "✅" in report
        assert "❌" in report

    def test_no_tasks_returns_empty_message(self):
        """Kalau tidak ada task, balik pesan kosong."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()

        with patch('tools.main.requests.post', return_value=mock_resp):
            report = get_daily_report("2020-01-01")

        assert "tidak ada" in report.lower()

    def test_api_error_handled(self):
        with patch('tools.main.requests.post', side_effect=Exception("Timeout")):
            result = get_daily_report()

        assert "Gagal" in result


# ======================================================
# 7. TEST create_notion_task()
# ======================================================
class TestCreateNotionTask:
    def test_creates_task_successfully(self):
        """Task baru berhasil dibuat di Notion via raw requests."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "new-page-id"}

        with patch('tools.main.requests.post', return_value=mock_resp):
            result = create_notion_task("Task Baru", duration="1 Jam", date_str="2026-05-02")

        assert "Task Baru" in result
        assert "2026-05-02" in result

    def test_creates_task_with_gcal_sync(self):
        """Task dengan start_time seharusnya trigger GCal event creation."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "new-page-id"}

        with patch('tools.main.requests.post', return_value=mock_resp), \
             patch('tools.main.create_google_calendar_event', return_value="GCal OK") as mock_gcal:
            result = create_notion_task("Task GCal", duration="2 Jam",
                                        date_str="2026-05-02", start_time="09:00")

        mock_gcal.assert_called_once()
        assert "GCal OK" in result

    def test_handles_exception(self):
        """Exception saat requests.post gagal ditangani dengan baik."""
        with patch('tools.main.requests.post', side_effect=Exception("Notion API error")):
            result = create_notion_task("Bad Task")

        assert "Gagal" in result


# ======================================================
# 8. TEST add_to_routine() / remove_from_routine()
# ======================================================
class TestRoutineManagement:
    def _setup_routine_mock(self, existing_routine=None):
        if existing_routine is None:
            existing_routine = [{"name": "Task Lama", "duration": "1 Jam"}]
        return "page-abc", existing_routine

    def test_add_new_task_to_routine(self):
        """Task baru berhasil ditambah ke rutinitas."""
        with patch('tools.main.get_master_routine_config',
                   return_value=self._setup_routine_mock()), \
             patch('tools.main.update_master_routine_config') as mock_update:
            result = add_to_routine("Task Baru", "30 Menit")

        assert "✅" in result
        assert "Task Baru" in result
        mock_update.assert_called_once()

    def test_add_duplicate_task(self):
        """Tidak bisa tambah task yang sudah ada."""
        existing = [{"name": "Task Lama", "duration": "1 Jam"}]
        with patch('tools.main.get_master_routine_config',
                   return_value=("page-abc", existing)):
            result = add_to_routine("Task Lama", "1 Jam")

        assert "sudah ada" in result.lower()

    def test_remove_existing_task(self):
        """Task berhasil dihapus dari rutinitas."""
        existing = [
            {"name": "Task A", "duration": "1 Jam"},
            {"name": "Task B", "duration": "30 Menit"}
        ]
        with patch('tools.main.get_master_routine_config',
                   return_value=("page-abc", existing)), \
             patch('tools.main.update_master_routine_config') as mock_update:
            result = remove_from_routine("Task A")

        assert "✅" in result
        # Pastikan update dipanggil dengan list tanpa "Task A"
        updated_list = mock_update.call_args[0][1]
        assert all(t["name"] != "Task A" for t in updated_list)

    def test_remove_nonexistent_task(self):
        """Task yang tidak ada tidak bisa dihapus."""
        existing = [{"name": "Task B", "duration": "1 Jam"}]
        with patch('tools.main.get_master_routine_config',
                   return_value=("page-abc", existing)):
            result = remove_from_routine("Task Tidak Ada")

        assert "tidak ditemukan" in result.lower()


# ======================================================
# 9. TEST save_memory() / delete_memory()
# ======================================================
class TestMemorySystem:
    def test_save_memory_success(self):
        """Memory berhasil disimpan."""
        initial_memory = {}
        with patch('tools.main.get_memory_config', return_value=("page-mem", initial_memory)), \
             patch('tools.main._update_memory_config') as mock_update:
            result = save_memory("nama_pacar", "Ayu")

        assert "✅" in result
        mock_update.assert_called_once()
        # Pastikan value tersimpan
        saved = mock_update.call_args[0][1]
        assert saved.get("nama_pacar") == "Ayu"

    def test_delete_existing_key(self):
        """Key yang ada berhasil dihapus."""
        initial_memory = {"nama_pacar": "Ayu", "target": "Belajar"}
        with patch('tools.main.get_memory_config', return_value=("page-mem", initial_memory)), \
             patch('tools.main._update_memory_config') as mock_update:
            result = delete_memory("nama_pacar")

        assert "✅" in result
        saved = mock_update.call_args[0][1]
        assert "nama_pacar" not in saved
        assert "target" in saved  # key lain tidak terpengaruh

    def test_delete_nonexistent_key(self):
        """Delete key yang tidak ada return pesan error."""
        initial_memory = {"target": "Belajar"}
        with patch('tools.main.get_memory_config', return_value=("page-mem", initial_memory)):
            result = delete_memory("key_tidak_ada")

        assert "tidak ada" in result.lower()

    def test_save_memory_exception(self):
        """Exception saat save ditangani."""
        with patch('tools.main.get_memory_config', side_effect=Exception("Notion error")):
            result = save_memory("key", "value")

        assert "Gagal" in result


# ======================================================
# 10. TEST get_memory_config() — Cache Logic
# ======================================================
class TestMemoryCache:
    def test_cache_hit(self):
        """Cache yang masih valid tidak hit Notion API."""
        # Set cache valid
        main_module._memory_cache["data"] = {"cached_key": "cached_val"}
        main_module._memory_cache["page_id"] = "page-cached"
        main_module._memory_cache["expires_at"] = time.time() + 300

        with patch('tools.main.requests.post') as mock_post:
            page_id, memory = get_memory_config()

        # Notion tidak dipanggil karena cache valid
        mock_post.assert_not_called()
        assert memory == {"cached_key": "cached_val"}

        # Reset cache untuk test lain
        main_module._memory_cache.update({"data": None, "page_id": None, "expires_at": 0.0})

    def test_cache_miss_hits_api(self):
        """Cache expired → hit Notion API."""
        # Pastikan cache expired
        main_module._memory_cache["data"] = None
        main_module._memory_cache["expires_at"] = 0.0

        fake_memory = {"test_key": "test_val"}
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [{
                "id": "page-from-api",
                "properties": {
                    "Notes / Summary": {
                        "rich_text": [{"text": {"content": json.dumps(fake_memory)}}]
                    }
                }
            }]
        }

        with patch('tools.main.requests.post', return_value=mock_resp):
            page_id, memory = get_memory_config()

        assert memory == fake_memory
        assert page_id == "page-from-api"

        # Reset cache
        main_module._memory_cache.update({"data": None, "page_id": None, "expires_at": 0.0})


# ======================================================
# 11. TEST Webhook Endpoint /webhook
# ======================================================
class TestWebhook:
    def test_webhook_text_message_returns_ok(self):
        """Webhook dengan pesan teks harus return 200 dan {status: ok}."""
        payload = {
            "update_id": 111111,
            "message": {
                "message_id": 1,
                "from": {"id": 8344404871, "first_name": "Rafis"},
                "chat": {"id": 8344404871, "type": "private"},
                "date": 1690000000,
                "text": "Halo bot!"
            }
        }
        with patch('tools.main._is_duplicate', new=AsyncMock(return_value=False)), \
             patch('tools.main._process_and_reply_sync'):
            resp = client.post("/webhook", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_webhook_duplicate_returns_ok(self):
        """Duplicate update_id tetap return 200 tapi tidak diproses."""
        payload = {
            "update_id": 999999,
            "message": {
                "message_id": 2,
                "chat": {"id": 8344404871, "type": "private"},
                "date": 1690000001,
                "text": "Duplikat!"
            }
        }
        with patch('tools.main._is_duplicate', new=AsyncMock(return_value=True)) as mock_dedup:
            resp = client.post("/webhook", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        mock_dedup.assert_called_once_with(999999)

    def test_webhook_no_message_returns_ok(self):
        """Payload tanpa key 'message' tetap return 200."""
        payload = {"update_id": 222222}
        with patch('tools.main._is_duplicate', new=AsyncMock(return_value=False)):
            resp = client.post("/webhook", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_webhook_empty_text_not_processed(self):
        """Pesan dengan text kosong tidak trigger background task."""
        payload = {
            "update_id": 333333,
            "message": {
                "chat": {"id": 8344404871, "type": "private"},
                "date": 1690000002,
                "text": ""
            }
        }
        with patch('tools.main._is_duplicate', new=AsyncMock(return_value=False)), \
             patch('tools.main._process_and_reply_sync') as mock_process:
            resp = client.post("/webhook", json=payload)

        assert resp.status_code == 200
        mock_process.assert_not_called()
