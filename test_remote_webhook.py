import requests

url = "https://rafisetiadipura--notion-telegram-scheduler-fastapi-app.modal.run/webhook"
payload = {
    "update_id": 12345678,
    "message": {
        "chat": {"id": 1609724101},
        "text": "Halo bot, ini test dari remote script."
    }
}

try:
    resp = requests.post(url, json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
