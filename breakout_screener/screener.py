"""
Orkestrasi utama Early Breakout Screener: download data, filter
likuiditas, hitung indikator & skor, klasifikasi mode, susun tabel output.
"""

import time

import pandas as pd
import yfinance as yf

from . import config as cfg
from .breakout import compute_entry_zone, compute_stop_loss, compute_targets
from .indicators import compute_indicators
from .modes import classify_mode
from .scoring import compute_total_score, score_support_bounce

BATCH_SIZE = 50


def _download_batches(tickers, period, interval="1d"):
    all_data = {}
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        try:
            data = yf.download(
                batch, period=period, interval=interval,
                group_by="ticker", progress=False, threads=True,
            )
        except Exception as e:
            print(f"[breakout_screener] Gagal download batch {batch}: {e}")
            continue
        for t in batch:
            try:
                df = data[t] if len(batch) > 1 else data
                df = df.dropna(how="all")
                if not df.empty:
                    all_data[t] = df
            except Exception:
                continue
        time.sleep(1)  # sopan-sopan ke server yfinance
    return all_data


def passes_liquidity_filter(df) -> bool:
    """Bagian 2 -- filter likuiditas SEBELUM scoring, sesuai spek."""
    if len(df) < cfg.VOLUME_AVG_SHORT:
        return False
    avg_vol = df["Volume"].rolling(cfg.VOLUME_AVG_SHORT).mean().iloc[-1]
    avg_val = (df["Close"] * df["Volume"]).rolling(cfg.VOLUME_AVG_SHORT).mean().iloc[-1]
    price = df["Close"].iloc[-1]
    if pd.isna(avg_vol) or pd.isna(avg_val) or pd.isna(price):
        return False
    return avg_vol > cfg.MIN_AVG_VOLUME_20 and avg_val > cfg.MIN_AVG_VALUE_20 and price > cfg.MIN_PRICE


def screen_tickers(tickers, period=None):
    """
    Return list of dict, satu per saham yang lolos filter likuiditas &
    punya histori cukup, berisi skor, mode, dan info risk management.
    Diurutkan dari skor tertinggi.
    """
    period = period or f"{cfg.HISTORY_DAYS_LIVE}d"
    raw = _download_batches(tickers, period)
    results = []

    for t, df in raw.items():
        if len(df) < cfg.MA_50 + 5:  # butuh histori cukup untuk MA50 dst
            continue
        if not passes_liquidity_filter(df):
            continue

        df_ind = compute_indicators(df)
        score_result = compute_total_score(df_ind)
        bounce_info = score_support_bounce(df_ind)
        mode = classify_mode(df_ind, score_result, bounce_info)

        stop_loss_info = compute_stop_loss(df_ind)
        target_info = compute_targets(df_ind, stop_loss_info.get("stop_loss"))
        entry_info = compute_entry_zone(
            df_ind, score_result["components"]["breakout"], score_result["components"]["overextended"]
        )

        last = df_ind.iloc[-1]
        last_index = df_ind.index[-1]
        results.append({
            "ticker": t.replace(".JK", ""),
            "price": round(float(last["Close"]), 2),
            "score": score_result["score"],
            "category": score_result["category"],
            "mode": mode,
            "rsi": score_result["components"]["rsi"].get("last_rsi"),
            "ma9": round(float(last["MA9"]), 2) if pd.notna(last["MA9"]) else None,
            "ma26": round(float(last["MA26"]), 2) if pd.notna(last["MA26"]) else None,
            "relative_volume": score_result["components"]["volume"].get("relative_volume"),
            "resistance": score_result["components"]["breakout"].get("resistance"),
            "distance_pct": score_result["components"]["breakout"].get("distance_pct"),
            "breakout_confirmed": score_result["components"]["breakout"].get("breakout_confirmed"),
            "warnings": score_result["components"]["overextended"].get("warnings", []),
            "entry_zone": entry_info.get("entry_zone"),
            "stop_loss": stop_loss_info.get("stop_loss"),
            "risk_pct": stop_loss_info.get("risk_pct"),
            "target1": target_info.get("target1"),
            "target2": target_info.get("target2"),
            "risk_reward": target_info.get("risk_reward"),
            "last_candle_date": str(last_index.date()) if hasattr(last_index, "date") else str(last_index),
            "bounce_info": bounce_info,
            "components": score_result["components"],  # detail lengkap tiap kategori, buat debug
        })

    results.sort(key=lambda r: -r["score"])
    return results


def group_by_dashboard(results):
    """Bagian 21 (+ tambahan BOUNCE) -- kelompokkan hasil ke RADAR / SIAGA / ENTRY / BOUNCE / OVEREXTENDED."""
    dashboard = {"RADAR": [], "SIAGA": [], "ENTRY": [], "BOUNCE": [], "OVEREXTENDED": []}
    for r in results:
        if r["warnings"]:
            dashboard["OVEREXTENDED"].append(r)
        if r["mode"]:
            dashboard[r["mode"]].append(r)
    return dashboard


def format_table(results, top_n=20) -> str:
    """Bagian 15 -- format tabel output ringkas untuk mode RADAR/SIAGA/ENTRY (teks/markdown)."""
    header = (
        "Rank | Ticker | Price | Score | Setup | RSI | MA9 | MA26 | RelVol | "
        "Resist | Dist | Entry Zone | SL | Risk% | TP1 | TP2 | R:R | Warning"
    )
    lines = [header, "-" * len(header)]
    for i, r in enumerate(results[:top_n], start=1):
        warn = ", ".join(r["warnings"]) if r["warnings"] else "-"
        signal = "BREAKOUT" if r["breakout_confirmed"] else (r["mode"] or "-")
        lines.append(
            f"{i} | {r['ticker']} | {r['price']} | {r['score']} | {r['category']} | "
            f"{r['rsi']} | {r['ma9']} | {r['ma26']} | {r['relative_volume']}x | "
            f"{r['resistance']} | {r['distance_pct']}% | {r['entry_zone']} | "
            f"{r['stop_loss']} | {r['risk_pct']}% | {r['target1']} | {r['target2']} | "
            f"{r['risk_reward']} | {warn} | {signal}"
        )
    return "\n".join(lines)


def format_bounce_table(results, top_n=20) -> str:
    """
    Format tabel KHUSUS untuk mode BOUNCE -- kolomnya beda dari mode
    breakout (pakai support & jarak ke support, bukan resistance).
    """
    header = "Rank | Ticker | Price | Score | RSI | Support | Jarak | SL | TP1 | R:R | Alasan"
    lines = [header, "-" * len(header)]
    for i, r in enumerate(results[:top_n], start=1):
        bounce = r["bounce_info"]
        reasons = "; ".join(bounce["details"]) if bounce["details"] else "-"
        lines.append(
            f"{i} | {r['ticker']} | {r['price']} | {r['score']} | {r['rsi']} | "
            f"{bounce['support_level']} | {bounce['distance_pct']}% | {r['stop_loss']} | "
            f"{r['target1']} | {r['risk_reward']} | {reasons}"
        )
    return "\n".join(lines)
