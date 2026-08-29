"""
Entry point buat menjalankan Early Breakout Screener, dijadwalkan otomatis
2x sehari (lihat .github/workflows/breakout-screener.yml):
- 15:30 WIB (sebelum market tutup)
- 20:00 WIB (setelah market tutup total, data foreign flow final)

Penggunaan manual:
    python run_breakout_screener.py              # print dashboard ke terminal
    python run_breakout_screener.py --telegram    # sekalian kirim ringkasan ke Telegram
"""

import sys

from breakout_screener import config as cfg
from breakout_screener.screener import screen_tickers, group_by_dashboard, format_table
from idx_tickers import get_idx_tickers
from foreign_flow import get_foreign_flow, format_rupiah
from bumn_list import is_bumn

TOP_FOREIGN_N = 20


def print_dashboard(dashboard):
    """Bagian 21 -- dashboard RADAR / SIAGA / ENTRY / OVEREXTENDED."""
    for section in ["ENTRY", "SIAGA", "RADAR", "OVEREXTENDED"]:
        items = dashboard[section]
        print(f"\n=== {section} ({len(items)} saham) ===")
        if items:
            print(format_table(items, top_n=15))
        else:
            print("(kosong)")


def get_foreign_bumn_flow():
    """Ambil data net foreign buy/sell hari ini, pisahkan top buy & top sell."""
    flow = get_foreign_flow()
    if not flow:
        return None, None
    top_buy = sorted(flow.items(), key=lambda x: x[1]["net_foreign"], reverse=True)
    top_buy = [(c, f) for c, f in top_buy if f["net_foreign"] > 0][:TOP_FOREIGN_N]
    top_sell = sorted(flow.items(), key=lambda x: x[1]["net_foreign"])
    top_sell = [(c, f) for c, f in top_sell if f["net_foreign"] < 0][:TOP_FOREIGN_N]
    return top_buy, top_sell


def print_foreign_bumn_section(top_buy, top_sell):
    print("\n=== DANA ASING & BUMN: MASUK/KELUAR ===")
    if top_buy is None:
        print("(Data foreign flow tidak berhasil diambil)")
        return
    print("\n-- Masuk (Net Buy) --")
    for code, f in top_buy:
        tag = " [BUMN]" if is_bumn(code) else ""
        print(f"  {code}{tag}: +{format_rupiah(f['net_foreign'])}")
    print("\n-- Keluar (Net Sell) --")
    for code, f in top_sell:
        tag = " [BUMN]" if is_bumn(code) else ""
        print(f"  {code}{tag}: -{format_rupiah(abs(f['net_foreign']))}")


def main():
    tickers = get_idx_tickers()
    print(f"[breakout_screener] Screening {len(tickers)} saham, histori {cfg.HISTORY_DAYS_LIVE} hari...")
    results = screen_tickers(tickers)
    print(f"[breakout_screener] {len(results)} saham lolos filter likuiditas.")

    dashboard = group_by_dashboard(results)
    print_dashboard(dashboard)

    top_buy, top_sell = get_foreign_bumn_flow()
    print_foreign_bumn_section(top_buy, top_sell)

    if results:
        print(f"\n[breakout_screener] Data candle terakhir: {results[0]['last_candle_date']}")

    if "--telegram" in sys.argv:
        from notifier import send_telegram_message
        lines = ["📊 *Early Breakout Screener*", ""]
        for section in ["ENTRY", "SIAGA", "RADAR"]:
            items = dashboard[section][:10]
            if not items:
                continue
            lines.append(f"*{section}*")
            for r in items:
                warn = f" ⚠️ {', '.join(r['warnings'])}" if r["warnings"] else ""
                lines.append(f"• {r['ticker']} @ {r['price']} - Score {r['score']} ({r['category']}){warn}")
            lines.append("")

        if top_buy:
            lines.append("*🌍 DANA ASING & BUMN MASUK (Net Buy)*")
            for code, f in top_buy:
                tag = " [BUMN]" if is_bumn(code) else ""
                lines.append(f"• {code}{tag}: +{format_rupiah(f['net_foreign'])}")
            lines.append("")

        if top_sell:
            lines.append("*🌍 DANA ASING & BUMN KELUAR (Net Sell)*")
            for code, f in top_sell:
                tag = " [BUMN]" if is_bumn(code) else ""
                lines.append(f"• {code}{tag}: -{format_rupiah(abs(f['net_foreign']))}")
            lines.append("")

        if top_buy is None:
            lines.append("_(Data foreign flow tidak berhasil diambil hari ini)_\n")

        lines.append(
            "_Sistem ini hanya menghasilkan ranking probabilitas setup teknikal, "
            "BUKAN jaminan saham akan naik. Bukan rekomendasi finansial. DYOR._"
        )
        send_telegram_message("\n".join(lines))


if __name__ == "__main__":
    main()
