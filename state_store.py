"""
Menyimpan daftar saham yang sudah dinotifikasi hari ini, biar alert
real-time gak muncul berkali-kali untuk saham yang sama.

State disimpan di state/notified_today.json dan otomatis di-reset
begitu tanggalnya berubah. File ini di-commit balik ke repo oleh
GitHub Actions setelah tiap run intraday (lihat workflow).
"""

import json
import os
from datetime import datetime, timezone, timedelta

STATE_PATH = os.path.join(os.path.dirname(__file__), "state", "notified_today.json")
WIB = timezone(timedelta(hours=7))


def _today_str():
    return datetime.now(WIB).strftime("%Y-%m-%d")


def load_notified_today() -> set:
    if not os.path.exists(STATE_PATH):
        return set()
    try:
        with open(STATE_PATH, "r") as f:
            data = json.load(f)
    except Exception:
        return set()

    if data.get("date") != _today_str():
        return set()  # hari sudah berganti -> reset
    return set(data.get("tickers", []))


def save_notified_today(tickers: set):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump({"date": _today_str(), "tickers": sorted(tickers)}, f, indent=2)
