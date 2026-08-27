"""
Entry point buat menjalankan Early Breakout Screener secara manual,
terpisah dari bot notifikasi jam-jaman yang sudah ada (main.py).

Penggunaan:
    python run_breakout_screener.py              # print dashboard ke terminal
    python run_breakout_screener.py --telegram    # sekalian kirim ringkasan ke Telegram
"""

import sys

from breakout_screener import config as cfg
from breakout_screener.screener import screen_tickers, group_by_dashboard, format_table
from idx_tickers import get_idx_tickers


def print_dashboard(dashboard):
    """Bagian 21 -- dashboard RADAR / SIAGA / ENTRY / OVEREXTENDED."""
    for section in ["ENTRY", "SIAGA", "RADAR", "OVEREXTENDED"]:
        items = dashboard[section]
        print(f"\n=== {section} ({len(items)} saham) ===")
        if items:
            print(format_table(items, top_n=15))
        else:
            print("(kosong)")


def main():
    tickers = get_idx_tickers()
    print(f"[breakout_screener] Screening {len(tickers)} saham, histori {cfg.HISTORY_DAYS_LIVE} hari...")
    results = screen_tickers(tickers)
    print(f"[breakout_screener] {len(results)} saham lolos filter likuiditas.")

    dashboard = group_by_dashboard(results)
    print_dashboard(dashboard)

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
        lines.append(
            "_Sistem ini hanya menghasilkan ranking probabilitas setup teknikal, "
            "BUKAN jaminan saham akan naik. Bukan rekomendasi finansial. DYOR._"
        )
        send_telegram_message("\n".join(lines))


if __name__ == "__main__":
    main()
