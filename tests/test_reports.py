import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Tambahkan root project ke sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.reports import get_daily_report, get_weekly_report, get_monthly_report

class TestReports:
    def test_get_daily_report_format(self):
        """Report harus punya section selesai dan belum."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
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
        mock_resp.raise_for_status = MagicMock()

        with patch('tools.reports.requests.post', return_value=mock_resp):
            report = get_daily_report("2026-05-02")

        assert "Task Selesai" in report
        assert "Task Belum" in report
        assert "✅" in report
        assert "❌" in report

    def test_get_weekly_report(self):
        """Weekly report mengembalikan string yang berisi ringkasan mingguan."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "properties": {
                        "Name": {"title": [{"text": {"content": "Habit A"}}]},
                        "Date": {"date": {"start": "2026-05-02"}},
                        "Status": {"checkbox": False} # Missed habit
                    }
                }
            ]
        }
        with patch('tools.reports.requests.post', return_value=mock_resp):
            report = get_weekly_report()
        
        assert "LAPORAN MINGGUAN" in report
        assert "Habit A" in report

    def test_get_monthly_report(self):
        """Monthly report mengembalikan string yang berisi ringkasan bulanan."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "properties": {
                        "Name": {"title": [{"text": {"content": "Habit B"}}]},
                        "Date": {"date": {"start": "2026-05-01"}},
                        "Status": {"checkbox": True}
                    }
                }
            ]
        }
        with patch('tools.reports.requests.post', return_value=mock_resp):
            report = get_monthly_report()
        
        assert "LAPORAN BULANAN" in report
        assert "Habit B" in report
