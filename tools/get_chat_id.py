import requests
import json
import sys

TOKEN = os.environ.get("TELEGRAM_TOKEN")
upd_resp = requests.get(f'https://api.telegram.org/bot{TOKEN}/getUpdates?limit=10&timeout=20')
data = upd_resp.json()

if data.get('result'):
    for upd in data['result']:
        msg = upd.get('message', {})
        chat = msg.get('chat', {})
        frm = msg.get('from', {})
        chat_id = chat.get('id')
        username = frm.get('username')
        text = msg.get('text')
        print(f'chat_id  : {chat_id}')
        print(f'username : {username}')
        print(f'text     : {text}')
        print('---')
else:
    print('Belum ada pesan masuk. Kirim pesan ke bot dulu!')
    print(json.dumps(data, indent=2))
