"""
Cek tren IHSG (indeks harga saham gabungan) secara keseluruhan.
Dipakai sebagai konteks tambahan: kalau IHSG lagi downtrend, risiko
gap-down market-wide lebih tinggi buat SEMUA saham (bukan cuma yang
kita screening), jadi laporan BSJP perlu kasih catatan tambahan.
"""

import yfinance as yf


def get_ihsg_trend():
    """
    Mengembalikan dict {trend: 'uptrend'|'downtrend'|'unknown', last_close, ma20}
    """
    try:
        df = yf.download("^JKSE", period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 21:
            return {"trend": "unknown", "last_close": None, "ma20": None}

        close = df["Close"]
        ma20 = close.rolling(20).mean()
        last_close = float(close.iloc[-1])
        last_ma20 = float(ma20.iloc[-1])

        trend = "uptrend" if last_close > last_ma20 else "downtrend"
        return {"trend": trend, "last_close": round(last_close, 2), "ma20": round(last_ma20, 2)}
    except Exception as e:
        print(f"[market_context] Gagal ambil data IHSG: {e}")
        return {"trend": "unknown", "last_close": None, "ma20": None}
