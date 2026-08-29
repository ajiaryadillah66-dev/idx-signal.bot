"""
Perhitungan semua indikator teknikal untuk Early Breakout Screener.

PENTING -- ANTI LOOK-AHEAD BIAS (Bagian 19):
Semua indikator yang dipakai untuk keputusan di hari H HANYA boleh
memakai data sampai hari H. Resistance/support khususnya dihitung dari
data SEBELUM hari ini (pakai .shift(1) sebelum rolling), supaya tidak
"mengintip" candle hari ini sendiri saat menentukan breakout.
"""

import numpy as np
import pandas as pd

from . import config as cfg


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    df: DataFrame dengan kolom Open, High, Low, Close, Volume (index tanggal).
    Return df baru dengan semua kolom indikator ditambahkan (tidak mengubah df asli).
    """
    out = df.copy()
    close = out["Close"]
    high = out["High"]
    low = out["Low"]
    volume = out["Volume"]

    # --- Moving Averages (Bagian 1) ---
    out["MA9"] = close.rolling(cfg.MA_FAST).mean()
    out["MA26"] = close.rolling(cfg.MA_MED).mean()
    out["MA20"] = close.rolling(cfg.MA_20).mean()
    out["MA50"] = close.rolling(cfg.MA_50).mean()

    # --- RSI 14 ---
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(cfg.RSI_PERIOD).mean()
    avg_loss = loss.rolling(cfg.RSI_PERIOD).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI14"] = 100 - (100 / (1 + rs))

    # --- ATR 14 ---
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["ATR14"] = tr.ewm(alpha=1 / cfg.ATR_PERIOD, adjust=False).mean()

    # --- Volume Averages & Relative Volume ---
    out["AvgVolume20"] = volume.rolling(cfg.VOLUME_AVG_SHORT).mean()
    out["AvgVolume50"] = volume.rolling(cfg.VOLUME_AVG_LONG).mean()
    out["RelativeVolume"] = volume / out["AvgVolume20"].replace(0, np.nan)
    out["AvgValue20"] = (close * volume).rolling(cfg.VOLUME_AVG_SHORT).mean()

    # --- Resistance / Support (HH20 / LL20) -- ANTI LOOK-AHEAD ---
    # shift(1) dulu SEBELUM rolling, supaya candle hari ini TIDAK ikut
    # dihitung sebagai bagian dari resistance/support-nya sendiri.
    out["Resistance20"] = high.shift(1).rolling(cfg.BREAKOUT_LOOKBACK).max()
    out["Support20"] = low.shift(1).rolling(cfg.BREAKOUT_LOOKBACK).min()

    # --- OBV (On Balance Volume) ---
    direction = np.sign(close.diff().fillna(0))
    out["OBV"] = (direction * volume).cumsum()

    # --- ADX 14 ---
    plus_dm = (high - high.shift(1)).clip(lower=0)
    minus_dm = (low.shift(1) - low).clip(lower=0)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)
    atr_for_adx = out["ATR14"].replace(0, np.nan)
    plus_di = 100 * (plus_dm.ewm(alpha=1 / cfg.ADX_PERIOD, adjust=False).mean() / atr_for_adx)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / cfg.ADX_PERIOD, adjust=False).mean() / atr_for_adx)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    out["ADX14"] = dx.ewm(alpha=1 / cfg.ADX_PERIOD, adjust=False).mean()
    out["PlusDI"] = plus_di
    out["MinusDI"] = minus_di

    # --- VWAP (anchored, rolling 20 hari -- proksi untuk data harian) ---
    # CATATAN: VWAP asli dihitung intraday (per menit). Untuk data harian
    # ini pakai pendekatan rolling 20 hari sebagai referensi, bukan VWAP
    # murni -- lihat catatan keterbatasan di README.
    typical_price = (high + low + close) / 3
    out["VWAP20"] = (typical_price * volume).rolling(cfg.VOLUME_AVG_SHORT).sum() / \
        volume.rolling(cfg.VOLUME_AVG_SHORT).sum().replace(0, np.nan)

    return out
