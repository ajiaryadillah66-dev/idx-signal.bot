"""
Entry point untuk menjalankan backtest Early Breakout Screener (Bagian 18).

Penggunaan:
    python run_backtest.py BBCA          # backtest 1 saham
    python run_backtest.py --all         # backtest semua saham IDX (LAMA! bisa puluhan menit)
"""

import sys

import yfinance as yf

from breakout_screener import config as cfg
from breakout_screener.backtest import backtest_ticker, summarize_trades
from idx_tickers import get_idx_tickers


def backtest_single(ticker):
    print(f"[backtest] Mengunduh data {ticker} ({cfg.HISTORY_PERIOD_BACKTEST})...")
    df = yf.download(ticker, period=cfg.HISTORY_PERIOD_BACKTEST, interval="1d", progress=False)
    df = df.dropna(how="all")
    if df.empty:
        print(f"[backtest] Tidak ada data untuk {ticker}.")
        return []
    trades = backtest_ticker(df)
    print(f"[backtest] {ticker}: {len(trades)} trade ditemukan.")
    return trades


def main():
    if len(sys.argv) < 2:
        print("Penggunaan: python run_backtest.py <TICKER> atau --all")
        return

    all_trades = []
    if sys.argv[1] == "--all":
        tickers = get_idx_tickers()
        for t in tickers:
            all_trades.extend(backtest_single(t))
    else:
        ticker = sys.argv[1].upper()
        if not ticker.endswith(".JK"):
            ticker += ".JK"
        all_trades = backtest_single(ticker)

    summary = summarize_trades(all_trades)
    print("\n=== HASIL BACKTEST ===")
    for k, v in summary.items():
        print(f"{k}: {v}")

    if all_trades:
        print("\n=== CONTOH TRADE (5 TERAKHIR) ===")
        for t in all_trades[-5:]:
            print(t)


if __name__ == "__main__":
    main()
