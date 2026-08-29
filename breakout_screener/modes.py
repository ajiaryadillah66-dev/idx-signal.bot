"""
Klasifikasi 4 mode screening: RADAR, SIAGA, ENTRY (Bagian 14 -- spek asli
ISAT/TMPO, fokus breakout ke atas), dan BOUNCE (TAMBAHAN, filosofi beda:
support-based entry, bukan breakout).

Prioritas pengecekan: ENTRY > SIAGA > RADAR > BOUNCE -- satu saham dicek
dari level paling matang dulu (breakout dulu), BOUNCE dicek PALING AKHIR
karena filosofinya beda arah (beli di support, bukan breakout ke atas) --
biar gak menimpa sinyal breakout yang lebih kuat kalau kebetulan dua-duanya
kena.
"""

from . import config as cfg


def classify_mode(df, score_result: dict, bounce_info: dict = None) -> str:
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

    # --- MODE D: BOUNCE -- support-based, dicek PALING AKHIR ---
    if bounce_info is not None and bounce_info.get("is_bounce_setup"):
        return "BOUNCE"

    return None
