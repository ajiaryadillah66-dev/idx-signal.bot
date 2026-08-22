"""
Modul pengirim notifikasi ke Telegram.

Butuh 2 env var:
- TELEGRAM_BOT_TOKEN : token bot dari @BotFather
- TELEGRAM_CHAT_ID   : chat id tujuan (bisa dapat dari @userinfobot)
"""

import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[notifier] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diset. Pesan:\n", text)
        return

    # Telegram batas 4096 karakter per pesan -> potong kalau kepanjangan
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)] or [text]

    for chunk in chunks:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            data={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if not resp.ok:
            print(f"[notifier] Gagal kirim pesan: {resp.status_code} {resp.text}")
