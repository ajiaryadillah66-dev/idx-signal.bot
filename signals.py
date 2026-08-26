"""
Modul deteksi pola candle & kondisi teknikal untuk screener saham IDX.

Screener versi ini (rebuild dari awal) fokus ke 5 kriteria yang dipilih:
1. Support + candle Doji/Hammer         -> detect_support_with_reversal_candle
2. Candle Doji/Hammer (downtrend/sideway) -> detect_bullish_candle_pattern
3. Reversal candle merah->hijau + volume  -> detect_red_to_green_volume_reversal
4. RSI rendah (oversold)                -> get_last_rsi
5. Dibeli asing & BUMN                  -> dihitung di main.py pakai foreign_flow.py

Semua fungsi di sini pakai data harian (candle harian, bukan intraday).
"""

import pandas as pd
import numpy as np


def _candle_shape(o: float, h: float, l: float, c: float):
    """Cek bentuk candle: Doji (body sangat kecil) & Hammer (sumbu bawah panjang)."""
    body = abs(c - o)
    candle_range = h - l
    if candle_range <= 0:
        return False, False
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    is_doji = body <= 0.1 * candle_range
    is_hammer = body > 0 and lower_shadow >= 2 * body and upper_shadow <= 0.3 * body
    return is_doji, is_hammer


def get_last_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """Hitung RSI dan kembalikan nilai terakhir saja (atau None kalau data kurang)."""
    if len(df) < period + 1:
        return None
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    last = rsi.iloc[-1]
    return float(last) if pd.notna(last) else None


def detect_bullish_candle_pattern(df: pd.DataFrame) -> dict:
    """
    Deteksi pola candle Doji/Hammer pada candle TERAKHIR (candle harian),
    khusus yang muncul dalam salah satu konteks berikut yang bikin pola
    ini dianggap sinyal pembalikan ke atas (bukan pola netral):

    1. Baru saja downtrend (5 candle terakhir turun)
    2. Sideway ~1 minggu (range harga 5 candle SEBELUM candle ini sempit)
    3. Sideway ~1 bulan (range harga 20 candle SEBELUM candle ini sempit)

    Return: {"patterns": [...], "last_close": ...} atau None.
    """
    if len(df) < 21:
        return None

    last = df.iloc[-1]
    o, h, l, c = float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"])
    is_doji, is_hammer = _candle_shape(o, h, l, c)

    if not (is_doji or is_hammer):
        return None

    was_downtrend = float(df["Close"].iloc[-1]) < float(df["Close"].iloc[-6])

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


def detect_support_touch(df: pd.DataFrame, threshold_pct: float = 3.0) -> dict:
    """
    Cek apakah harga hari ini nyentuh/deket area SUPPORT -- support level
    dihitung dari harga terendah 20 hari trading terakhir (SEBELUM hari ini).

    Return: {"last_close": ..., "support_level": ..., "distance_pct": ...}
    atau None kalau harga masih jauh dari support.
    """
    if len(df) < 21:
        return None

    prior_low20 = float(df["Low"].iloc[-21:-1].min())
    last_close = float(df["Close"].iloc[-1])
    if prior_low20 <= 0:
        return None

    distance_pct = (last_close - prior_low20) / prior_low20 * 100
    if distance_pct > threshold_pct:
        return None

    return {
        "last_close": round(last_close, 2),
        "support_level": round(prior_low20, 2),
        "distance_pct": round(distance_pct, 2),
    }


def detect_support_with_reversal_candle(df: pd.DataFrame) -> dict:
    """
    Kombinasi: harga nyentuh/deket support 20 hari DAN candle hari ini
    berbentuk Doji/Hammer -- kombinasi lebih kuat dibanding cuma nyentuh
    support doang.
    """
    support = detect_support_touch(df)
    if support is None:
        return None

    last = df.iloc[-1]
    o, h, l, c = float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"])
    is_doji, is_hammer = _candle_shape(o, h, l, c)
    if not (is_doji or is_hammer):
        return None

    candle_name = "Hammer" if is_hammer else "Doji"
    support["candle"] = candle_name
    return support


def detect_red_to_green_volume_reversal(df: pd.DataFrame) -> dict:
    """
    Deteksi saham yang candle KEMARIN merah (close < open), lalu candle
    HARI INI berbalik hijau (close > open), DIBARENGI volume hari ini di
    atas rata-rata volume 1 minggu (5 hari trading) terakhir.

    Return: {"last_close": ..., "volume_increase_pct": ...} atau None.
    """
    if len(df) < 7:
        return None

    yesterday = df.iloc[-2]
    today = df.iloc[-1]

    yesterday_red = float(yesterday["Close"]) < float(yesterday["Open"])
    today_green = float(today["Close"]) > float(today["Open"])

    avg_vol_1w = df["Volume"].iloc[-6:-1].mean()
    if pd.isna(avg_vol_1w) or avg_vol_1w <= 0:
        return None

    today_volume = float(today["Volume"])
    volume_up = today_volume > avg_vol_1w

    if not (yesterday_red and today_green and volume_up):
        return None

    vol_increase_pct = (today_volume / avg_vol_1w - 1) * 100

    return {
        "last_close": round(float(today["Close"]), 2),
        "volume_increase_pct": round(vol_increase_pct, 1),
    }
