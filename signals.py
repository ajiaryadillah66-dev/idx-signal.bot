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
    return out


def classify_intraday_bullish(df: pd.DataFrame) -> dict:
    """
    Deteksi saham yang BARU SAJA mulai berbalik bullish hari ini (dipakai
    untuk alert real-time selama jam trading), berbeda dari classify_signal
    yang dipakai untuk screening harian.
    """
    if len(df) < 25 or df[["EMA9", "EMA21", "RSI"]].iloc[-1].isna().any():
        return {"bullish": False, "reasons": [], "last_price": None, "rsi": None}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    reasons = []

    ema_cross_up = prev["EMA9"] <= prev["EMA21"] and last["EMA9"] > last["EMA21"]
    rsi_turning_up = prev["RSI"] < 50 and last["RSI"] >= 50 and last["RSI"] > prev["RSI"]
    volume_spike = last["Volume"] > 1.5 * last["VolAvg20"] if pd.notna(last["VolAvg20"]) else False
    price_up = last["Close"] > prev["Close"]

    bullish = ema_cross_up and price_up
    if bullish:
        reasons.append("EMA9 cross ke atas EMA21 (momentum jangka pendek berbalik naik)")
        if rsi_turning_up:
            reasons.append(f"RSI naik ke {last['RSI']:.1f}")
        if volume_spike:
            reasons.append("volume melonjak dari rata-rata")

    return {
        "bullish": bullish,
        "reasons": reasons,
        "last_price": round(float(last["Close"]), 2),
        "rsi": round(float(last["RSI"]), 1) if pd.notna(last["RSI"]) else None,
    }
