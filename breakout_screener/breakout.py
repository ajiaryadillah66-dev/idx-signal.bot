"""
Manajemen risiko: entry zone, stop loss (ATR-based), target 1/2, risk/reward.
Bagian 12, 16, 17 dari spek.
"""

import pandas as pd

from . import config as cfg


def compute_entry_zone(df, breakout_info: dict, overextended_info: dict) -> dict:
    """Bagian 16 -- tentukan area entry berdasarkan posisi harga vs resistance."""
    close = float(df["Close"].iloc[-1])
    resistance = breakout_info.get("resistance")

    if overextended_info.get("do_not_chase"):
        return {"entry_zone": "DO NOT CHASE", "note": "harga sudah naik terlalu jauh dari resistance"}

    if breakout_info.get("breakout"):
        return {
            "entry_zone": f"~{resistance} - {round(close, 2)} (area breakout)",
            "note": "gunakan area breakout sebagai referensi entry",
        }

    if resistance:
        return {
            "entry_zone": f"dekat {resistance} (jangan kejar kalau sudah jauh di atas)",
            "note": None,
        }

    return {"entry_zone": "-", "note": "resistance belum tersedia (data kurang)"}


def compute_stop_loss(df) -> dict:
    """Bagian 12 -- ATR-based stop loss, BUKAN persentase tetap untuk semua saham."""
    if len(df) == 0 or "ATR14" not in df.columns:
        return {"stop_loss": None, "risk_pct": None}

    close = float(df["Close"].iloc[-1])
    atr = df["ATR14"].iloc[-1]
    support = df["Support20"].iloc[-1] if "Support20" in df.columns else None

    if pd.isna(atr):
        return {"stop_loss": None, "risk_pct": None}

    stop_loss = close - (atr * cfg.ATR_STOP_MULTIPLIER)

    # Support terdekat dipakai sebagai REFERENSI TAMBAHAN, bukan pengganti ATR stop
    if pd.notna(support) and support > stop_loss:
        stop_loss = max(stop_loss, support * 0.98)

    risk_pct = (close - stop_loss) / close * 100 if close > 0 else None
    return {
        "stop_loss": round(stop_loss, 2),
        "risk_pct": round(risk_pct, 2) if risk_pct is not None else None,
    }


def compute_targets(df, stop_loss: float) -> dict:
    """Bagian 17 -- target berdasarkan resistance berikutnya, R:R minimal 1:2, dan ATR."""
    if len(df) == 0 or "ATR14" not in df.columns or stop_loss is None:
        return {"target1": None, "target2": None, "risk_reward": None}

    close = float(df["Close"].iloc[-1])
    atr = df["ATR14"].iloc[-1]
    if pd.isna(atr):
        return {"target1": None, "target2": None, "risk_reward": None}

    risk = close - stop_loss
    if risk <= 0:
        return {"target1": None, "target2": None, "risk_reward": None}

    target1 = close + risk * cfg.MIN_RISK_REWARD          # R:R minimal 1:2
    target2 = close + risk * (cfg.MIN_RISK_REWARD * 1.5)  # target lanjutan ~1:3
    target1 = max(target1, close + atr)                  # ATR sebagai referensi tambahan

    risk_reward = round((target1 - close) / risk, 2) if risk > 0 else None
    return {
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "risk_reward": risk_reward,
    }
