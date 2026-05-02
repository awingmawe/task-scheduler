"""
conftest.py — Shared fixtures untuk semua test di task-scheduler.
Mocking semua environment variable agar test bisa jalan tanpa .env asli,
dan tanpa koneksi ke Notion, Telegram, GCal, atau Gemini.
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# -------------------------------------------------------
# Mock semua external modules SEBELUM import main.py
# Ini penting karena main.py import modal, google.generativeai, dll
# saat file di-load (module-level), bukan hanya saat fungsi dipanggil.
# -------------------------------------------------------

# Mock modal module
mock_modal = MagicMock()
mock_modal_dict = MagicMock()
mock_modal_dict.get = MagicMock(return_value=None)
mock_modal.Dict.from_name.return_value = mock_modal_dict
mock_modal.App = MagicMock(return_value=MagicMock())
mock_modal.Image.debian_slim.return_value.pip_install.return_value = MagicMock()
mock_modal.Secret.from_name.return_value = MagicMock()
mock_modal.Cron = MagicMock()
mock_modal.asgi_app = lambda: lambda f: f
sys.modules['modal'] = mock_modal

# Mock google.generativeai
mock_genai = MagicMock()
sys.modules['google.generativeai'] = mock_genai
sys.modules['google'] = MagicMock()
sys.modules['google.oauth2'] = MagicMock()
sys.modules['google.oauth2.credentials'] = MagicMock()
sys.modules['google.auth'] = MagicMock()
sys.modules['google.auth.transport'] = MagicMock()
sys.modules['google.auth.transport.requests'] = MagicMock()
sys.modules['googleapiclient'] = MagicMock()
sys.modules['googleapiclient.discovery'] = MagicMock()

# Mock notion_client
mock_notion_client = MagicMock()
sys.modules['notion_client'] = mock_notion_client


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """
    Inject fake environment variables untuk semua test secara otomatis.
    Ini supaya fungsi-fungsi yang baca os.environ tidak crash.
    """
    monkeypatch.setenv("NOTION_TOKEN", "fake-notion-token")
    monkeypatch.setenv("NOTION_DB_ID", "fake-db-id-1234")
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "8344404871")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("GCAL_REFRESH_TOKEN", "fake-refresh-token")
    monkeypatch.setenv("GCAL_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GCAL_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("GCAL_CALENDAR_ID", "primary")
