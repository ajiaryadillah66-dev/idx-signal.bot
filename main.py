"""
Script utama: screening seluruh saham IDX, hitung sinyal, kirim ke Telegram.

Mode:
- "evening"  : jam 15:30 WIB (market masih buka, sebelum tutup) -> prediksi
               saham yang kemungkinan masih lanjut naik besok (BUY / REBOUND WATCH)
- "reversal" : jam 15:40 WIB -> saham yang kemarin merah lalu hari ini
               hijau, dibarengi volume di atas rata-rata 1 minggu terakhir
- "morning"  : jam 08:15 WIB (sebelum market buka) -> cek sinyal SELL/overbought
               + pola candle Doji/Hammer + data foreign flow final kemarin
- "intraday" : mode manual (gak lagi terjadwal otomatis) -> alert real-time
               begitu ada saham yang mulai bullish hari itu

Penggunaan manual:
    python main.py evening
    python main.py reversal
    python main.py morning
    python main.py intraday
"""

import sys
import time
import yfinance as yf

from idx_tickers import get_idx_tickers
from signals import (
    compute_indicators, classify_signal,
    compute_intraday_indicators, classify_intraday_bullish,
    detect_bullish_candle_pattern, detect_red_to_green_volume_reversal,
)
from notifier import send_telegram_message
from state_store import load_notified_today, save_notified_today
from foreign_flow import get_foreign_flow, format_rupiah, get_previous_trading_day_str
from bumn_list import is_bumn
from market_context import get_ihsg_trend
from bsjp_confidence import score_confidence

BATCH_SIZE = 50
HISTORY_PERIOD = "6mo"


def _download_batches(tickers, period, interval):
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


def run_daily_screening(tickers, detect_candles=False):
    """Dipakai untuk mode evening & morning (basis data harian).
    Kalau detect_candles=True (mode pagi), sekalian scan pola candle
    Doji/Hammer bullish reversal di semua saham (bukan cuma yang punya
    sinyal teknikal lain), pakai data yang sama tanpa download ulang."""
    raw = _download_batches(tickers, HISTORY_PERIOD, "1d")
    results = {}
    candle_patterns = {}
    for t, df in raw.items():
        df_ind = compute_indicators(df)
        res = classify_signal(df_ind)
        if res["signal"]:
            results[t] = res
        if detect_candles:
            cp = detect_bullish_candle_pattern(df)
            if cp:
                candle_patterns[t] = cp
    return results, candle_patterns


def run_intraday_scan(tickers):
    """Dipakai untuk mode intraday (basis data 15 menit, hanya sinyal bullish baru)."""
    raw = _download_batches(tickers, "5d", "15m")
    already_notified = load_notified_today()
    new_bullish = {}

    for t, df in raw.items():
        if t in already_notified:
            continue
        df_ind = compute_intraday_indicators(df)
        res = classify_intraday_bullish(df_ind)
        if res["bullish"]:
            new_bullish[t] = res
            already_notified.add(t)

    save_notified_today(already_notified)
    return new_bullish


def run_reversal_scan(tickers):
    """Dipakai untuk mode reversal (jam 15:40): saham merah->hijau + volume naik."""
    raw = _download_batches(tickers, HISTORY_PERIOD, "1d")
    results = {}
    for t, df in raw.items():
        r = detect_red_to_green_volume_reversal(df)
        if r:
            results[t] = r
    return results


def format_reversal_message(results: dict, foreign_flow: dict = None) -> str:
    foreign_flow = foreign_flow or {}
    lines = ["🔄 *15:40 WIB - Reversal Merah ke Hijau + Volume Naik*", ""]
    if results:
        for code, info in sorted(results.items(), key=lambda x: -x[1]["volume_increase_pct"]):
            code_short = code.replace(".JK", "")
            tag = _tag_suffix(code_short, foreign_flow)
            lines.append(
                f"• {code_short} @ {info['last_close']} - volume +{info['volume_increase_pct']}% "
                f"dari rata-rata 1 minggu terakhir{tag}"
            )
    else:
        lines.append("Tidak ada saham yang memenuhi kriteria hari ini.")
    lines.append("\n_Bukan rekomendasi finansial. DYOR._")
    return "\n".join(lines)


def _tag_suffix(code_no_suffix: str, foreign_flow: dict) -> str:
    """Bikin tag tambahan '[BUMN]' dan/atau info net foreign buy/sell."""
    tags = []
    if is_bumn(code_no_suffix):
        tags.append("BUMN")
    flow = foreign_flow.get(code_no_suffix)
    if flow:
        net = flow["net_foreign"]
        if net > 0:
            tags.append(f"asing net buy {format_rupiah(net)}")
        elif net < 0:
            tags.append(f"asing net sell {format_rupiah(abs(net))}")
    return f" [{', '.join(tags)}]" if tags else ""


def format_daily_message(results: dict, mode: str, foreign_flow: dict = None, ihsg: dict = None,
                          candle_patterns: dict = None) -> str:
    foreign_flow = foreign_flow or {}
    ihsg = ihsg or {"trend": "unknown"}
    candle_patterns = candle_patterns or {}
    buys = {k: v for k, v in results.items() if v["signal"] == "BUY"}
    rebounds = {k: v for k, v in results.items() if v["signal"] == "REBOUND_WATCH"}
    sells = {k: v for k, v in results.items() if v["signal"] == "SELL"}

    lines = []

    def section_plain(title, items):
        if not items:
            return
        lines.append(f"*{title}*")
        for code, info in sorted(items.items()):
            reasons = "; ".join(info["reasons"])
            code_short = code.replace(".JK", "")
            tag = _tag_suffix(code_short, foreign_flow)
            lines.append(f"• {code_short} @ {info['last_close']} (RSI {info['rsi']}) - {reasons}{tag}")
        lines.append("")

    def section_with_confidence(title, items):
        """Khusus BUY & REBOUND WATCH di laporan sore: dikasih skor confidence & di-sort."""
        if not items:
            return
        scored = []
        for code, info in items.items():
            code_short = code.replace(".JK", "")
            conf = score_confidence(code_short, info, foreign_flow, ihsg["trend"])
            scored.append((code_short, info, conf))

        order = {"Tinggi": 0, "Sedang": 1, "Rendah": 2}
        scored.sort(key=lambda x: (order[x[2]["level"]], x[0]))

        lines.append(f"*{title}*")
        for code_short, info, conf in scored:
            reasons = "; ".join(info["reasons"])
            bumn_tag = " [BUMN]" if is_bumn(code_short) else ""
            flow = foreign_flow.get(code_short)
            flow_tag = ""
            if flow:
                flow_tag = f", asing net {'buy' if flow['net_foreign'] > 0 else 'sell'} {format_rupiah(abs(flow['net_foreign']))}"
            lines.append(f"• {code_short} @ {info['last_close']} (RSI {info['rsi']}) - Confidence: *{conf['level']}*{bumn_tag}{flow_tag}")
            lines.append(f"   _{reasons}_")
            if conf["cautions"]:
                lines.append(f"   ⚠️ {'; '.join(conf['cautions'])}")
        lines.append("")

    if mode == "evening":
        # Sore: fokus HANYA ke kemungkinan saham masih naik besok -> BUY & REBOUND WATCH saja
        lines.append("🌆 *15:30 WIB - Prediksi Saham Lanjut Naik Besok*")
        if ihsg["trend"] != "unknown":
            lines.append(f"_Kondisi IHSG hari ini: {ihsg['trend'].upper()}_")
        lines.append("")
        section_with_confidence("✅ BUY", buys)
        section_with_confidence("👀 REBOUND WATCH", rebounds)
        if not (buys or rebounds):
            lines.append("Tidak ada saham dengan potensi lanjut naik besok.")
    else:
        # Pagi: fokus HANYA ke sinyal jual/overbought
        lines.append("🌅 *PAGI - Screening Jual/Overbought*")
        lines.append("")
        section_plain("🔻 SELL / OVERBOUGHT", sells)
        if not sells:
            lines.append("Tidak ada sinyal jual/overbought signifikan.")

        # Section baru: pola candle Doji/Hammer bullish reversal (candle kemarin)
        if candle_patterns:
            lines.append("*🕯️ CANDLE BULLISH REVERSAL (kemarin)*")
            for code, cp in sorted(candle_patterns.items()):
                code_short = code.replace(".JK", "")
                tag = _tag_suffix(code_short, foreign_flow)
                patterns_str = "; ".join(cp["patterns"])
                lines.append(f"• {code_short} @ {cp['last_close']} - {patterns_str}{tag}")
            lines.append("")

    # Section foreign flow: sore pakai data hari itu (masih live saat market
    # buka), pagi pakai data hari sebelumnya yang SUDAH FINAL setelah market
    # tutup -- makanya di laporan pagi datanya lebih lengkap & lebih akurat.
    top_n = 5 if mode == "evening" else 20
    if foreign_flow:
        top_buy = sorted(foreign_flow.items(), key=lambda x: x[1]["net_foreign"], reverse=True)[:top_n]
        top_buy = [(c, f) for c, f in top_buy if f["net_foreign"] > 0]
        top_sell = sorted(foreign_flow.items(), key=lambda x: x[1]["net_foreign"])[:top_n]
        top_sell = [(c, f) for c, f in top_sell if f["net_foreign"] < 0]

        data_note = "data FINAL kemarin (market sudah tutup)" if mode == "morning" else "data hari ini (masih berjalan)"
        lines.append(f"*🌍 TOP NET FOREIGN BUY* _({data_note})_")
        if top_buy:
            for code, f in top_buy:
                bumn_tag = " [BUMN]" if is_bumn(code) else ""
                lines.append(f"• {code}{bumn_tag}: +{format_rupiah(f['net_foreign'])}")
        else:
            lines.append("Tidak ada net foreign buy signifikan.")
        lines.append("")

        lines.append(f"*🌍 TOP NET FOREIGN SELL* _({data_note})_")
        if top_sell:
            for code, f in top_sell:
                bumn_tag = " [BUMN]" if is_bumn(code) else ""
                lines.append(f"• {code}{bumn_tag}: -{format_rupiah(abs(f['net_foreign']))}")
        else:
            lines.append("Tidak ada net foreign sell signifikan.")
        lines.append("")
    else:
        lines.append("_(Data foreign flow tidak berhasil diambil, laporan tetap lanjut tanpa data ini.)_\n")

    lines.append("_Bukan rekomendasi finansial. DYOR._")
    return "\n".join(lines)


def format_intraday_message(results: dict) -> str:
    lines = ["⚡ *ALERT: Mulai Bullish Hari Ini*", ""]
    for code, info in sorted(results.items()):
        reasons = "; ".join(info["reasons"])
        lines.append(f"• {code.replace('.JK','')} @ {info['last_price']} (RSI {info['rsi']}) - {reasons}")
    lines.append("\n_Bukan rekomendasi finansial. DYOR._")
    return "\n".join(lines)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "evening"
    tickers = get_idx_tickers()
    print(f"[main] Mode={mode}, total saham dipantau: {len(tickers)}")

    if mode == "intraday":
        results = run_intraday_scan(tickers)
        if results:
            message = format_intraday_message(results)
            print(message)
            send_telegram_message(message)
        else:
            print("[main] Tidak ada sinyal bullish baru saat ini.")
        return

    if mode == "reversal":
        results = run_reversal_scan(tickers)
        foreign_flow = get_foreign_flow()
        message = format_reversal_message(results, foreign_flow)
        print(message)
        send_telegram_message(message)
        return

    results, candle_patterns = run_daily_screening(tickers, detect_candles=(mode == "morning"))

    # Foreign flow: sore pakai data hari ini (masih live), pagi pakai data
    # hari trading terakhir (sudah final karena market sudah tutup semalam)
    if mode == "evening":
        foreign_flow = get_foreign_flow()
    elif mode == "morning":
        foreign_flow = get_foreign_flow(date_str=get_previous_trading_day_str())
    else:
        foreign_flow = {}

    ihsg = get_ihsg_trend() if mode == "evening" else None
    message = format_daily_message(results, mode, foreign_flow, ihsg, candle_patterns)
    print(message)
    send_telegram_message(message)


if __name__ == "__main__":
    main()
