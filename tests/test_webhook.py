import sys
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Tambahkan root project ke sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.main import web_app

client = TestClient(web_app)

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

    def test_webhook_duplicate_blocked(self):
        """Duplicate update_id tetap return 200 tapi tidak diproses."""
        payload = {
            "update_id": 999999,
            "message": {
                "message_id": 2,
                "chat": {"id": 8344404871},
                "text": "Duplikat!"
            }
        }
        with patch('tools.main._is_duplicate', new=AsyncMock(return_value=True)):
            resp = client.post("/webhook", json=payload)

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_webhook_voice_note_handled(self):
        """Voice note harus diproses dengan mendownload file."""
        payload = {
            "update_id": 444444,
            "message": {
                "chat": {"id": 8344404871},
                "voice": {"file_id": "v123"}
            }
        }
        mock_file_resp = MagicMock()
        mock_file_resp.json.return_value = {"ok": True, "result": {"file_path": "path/to/file"}}
        
        mock_audio_resp = MagicMock()
        mock_audio_resp.content = b"fake-audio-bytes"

        with patch('tools.main._is_duplicate', new=AsyncMock(return_value=False)), \
             patch('tools.main.requests.get') as mock_get, \
             patch('tools.main.BackgroundTasks.add_task') as mock_add_task:
            
            mock_get.side_effect = [mock_file_resp, mock_audio_resp]
            resp = client.post("/webhook", json=payload)

        assert resp.status_code == 200
        mock_add_task.assert_called_once()
