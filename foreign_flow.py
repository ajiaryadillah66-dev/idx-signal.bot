"""
Modul pengambil data transaksi asing (foreign buy/sell) per saham dari IDX.

CATATAN: endpoint ini berdasarkan pola yang umum dipakai komunitas untuk
scraping "Ringkasan Saham" IDX, bukan dokumentasi API resmi publik. Kalau
IDX mengubah struktur endpoint/response-nya, fungsi ini bisa gagal -- makanya
ada penanganan error yang jelas, dan hasilnya di-skip (bukan bikin seluruh
laporan gagal) kalau data foreign flow tidak berhasil diambil.
"""

import requests
from datetime import datetime, timezone, timedelta

WIB = timezone(timedelta(hours=7))
STOCK_SUMMARY_ENDPOINT = "https://www.idx.co.id/primary/StockData/GetStockSummary"


def _today_str():
    return datetime.now(WIB).strftime("%Y%m%d")


def get_foreign_flow(date_str=None, timeout=20):
    """
    Mengembalikan dict {kode_saham: {"foreign_buy": ..., "foreign_sell": ...,
    "net_foreign": ..., "value": ...}} dalam Rupiah.

    kode_saham TANPA suffix ".JK" (mis. "BBCA"), biar gampang di-mapping ke
    hasil yfinance yang pakai suffix.

    Return dict kosong {} kalau gagal ambil data (bukan raise exception),
    supaya kegagalan sumber data ini tidak menggagalkan seluruh laporan.
    """
    date_str = date_str or _today_str()
    try:
        resp = requests.get(
            STOCK_SUMMARY_ENDPOINT,
            params={"date": date_str, "length": 9999, "start": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
        if not rows:
            print(f"[foreign_flow] Data kosong untuk tanggal {date_str} (mungkin belum ada data / market belum jalan).")
            return {}

        result = {}
        for row in rows:
            code = row.get("StockCode") or row.get("Code")
            if not code:
                continue
            fbuy = float(row.get("ForeignBuy", 0) or 0)
            fsell = float(row.get("ForeignSell", 0) or 0)
            result[code.strip().upper()] = {
                "foreign_buy": fbuy,
                "foreign_sell": fsell,
                "net_foreign": fbuy - fsell,
                "value": float(row.get("Value", 0) or 0),
            }
        print(f"[foreign_flow] Berhasil ambil data foreign flow untuk {len(result)} saham.")
        return result
    except Exception as e:
        print(f"[foreign_flow] Gagal ambil data foreign flow: {e}. "
              f"Laporan tetap lanjut tanpa data ini.")
        return {}


def format_rupiah(value: float) -> str:
    """Format singkat: 1_250_000_000 -> 'Rp1,25 M', dst."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000_000_000:
        return f"{sign}Rp{value / 1_000_000_000_000:.2f} T"
    if value >= 1_000_000_000:
        return f"{sign}Rp{value / 1_000_000_000:.2f} M"
    if value >= 1_000_000:
        return f"{sign}Rp{value / 1_000_000:.1f} Jt"
    return f"{sign}Rp{value:,.0f}"


if __name__ == "__main__":
    flow = get_foreign_flow()
    print(f"Total saham dengan data foreign flow: {len(flow)}")
