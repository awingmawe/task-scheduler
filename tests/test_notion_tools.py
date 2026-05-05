import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Tambahkan root project ke sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.notion_tools import (
    update_notion_task,
    mark_all_tasks,
    create_notion_task,
    add_to_routine,
    remove_from_routine,
    delete_notion_task,
    create_notion_database,
    insert_into_dynamic_db
)

class TestNotionTools:
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

    def test_update_notion_task_success(self):
        """Task ditemukan, status dan summary diupdate."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._make_notion_results()
        mock_patch = MagicMock()
        mock_patch.status_code = 200

        with patch('tools.notion_tools.requests.post', return_value=mock_response), \
             patch('tools.notion_tools.requests.patch', return_value=mock_patch):
            result = update_notion_task("Test Task", True, "Test summary")

        assert "✅" in result
        assert "berhasil" in result.lower()

    def test_mark_all_tasks_success(self):
        """Semua task berhasil diupdate jadi selesai."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"id": "p1", "properties": {"Name": {"title": [{"text": {"content": "Task A"}}]}}},
                {"id": "p2", "properties": {"Name": {"title": [{"text": {"content": "Task B"}}]}}},
            ]
        }
        mock_patch = MagicMock()
        mock_patch.status_code = 200

        with patch('tools.notion_tools.requests.post', return_value=mock_resp), \
             patch('tools.notion_tools.requests.patch', return_value=mock_patch):
            result = mark_all_tasks(True)

        assert "✅" in result
        assert "2" in result

    def test_create_notion_task_success(self):
        """Task baru berhasil dibuat di Notion."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "new-page-id"}

        with patch('tools.notion_tools.requests.post', return_value=mock_resp), \
             patch('tools.notion_tools._task_exists_for_date', return_value=False):
            result = create_notion_task("Task Baru", duration="1 Jam", date_str="2026-05-02")

        assert "Task Baru" in result
        assert "berhasil dibuat" in result

    def test_delete_notion_task_success(self):
        """Task berhasil dihapus (archived)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self._make_notion_results()
        mock_patch = MagicMock()
        mock_patch.status_code = 200

        with patch('tools.notion_tools.requests.post', return_value=mock_resp), \
             patch('tools.notion_tools.requests.patch', return_value=mock_patch):
            result = delete_notion_task("Test Task", "2026-05-02")

        assert "berhasil dihapus" in result

class TestRoutineManagement:
    def test_add_to_routine(self):
        """Task baru berhasil ditambah ke rutinitas."""
        with patch('tools.notion_tools.get_master_routine_config',
                   return_value=("page-abc", [])), \
             patch('tools.notion_tools.update_master_routine_config'), \
             patch('tools.notion_tools.create_notion_task', return_value="Created"):
            result = add_to_routine("Task Baru", "30 Menit")

        assert "✅" in result
        assert "Task Baru" in result

    def test_remove_from_routine(self):
        """Task berhasil dihapus dari rutinitas."""
        existing = [{"name": "Task A", "duration": "1 Jam"}]
        with patch('tools.notion_tools.get_master_routine_config',
                   return_value=("page-abc", existing)), \
             patch('tools.notion_tools.update_master_routine_config'):
            result = remove_from_routine("Task A")

        assert "✅" in result
        assert "sukses" in result.lower()

class TestDynamicDatabase:
    @patch('tools.notion_tools.requests.post')
    @patch('tools.notion_tools._check_database_exists')
    @patch('tools.notion_tools._get_parent_page')
    @patch('tools.notion_tools.get_memory_config')
    @patch('tools.notion_tools._update_memory_config')
    def test_create_notion_database_success(self, mock_upd, mock_mem, mock_parent, mock_exists, mock_post):
        """Database baru berhasil dibuat dan dicatat di registry."""
        mock_exists.return_value = False
        mock_parent.return_value = {"type": "page_id", "page_id": "parent-123"}
        mock_mem.return_value = ("mem-id", {})
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "db-789", "url": "https://notion.so/db789"}
        mock_post.return_value = mock_resp
        
        result = create_notion_database("My Finance", "Finance")
        
        assert "✅" in result
        assert "db-789" not in result # ID hidden, URL shown
        assert "https://notion.so/db789" in result
        mock_upd.assert_called_once()

    @patch('tools.notion_tools._check_database_exists')
    def test_create_notion_database_duplicate(self, mock_exists):
        """Gagal jika nama database sudah ada."""
        mock_exists.return_value = True
        result = create_notion_database("Existing DB", "Journal")
        assert "Gagal" in result
        assert "sudah ada" in result

    def test_create_notion_database_invalid_template(self):
        """Gagal jika template tidak dikenal."""
        result = create_notion_database("Wrong", "Unknown")
        assert "tidak tersedia" in result

    @patch('tools.notion_tools.get_memory_config')
    @patch('tools.notion_tools.requests.post')
    def test_insert_into_dynamic_db_success(self, mock_post, mock_mem):
        """Berhasil memasukkan record ke database dinamis."""
        mock_mem.return_value = ("mem-id", {
            "_DATABASE_REGISTRY": {
                "My Finance": {"id": "db-123", "template": "Finance"}
            }
        })
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        
        result = insert_into_dynamic_db("My Finance", {"Name": {"title": [{"text": {"content": "Buy Coffee"}}]}})
        assert "✅" in result
        assert "berhasil" in result.lower()
    @patch('tools.notion_tools.requests.post')
    @patch('tools.notion_tools.requests.patch')
    @patch('tools.notion_tools._check_database_exists')
    @patch('tools.notion_tools._get_parent_page')
    @patch('tools.notion_tools.get_memory_config')
    def test_create_notion_database_registry_failure_rollback(self, mock_mem, mock_parent, mock_exists, mock_patch, mock_post):
        """Gagal registry -> Rollback (archive) database."""
        mock_exists.return_value = False
        mock_parent.return_value = {"type": "page_id", "page_id": "parent-123"}
        mock_mem.side_effect = Exception("Registry error")
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "db-fail", "url": "https://notion.so/dbfail"}
        mock_post.return_value = mock_resp
        
        # Patch for archive call
        mock_archive_resp = MagicMock()
        mock_archive_resp.status_code = 200
        mock_patch.return_value = mock_archive_resp
        
        result = create_notion_database("Fail DB", "Finance")
        
        assert "❌ Gagal" in result
        assert "telah otomatis di-rollback" in result
        # Verify patch (archive) was called
        mock_patch.assert_called_once()
        args, kwargs = mock_patch.call_args
        assert "db-fail" in args[0]
        assert kwargs["json"]["archived"] is True
