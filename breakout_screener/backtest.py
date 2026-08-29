"""
Modul backtesting Early Breakout Screener (Bagian 18).

Simulasi WALK-FORWARD: pada tiap hari H, indikator & sinyal dihitung
HANYA memakai data sampai hari H (anti look-ahead bias, Bagian 19) --
dilakukan dengan cara memotong DataFrame ke df.iloc[:i+1] sebelum
menghitung ulang skor breakout di hari itu, bukan menghitung sekali di
seluruh data (yang akan membocorkan info masa depan lewat rolling
window yang menyentuh sisi kanan).

Aturan:
- BUY saat breakout_confirmed == True (Bagian 8)
- SELL saat salah satu dari: stop loss kena, target 1 kena,
  bearish MA cross (MA9 < MA26), atau melewati MAX_HOLDING_DAYS
"""

import pandas as pd

from . import config as cfg
from .breakout import compute_stop_loss, compute_targets
from .indicators import compute_indicators
from .scoring import score_breakout


def _is_breakout_confirmed_at(df_slice) -> bool:
    """Cek breakout_confirmed pakai data SAMPAI index terakhir df_slice saja."""
    breakout_info = score_breakout(df_slice)
    return breakout_info.get("breakout_confirmed", False)


def backtest_ticker(df: pd.DataFrame, min_history: int = 60) -> list:
    """
    df: data harian mentah (Open, High, Low, Close, Volume), idealnya
    2-5 tahun kalau tersedia (Bagian 18).

    Return: list of trade dict {entry_date, entry_price, exit_date,
    exit_price, return_pct, holding_days, exit_reason, is_false_breakout}.
    """
    df_ind_full = compute_indicators(df)
    trades = []
    in_position = False
    entry_idx = None
    entry_price = None
    stop_loss = None
    target1 = None

    n = len(df_ind_full)
    for i in range(min_history, n):
        window = df_ind_full.iloc[: i + 1]  # HANYA data sampai hari ke-i
        today = window.iloc[-1]

        if not in_position:
            if _is_breakout_confirmed_at(window):
                in_position = True
                entry_idx = i
                entry_price = float(today["Close"])
                sl_info = compute_stop_loss(window)
                stop_loss = sl_info.get("stop_loss")
                tgt_info = compute_targets(window, stop_loss)
                target1 = tgt_info.get("target1")
        else:
            holding_days = i - entry_idx
            close = float(today["Close"])
            ma9 = today["MA9"]
            ma26 = today["MA26"]
            bearish_cross = (
                pd.notna(ma9) and pd.notna(ma26) and
                pd.notna(df_ind_full["MA9"].iloc[i - 1]) and pd.notna(df_ind_full["MA26"].iloc[i - 1]) and
                df_ind_full["MA9"].iloc[i - 1] >= df_ind_full["MA26"].iloc[i - 1] and
                ma9 < ma26
            )

            exit_reason = None
            if stop_loss is not None and close <= stop_loss:
                exit_reason = "STOP_LOSS"
            elif target1 is not None and close >= target1:
                exit_reason = "TARGET_HIT"
            elif bearish_cross:
                exit_reason = "BEARISH_MA_CROSS"
            elif holding_days >= cfg.MAX_HOLDING_DAYS:
                exit_reason = "MAX_HOLDING_PERIOD"

            if exit_reason:
                return_pct = (close - entry_price) / entry_price * 100
                is_false_breakout = exit_reason == "STOP_LOSS" and holding_days <= cfg.FALSE_BREAKOUT_WINDOW_DAYS
                trades.append({
                    "entry_date": str(df_ind_full.index[entry_idx].date()),
                    "entry_price": round(entry_price, 2),
                    "exit_date": str(df_ind_full.index[i].date()),
                    "exit_price": round(close, 2),
                    "return_pct": round(return_pct, 2),
                    "holding_days": holding_days,
                    "exit_reason": exit_reason,
                    "is_false_breakout": is_false_breakout,
                })
                in_position = False
                entry_idx = None
                stop_loss = None
                target1 = None

    return trades


def summarize_trades(all_trades: list) -> dict:
    """Bagian 18 -- ringkasan metrik backtest: win rate, avg return, max
    drawdown, profit factor, avg holding period, jumlah trade, false
    breakout rate."""
    if not all_trades:
        return {"number_of_trades": 0}

    n = len(all_trades)
    wins = [t for t in all_trades if t["return_pct"] > 0]
    losses = [t for t in all_trades if t["return_pct"] <= 0]
    win_rate = len(wins) / n * 100
    avg_return = sum(t["return_pct"] for t in all_trades) / n
    avg_holding = sum(t["holding_days"] for t in all_trades) / n
    false_breakouts = sum(1 for t in all_trades if t["is_false_breakout"])
    false_breakout_rate = false_breakouts / n * 100

    gross_profit = sum(t["return_pct"] for t in wins)
    gross_loss = abs(sum(t["return_pct"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # Max drawdown dari equity curve kumulatif (asumsi compounding sederhana,
    # posisi full-size tiap trade -- bukan simulasi position sizing riil)
    equity = 100.0
    peak = equity
    max_dd = 0.0
    for t in all_trades:
        equity *= (1 + t["return_pct"] / 100)
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100
        max_dd = max(max_dd, dd)

    return {
        "number_of_trades": n,
        "win_rate_pct": round(win_rate, 1),
        "avg_return_pct": round(avg_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "avg_holding_days": round(avg_holding, 1),
        "false_breakout_rate_pct": round(false_breakout_rate, 1),
    }
