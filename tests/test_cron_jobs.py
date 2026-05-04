import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Tambahkan root project ke sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.cron_jobs import (
    execute_morning_slap,
    execute_noon_slap,
    execute_afternoon_slap,
    execute_evening_slap
)

class TestCronJobs:
    @patch('tools.cron_jobs.get_master_routine_config')
    @patch('tools.cron_jobs._task_exists_for_date')
    @patch('tools.cron_jobs.create_notion_task')
    @patch('tools.cron_jobs.send_telegram_message')
    def test_morning_slap(self, mock_send, mock_create, mock_exists, mock_config):
        mock_config.return_value = ("page-1", [{"name": "Task 1", "duration": "1h"}])
        mock_exists.return_value = False
        
        execute_morning_slap()
        
        mock_create.assert_called_once()
        mock_send.assert_called_once()
        assert "Woi bangun" in mock_send.call_args[0][0]

    @patch('tools.cron_jobs.get_daily_report')
    @patch('tools.cron_jobs.send_telegram_message')
    def test_noon_slap(self, mock_send, mock_report):
        mock_report.return_value = "Daily Report Content"
        execute_noon_slap()
        mock_send.assert_called_once()
        assert "Matahari udah di atas kepala" in mock_send.call_args[0][0]

    @patch('tools.cron_jobs.get_daily_report')
    @patch('tools.cron_jobs.generate_ai_response')
    @patch('tools.cron_jobs.send_telegram_message')
    @patch('tools.cron_jobs.requests.post')
    @patch('tools.cron_jobs.requests.patch')
    def test_evening_slap(self, mock_patch, mock_post, mock_send, mock_ai, mock_report):
        mock_report.return_value = "Daily Report Content"
        mock_ai.return_value = "AI Reflection Content"
        mock_post.return_value.json.return_value = {"results": []} # No existing report
        
        execute_evening_slap()
        
        mock_ai.assert_called_once()
        mock_send.assert_called_once()
        assert "Woi udah jam 6 sore" in mock_send.call_args[0][0]
        assert "AI Reflection Content" in mock_send.call_args[0][0]
