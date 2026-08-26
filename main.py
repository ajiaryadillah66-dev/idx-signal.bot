"""
Screener saham IDX (rebuild dari awal) -- jalan tiap 1 jam selama jam
trading (09:00, 10:00, 11:00, 13:00, 14:00, 15:00 WIB), cek 5 kriteria,
dan kirim notifikasi Telegram SETIAP KALI ada saham yang kena kriteria.

TIDAK ADA dedup/state -- saham yang sama bisa muncul lagi di jam
berikutnya kalau masih memenuhi kriteria (sesuai permintaan).

Kriteria yang dicek:
1. Support + candle Doji/Hammer
2. Candle Doji/Hammer (setelah downtrend / sideway ~1 minggu / ~1 bulan)
3. Reversal candle merah->hijau + volume naik dari rata-rata 1 minggu
4. RSI rendah (oversold, < 30)
5. Dibeli asing & BUMN (net foreign buy positif, ditandai [BUMN])

Penggunaan manual:
    python main.py
"""

import time
import yfinance as yf

from idx_tickers import get_idx_tickers
from signals import (
    detect_bullish_candle_pattern,
    detect_support_with_reversal_candle,
    detect_red_to_green_volume_reversal,
    get_last_rsi,
)
from notifier import send_telegram_message
from foreign_flow import get_foreign_flow, format_rupiah
from bumn_list import is_bumn

BATCH_SIZE = 50
HISTORY_PERIOD = "6mo"
RSI_OVERSOLD_THRESHOLD = 30
TOP_FOREIGN_BUY_N = 20


def _download_batches(tickers, period=HISTORY_PERIOD, interval="1d"):
    all_data = {}
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        try:
            data = yf.download(
                batch, period=period, interval=interval,
                group_by="ticker", progress=False, threads=True,
            )
        except Exception as e:
            print(f"[main] Gagal download batch {batch}: {e}")
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


def _tag_bumn(code_short: str) -> str:
    return " [BUMN]" if is_bumn(code_short) else ""


def run_screener(tickers):
    raw = _download_batches(tickers)
    results = {
        "support_candle": {},
        "candle_pattern": {},
        "red_to_green": {},
        "rsi_oversold": {},
    }
    for t, df in raw.items():
        sc = detect_support_with_reversal_candle(df)
        if sc:
            results["support_candle"][t] = sc

        cp = detect_bullish_candle_pattern(df)
        if cp:
            results["candle_pattern"][t] = cp

        rtg = detect_red_to_green_volume_reversal(df)
        if rtg:
            results["red_to_green"][t] = rtg

        rsi = get_last_rsi(df)
        if rsi is not None and rsi < RSI_OVERSOLD_THRESHOLD:
            results["rsi_oversold"][t] = {
                "last_close": round(float(df["Close"].iloc[-1]), 2),
                "rsi": round(rsi, 1),
            }
    return results


def format_message(results: dict, foreign_flow: dict) -> str:
    lines = ["📡 *Screening Saham IDX*", ""]
    any_result = False

    def section(title, items, line_fn):
        nonlocal any_result
        if not items:
            return
        any_result = True
        lines.append(f"*{title}*")
        for code, info in sorted(items.items()):
            code_short = code.replace(".JK", "")
            lines.append(f"• {line_fn(code_short, info)}{_tag_bumn(code_short)}")
        lines.append("")

    section(
        "🎯 SUPPORT + CANDLE REVERSAL", results["support_candle"],
        lambda c, i: f"{c} @ {i['last_close']} - candle {i['candle']} di support {i['support_level']} (jarak {i['distance_pct']}%)",
    )
    section(
        "🕯️ CANDLE DOJI/HAMMER", results["candle_pattern"],
        lambda c, i: f"{c} @ {i['last_close']} - {'; '.join(i['patterns'])}",
    )
    section(
        "🔄 REVERSAL MERAH KE HIJAU", results["red_to_green"],
        lambda c, i: f"{c} @ {i['last_close']} - volume +{i['volume_increase_pct']}% dari rata-rata 1 minggu",
    )
    section(
        "📉 RSI RENDAH (OVERSOLD)", results["rsi_oversold"],
        lambda c, i: f"{c} @ {i['last_close']} - RSI {i['rsi']}",
    )

    if foreign_flow:
        top_buy = sorted(foreign_flow.items(), key=lambda x: x[1]["net_foreign"], reverse=True)
        top_buy = [(c, f) for c, f in top_buy if f["net_foreign"] > 0][:TOP_FOREIGN_BUY_N]
        if top_buy:
            any_result = True
            lines.append("*🌍 DIBELI ASING & BUMN*")
            for code, f in top_buy:
                lines.append(f"• {code}{_tag_bumn(code)}: net buy +{format_rupiah(f['net_foreign'])}")
            lines.append("")

    if not any_result:
        lines.append("Tidak ada saham yang memenuhi kriteria saat ini.")

    lines.append("_Bukan rekomendasi finansial. DYOR._")
    return "\n".join(lines)


def main():
    tickers = get_idx_tickers()
    print(f"[main] Screening {len(tickers)} saham...")
    results = run_screener(tickers)
    foreign_flow = get_foreign_flow()
    message = format_message(results, foreign_flow)
    print(message)
    send_telegram_message(message)


if __name__ == "__main__":
    main()
