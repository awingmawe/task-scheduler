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
    delete_notion_task
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
