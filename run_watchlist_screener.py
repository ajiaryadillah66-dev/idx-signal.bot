"""
Laporan gabungan khusus untuk watchlist saham pilihan (lihat watchlist.py)
-- menggabungkan 2 sistem screening yang sudah dibangun:

1. 5 kriteria dari signals.py (support+candle, doji/hammer, reversal
   merah->hijau, RSI oversold)
2. Scoring 0-100 dari breakout_screener (RADAR/SIAGA/ENTRY/BOUNCE +
   risk management: entry zone, stop loss, target, risk/reward)

Plus data foreign flow & tag BUMN.

TIDAK melalui filter likuiditas breakout_screener -- semua saham di
watchlist SELALU tampil apa adanya, karena ini daftar pilihan manual,
bukan hasil scan otomatis semua saham IDX.

Dijadwalkan otomatis 2x sehari (lihat .github/workflows/watchlist-screener.yml):
- 15:30 WIB (sore, sebelum market tutup)
- 20:00 WIB (malam, setelah market tutup total)

Penggunaan manual:
    python run_watchlist_screener.py
    python run_watchlist_screener.py --telegram
"""

import sys
import time

import yfinance as yf

from watchlist import WATCHLIST_TICKERS
from signals import (
    detect_support_with_reversal_candle,
    detect_bullish_candle_pattern,
    detect_red_to_green_volume_reversal,
    get_last_rsi,
)
from breakout_screener.indicators import compute_indicators
from breakout_screener.scoring import compute_total_score, score_support_bounce
from breakout_screener.modes import classify_mode
from breakout_screener.breakout import compute_stop_loss, compute_targets, compute_entry_zone
from foreign_flow import get_foreign_flow, format_rupiah
from bumn_list import is_bumn
from notifier import send_telegram_message

HISTORY_PERIOD = "200d"  # cukup buat MA50 (breakout_screener) & semua kriteria signals.py


def analyze_ticker(ticker_no_suffix: str, foreign_flow: dict) -> dict:
    """Jalankan 5 kriteria + scoring breakout untuk 1 saham watchlist."""
    ticker = f"{ticker_no_suffix}.JK"
    try:
        df = yf.download(ticker, period=HISTORY_PERIOD, interval="1d", progress=False)
        df = df.dropna(how="all")
    except Exception as e:
        return {"ticker": ticker_no_suffix, "error": f"Gagal download: {e}"}

    if df.empty:
        return {"ticker": ticker_no_suffix, "error": "Data tidak ditemukan (cek kode saham/suspend)"}
    if len(df) < 55:
        return {"ticker": ticker_no_suffix, "error": f"Histori kurang ({len(df)} hari, butuh minimal 55)"}

    # --- 5 kriteria (signals.py) ---
    criteria_hits = []

    sc = detect_support_with_reversal_candle(df)
    if sc:
        criteria_hits.append(
            f"Support+Candle ({sc['candle']} di {sc['support_level']}, jarak {sc['distance_pct']}%)"
        )

    cp = detect_bullish_candle_pattern(df)
    if cp:
        criteria_hits.append("; ".join(cp["patterns"]))

    rtg = detect_red_to_green_volume_reversal(df)
    if rtg:
        criteria_hits.append(f"Reversal merah->hijau (volume +{rtg['volume_increase_pct']}%)")

    last_rsi_simple = get_last_rsi(df)
    if last_rsi_simple is not None and last_rsi_simple < 30:
        criteria_hits.append(f"RSI oversold ({last_rsi_simple:.1f})")

    # --- Scoring breakout 0-100 (breakout_screener) ---
    df_ind = compute_indicators(df)
    score_result = compute_total_score(df_ind)
    bounce_info = score_support_bounce(df_ind)
    mode = classify_mode(df_ind, score_result, bounce_info)

    stop_loss_info = compute_stop_loss(df_ind)
    target_info = compute_targets(df_ind, stop_loss_info.get("stop_loss"))
    entry_info = compute_entry_zone(
        df_ind, score_result["components"]["breakout"], score_result["components"]["overextended"]
    )

    flow = foreign_flow.get(ticker_no_suffix)

    last = df_ind.iloc[-1]
    return {
        "ticker": ticker_no_suffix,
        "error": None,
        "price": round(float(last["Close"]), 2),
        "is_bumn": is_bumn(ticker_no_suffix),
        "foreign_flow": flow,
        "criteria_hits": criteria_hits,
        "score": score_result["score"],
        "category": score_result["category"],
        "mode": mode,
        "bounce_details": bounce_info.get("details", []) if bounce_info else [],
        "warnings": score_result["components"]["overextended"].get("warnings", []),
        "entry_zone": entry_info.get("entry_zone"),
        "stop_loss": stop_loss_info.get("stop_loss"),
        "target1": target_info.get("target1"),
        "target2": target_info.get("target2"),
        "risk_reward": target_info.get("risk_reward"),
    }


def format_report(results: list) -> str:
    lines = ["📋 *Laporan Watchlist Gabungan*", ""]

    for r in results:
        tag = " [BUMN]" if r.get("is_bumn") else ""
        lines.append(f"*{r['ticker']}{tag}*")

        if r.get("error"):
            lines.append(f"  ⚠️ {r['error']}")
            lines.append("")
            continue

        lines.append(f"  Harga: {r['price']}")
        lines.append(f"  Skor Breakout: {r['score']}/100 ({r['category']}) - Mode: {r['mode'] or '-'}")

        if r["criteria_hits"]:
            for hit in r["criteria_hits"]:
                lines.append(f"  ✅ {hit}")
        else:
            lines.append("  (tidak ada dari 5 kriteria yang kena hari ini)")

        if r["mode"] == "BOUNCE" and r["bounce_details"]:
            lines.append(f"  🎯 Bounce: {'; '.join(r['bounce_details'])}")

        if r["foreign_flow"]:
            net = r["foreign_flow"]["net_foreign"]
            arah = "net buy" if net > 0 else "net sell"
            lines.append(f"  Asing: {arah} {format_rupiah(abs(net))}")

        if r["warnings"]:
            lines.append(f"  ⚠️ {', '.join(r['warnings'])}")

        lines.append(
            f"  Entry: {r['entry_zone']} | SL: {r['stop_loss']} | "
            f"TP1: {r['target1']} | R:R: {r['risk_reward']}"
        )
        lines.append("")

    lines.append("_Sistem breakout hanya ranking probabilitas setup teknikal, bukan jaminan. Bukan rekomendasi finansial. DYOR._")
    return "\n".join(lines)


def main():
    print(f"[watchlist] Analisa {len(WATCHLIST_TICKERS)} saham watchlist...")
    foreign_flow = get_foreign_flow()

    results = []
    for t in WATCHLIST_TICKERS:
        print(f"[watchlist] Proses {t}...")
        results.append(analyze_ticker(t, foreign_flow))
        time.sleep(1)  # sopan-sopan ke server yfinance

    report = format_report(results)
    print(report)

    if "--telegram" in sys.argv:
        send_telegram_message(report)


if __name__ == "__main__":
    main()
