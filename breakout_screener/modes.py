"""
Klasifikasi 3 mode screening (Bagian 14): RADAR, SIAGA, ENTRY.

Prioritas pengecekan: ENTRY > SIAGA > RADAR -- satu saham dicek dari
level paling matang dulu, biar saham yang sudah breakout confirmed gak
malah "terjebak" di kategori RADAR yang lebih longgar.
"""

from . import config as cfg


def classify_mode(df, score_result: dict) -> str:
    comp = score_result["components"]
    breakout = comp["breakout"]
    rsi = comp["rsi"]
    ma = comp["ma"]
    volume = comp["volume"]

    last_rsi = rsi.get("last_rsi")
    rel_vol = volume.get("relative_volume")
    distance_pct = breakout.get("distance_pct")

    # --- MODE C: ENTRY -- breakout sudah dikonfirmasi ---
    if (
        breakout.get("breakout")
        and rel_vol is not None and rel_vol > cfg.REL_VOLUME_TIER1
        and ma["raw"] >= 10  # MA9 > MA26 minimal kebentuk
        and last_rsi is not None and last_rsi > cfg.RSI_MOMENTUM_LOW
        and not comp["overextended"].get("do_not_chase")
    ):
        return "ENTRY"

    # --- MODE B: SIAGA -- sudah mulai bergerak, mendekati breakout ---
    if (
        ma["raw"] >= 10
        and last_rsi is not None and last_rsi > cfg.RSI_MOMENTUM_LOW
        and rel_vol is not None and rel_vol > 1.0
        and distance_pct is not None and distance_pct > -5  # dalam 5% dari resistance
    ):
        return "SIAGA"

    # --- MODE A: RADAR -- base/sideways, belum wajib breakout ---
    if (
        comp["base"]["raw"] > 0
        and last_rsi is not None and 45 <= last_rsi <= 60
    ):
        return "RADAR"

    return None
