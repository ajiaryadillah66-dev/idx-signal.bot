"""
Modul indikator teknikal & logika klasifikasi sinyal.

Sinyal yang dihasilkan per saham:
- "BUY"           : momentum naik / breakout, cocok dibeli sore ini
- "REBOUND_WATCH" : oversold & mulai berbalik arah, kandidat rebound
- "SELL"          : overbought / momentum melemah, waktunya jual/hindari
- None            : tidak ada sinyal signifikan
"""

import pandas as pd
import numpy as np


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """df harus punya kolom: Open, High, Low, Close, Volume (index = tanggal)."""
    out = df.copy()

    out["MA5"] = out["Close"].rolling(5).mean()
    out["MA20"] = out["Close"].rolling(20).mean()
    out["MA50"] = out["Close"].rolling(50).mean()

    # RSI 14
    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = out["Close"].ewm(span=12, adjust=False).mean()
    ema26 = out["Close"].ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_hist"] = out["MACD"] - out["MACD_signal"]

    # Volume rata-rata 20 hari
    out["VolAvg20"] = out["Volume"].rolling(20).mean()

    # Untuk analisa BSJP: likuiditas (rata-rata value transaksi) & jarak ke resistance
    out["AvgValue20"] = (out["Close"] * out["Volume"]).rolling(20).mean()
    out["High20"] = out["High"].rolling(20).max()

    return out


def classify_signal(df: pd.DataFrame) -> dict:
    """
    Menerima df yang sudah ada indikatornya (compute_indicators),
    mengembalikan dict {signal, reasons, last_close, rsi}.
    """
    if len(df) < 55 or df[["MA50", "RSI", "MACD"]].iloc[-1].isna().any():
        return {"signal": None, "reasons": [], "last_close": None, "rsi": None}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    reasons = []

    golden_cross = prev["MA5"] <= prev["MA20"] and last["MA5"] > last["MA20"]
    macd_bull_cross = prev["MACD"] <= prev["MACD_signal"] and last["MACD"] > last["MACD_signal"]
    macd_bear_cross = prev["MACD"] >= prev["MACD_signal"] and last["MACD"] < last["MACD_signal"]
    volume_spike = last["Volume"] > 1.5 * last["VolAvg20"] if pd.notna(last["VolAvg20"]) else False
    price_up = last["Close"] > prev["Close"]
    price_down = last["Close"] < prev["Close"]

    was_oversold_recently = (df["RSI"].iloc[-5:-1] < 32).any()
    reversal_candle = price_up and prev["Close"] <= df["Close"].iloc[-3]

    signal = None

    # --- BUY: breakout / momentum naik ---
    if golden_cross or (macd_bull_cross and price_up):
        signal = "BUY"
        if golden_cross:
            reasons.append("MA5 memotong ke atas MA20 (golden cross)")
        if macd_bull_cross:
            reasons.append("MACD cross bullish")
        if volume_spike:
            reasons.append("volume di atas rata-rata 20 hari (breakout)")

    # --- REBOUND_WATCH: oversold lalu mulai berbalik ---
    elif last["RSI"] < 35 or (was_oversold_recently and reversal_candle):
        signal = "REBOUND_WATCH"
        reasons.append(f"RSI rendah ({last['RSI']:.1f}), berpotensi oversold")
        if reversal_candle:
            reasons.append("mulai ada candle pembalikan arah setelah turun")

    # --- SELL: overbought / momentum melemah ---
    elif last["RSI"] > 70 or macd_bear_cross:
        signal = "SELL"
        if last["RSI"] > 70:
            reasons.append(f"RSI tinggi ({last['RSI']:.1f}), overbought")
        if macd_bear_cross:
            reasons.append("MACD cross bearish")

    return {
        "signal": signal,
        "reasons": reasons,
        "last_close": round(float(last["Close"]), 2),
        "rsi": round(float(last["RSI"]), 1) if pd.notna(last["RSI"]) else None,
        "avg_value_20d": float(last["AvgValue20"]) if pd.notna(last["AvgValue20"]) else None,
        "pct_below_high20": round(float((last["High20"] - last["Close"]) / last["High20"] * 100), 2)
            if pd.notna(last["High20"]) and last["High20"] > 0 else None,
    }


def compute_intraday_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Indikator versi lebih pendek, dipakai untuk bar intraday (mis. 15 menit)."""
    out = df.copy()
    out["EMA9"] = out["Close"].ewm(span=9, adjust=False).mean()
    out["EMA21"] = out["Close"].ewm(span=21, adjust=False).mean()

    delta = out["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))

    out["VolAvg20"] = out["Volume"].rolling(20).mean()

    # Untuk deteksi pola sideway: range harga & rata-rata harga N bar terakhir
    # (tidak termasuk bar terakhir, karena bar terakhir yang dicek untuk breakout)
    out["RangeHigh20"] = out["High"].shift(1).rolling(20).max()
    out["RangeLow20"] = out["Low"].shift(1).rolling(20).min()
    out["RangeMean20"] = out["Close"].shift(1).rolling(20).mean()
    return out


def _candle_shape(o: float, h: float, l: float, c: float):
    """Cek bentuk candle: Doji (body sangat kecil) & Hammer (sumbu bawah panjang).
    Dipakai bareng untuk deteksi harian (setelah downtrend) & intraday (saat sideway)."""
    body = abs(c - o)
    candle_range = h - l
    if candle_range <= 0:
        return False, False
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    is_doji = body <= 0.1 * candle_range
    is_hammer = body > 0 and lower_shadow >= 2 * body and upper_shadow <= 0.3 * body
    return is_doji, is_hammer


def classify_intraday_bullish(df: pd.DataFrame) -> dict:
    """
    Deteksi saham yang BARU SAJA mulai berbalik bullish hari ini (dipakai
    untuk alert real-time selama jam trading), berbeda dari classify_signal
    yang dipakai untuk screening harian.

    Dua pola yang dideteksi:
    1. Momentum reversal umum: EMA9 cross ke atas EMA21
    2. Breakout dari sideway: harga sempat bergerak di range sempit
       (20 bar terakhir), lalu tembus ke atas range itu dengan volume naik

    Catatan: deteksi candle Doji/Hammer TIDAK dilakukan di sini -- itu
    khusus dicek dari candle HARIAN saat market tutup, lihat
    detect_bullish_candle_pattern() di bawah, yang dikirim di laporan pagi.
    """
    required_cols = ["EMA9", "EMA21", "RSI", "RangeHigh20", "RangeLow20", "RangeMean20"]
    if len(df) < 25 or df[required_cols].iloc[-1].isna().any():
        return {"bullish": False, "reasons": [], "last_price": None, "rsi": None}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    reasons = []

    ema_cross_up = prev["EMA9"] <= prev["EMA21"] and last["EMA9"] > last["EMA21"]
    volume_spike = last["Volume"] > 1.5 * last["VolAvg20"] if pd.notna(last["VolAvg20"]) else False
    price_up = last["Close"] > prev["Close"]

    # Pola sideway: range 20 bar terakhir sempit (<3.5% dari harga rata-rata)
    range_width_pct = (last["RangeHigh20"] - last["RangeLow20"]) / last["RangeMean20"] * 100
    was_sideways = range_width_pct < 3.5
    breakout_from_range = last["Close"] > last["RangeHigh20"]

    momentum_bullish = ema_cross_up and price_up
    sideway_breakout = was_sideways and breakout_from_range and price_up

    bullish = momentum_bullish or sideway_breakout
    if sideway_breakout:
        reasons.append(f"breakout dari pola sideway (range ~{range_width_pct:.1f}% beberapa jam terakhir)")
        if volume_spike:
            reasons.append("volume melonjak saat breakout")
    if momentum_bullish:
        reasons.append("EMA9 cross ke atas EMA21 (momentum jangka pendek berbalik naik)")
        if volume_spike and not sideway_breakout:
            reasons.append("volume melonjak dari rata-rata")

    return {
        "bullish": bullish,
        "reasons": reasons,
        "last_price": round(float(last["Close"]), 2),
        "rsi": round(float(last["RSI"]), 1) if pd.notna(last["RSI"]) else None,
    }


def detect_bullish_candle_pattern(df: pd.DataFrame) -> dict:
    """
    Deteksi pola candle Doji/Hammer pada candle TERAKHIR (candle harian
    saat market tutup -- dipakai untuk laporan pagi sebelum market buka
    besoknya), khusus yang muncul dalam salah satu konteks berikut yang
    bikin pola ini dianggap sinyal pembalikan ke atas (bukan pola netral):

    1. Baru saja downtrend (5 candle terakhir turun)
    2. Sideway ~1 minggu (range harga 5 candle SEBELUM candle ini sempit)
    3. Sideway ~1 bulan (range harga 20 candle SEBELUM candle ini sempit)

    Return: {"patterns": [...], "last_close": ...} atau None kalau gak ada
    pola bullish reversal yang terdeteksi.
    """
    if len(df) < 21:
        return None

    last = df.iloc[-1]
    o, h, l, c = float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"])
    is_doji, is_hammer = _candle_shape(o, h, l, c)

    if not (is_doji or is_hammer):
        return None

    # Konteks 1: downtrend 5 candle terakhir (tidak termasuk candle ini)
    was_downtrend = float(df["Close"].iloc[-1]) < float(df["Close"].iloc[-6])

    # Konteks 2 & 3: sideway 1 minggu (5 candle) / 1 bulan (20 candle),
    # dihitung dari candle SEBELUM candle terakhir (biar gak ikut candle
    # doji/hammer-nya sendiri dalam perhitungan range)
    prior = df.iloc[:-1]
    high_5, low_5, mean_5 = prior["High"].iloc[-5:].max(), prior["Low"].iloc[-5:].min(), prior["Close"].iloc[-5:].mean()
    high_20, low_20, mean_20 = prior["High"].iloc[-20:].max(), prior["Low"].iloc[-20:].min(), prior["Close"].iloc[-20:].mean()

    range_1w_pct = (high_5 - low_5) / mean_5 * 100 if mean_5 > 0 else 999
    range_1m_pct = (high_20 - low_20) / mean_20 * 100 if mean_20 > 0 else 999

    was_sideways_1w = range_1w_pct < 5
    was_sideways_1m = range_1m_pct < 8

    candle_name = "Hammer" if is_hammer else "Doji"
    patterns = []

    if was_sideways_1w:
        patterns.append(f"{candle_name} setelah sideway ~1 minggu (range ~{range_1w_pct:.1f}%), potensi mulai breakout naik")
    elif was_sideways_1m:
        patterns.append(f"{candle_name} setelah sideway ~1 bulan (range ~{range_1m_pct:.1f}%), potensi mulai breakout naik")
    elif was_downtrend:
        patterns.append(f"{candle_name} setelah tren turun, potensi berbalik naik (rebound)")

    if not patterns:
        return None

    return {"patterns": patterns, "last_close": round(c, 2)}
