"""
Sistem scoring 0-100 untuk Early Breakout Screener.

Tiap kategori scoring (Bagian 3-9) dihitung sebagai raw_score/raw_max,
lalu dinormalisasi ke bobot kategorinya (Bagian 13) supaya total akhir
tetap dalam skala 0-100 walau jumlah poin mentah per kategori berbeda
dengan bobot akhirnya di tabel skor.

False Breakout Detection (Bagian 10) & Overextended Filter (Bagian 11)
diterapkan sebagai PENALTI setelah skor dasar dihitung, bukan bagian
dari 7 kategori berbobot -- sesuai spek ("boleh tetap masuk hasil
screener, tapi rankingnya diturunkan", bukan diblokir total).
"""

import pandas as pd

from . import config as cfg


def _last(df, col):
    if col not in df.columns or len(df) == 0:
        return None
    val = df[col].iloc[-1]
    return float(val) if pd.notna(val) else None


def score_liquidity(df) -> dict:
    """Bagian 2 -- filter likuiditas, dipakai juga sebagai bagian skor (bobot 10)."""
    avg_vol = _last(df, "AvgVolume20")
    avg_val = _last(df, "AvgValue20")
    price = _last(df, "Close")

    passes = (
        avg_vol is not None and avg_vol > cfg.MIN_AVG_VOLUME_20 and
        avg_val is not None and avg_val > cfg.MIN_AVG_VALUE_20 and
        price is not None and price > cfg.MIN_PRICE
    )
    raw = cfg.WEIGHT_LIQUIDITY if passes else 0
    return {"raw": raw, "raw_max": cfg.WEIGHT_LIQUIDITY, "passes_filter": passes, "details": []}


def score_base_sideways(df) -> dict:
    """Bagian 3 -- deteksi base/sideways sebelum breakout."""
    details = []
    raw = 0
    raw_max = 25  # 5 sub-kriteria x 5 poin mentah, dinormalisasi ke bobot 15

    if len(df) < 26:
        return {"raw": 0, "raw_max": raw_max, "details": details}

    resistance = _last(df, "Resistance20")
    support = _last(df, "Support20")
    close = _last(df, "Close")
    ma9 = df["MA9"]
    ma26 = df["MA26"]
    atr = df["ATR14"]
    avg_vol20 = df["AvgVolume20"]

    if resistance and support and support > 0:
        range20_pct = (resistance - support) / support * 100
        if range20_pct <= cfg.BASE_RANGE_TIGHT_PCT:
            raw += 5
            details.append(f"range 20 hari sempit (~{range20_pct:.1f}%)")

    if len(ma9) >= 6 and pd.notna(ma9.iloc[-1]) and pd.notna(ma9.iloc[-6]) and ma9.iloc[-6] != 0:
        ma9_change_pct = abs(ma9.iloc[-1] - ma9.iloc[-6]) / ma9.iloc[-6] * 100
        if ma9_change_pct < 2:
            raw += 5
            details.append("MA9 mulai mendatar")

    if len(ma26) >= 6 and pd.notna(ma26.iloc[-1]) and pd.notna(ma26.iloc[-6]) and ma26.iloc[-6] != 0:
        ma26_change_pct = abs(ma26.iloc[-1] - ma26.iloc[-6]) / ma26.iloc[-6] * 100
        if ma26_change_pct < 2:
            raw += 5
            details.append("MA26 mulai mendatar")

    if len(atr) >= 11 and pd.notna(atr.iloc[-1]) and pd.notna(atr.iloc[-11]):
        if atr.iloc[-1] < atr.iloc[-11]:
            raw += 5
            details.append("volatilitas (ATR) menurun")

    if len(avg_vol20) >= 21 and pd.notna(avg_vol20.iloc[-1]) and pd.notna(avg_vol20.iloc[-21]):
        if avg_vol20.iloc[-1] < avg_vol20.iloc[-21]:
            raw += 5
            details.append("volume sebelumnya relatif kecil")

    if resistance and close:
        dist_to_resistance = (resistance - close) / resistance * 100
        if 0 <= dist_to_resistance <= 5:
            raw += 5
            details.append(f"harga dekat resistance (jarak {dist_to_resistance:.1f}%)")

    return {"raw": raw, "raw_max": raw_max, "details": details}


def score_ma(df) -> dict:
    """Bagian 4 -- MA9/MA26 scoring + deteksi golden cross (bonus, bukan syarat wajib)."""
    details = []
    raw = 0
    raw_max = 40  # 10+10+5+5+10(bonus cross) mentah, dinormalisasi ke bobot 15

    ma9 = df["MA9"]
    ma26 = df["MA26"]
    close = df["Close"]

    if len(ma9) < 6 or pd.isna(ma9.iloc[-1]) or pd.isna(ma9.iloc[-2]):
        return {"raw": 0, "raw_max": raw_max, "details": [], "golden_cross_recent": False}

    ma9_rising = ma9.iloc[-1] > ma9.iloc[-2]
    if ma9_rising:
        raw += 10
        details.append("MA9 mulai naik")

    ma9_above_ma26 = pd.notna(ma26.iloc[-1]) and ma9.iloc[-1] > ma26.iloc[-1]
    if ma9_above_ma26:
        raw += 10
        details.append("MA9 > MA26")

    ma26_rising = pd.notna(ma26.iloc[-2]) and ma26.iloc[-1] > ma26.iloc[-2]
    if ma26_rising:
        raw += 5
        details.append("MA26 mulai naik")

    price_above_both = (
        pd.notna(ma26.iloc[-1]) and close.iloc[-1] > ma9.iloc[-1] > ma26.iloc[-1]
    )
    if price_above_both:
        raw += 5
        details.append("Harga > MA9 > MA26")

    golden_cross_recent = False
    lookback = min(cfg.MA_CROSS_RECENT_DAYS, len(ma9) - 1)
    for i in range(1, lookback + 1):
        prev9, prev26 = ma9.iloc[-1 - i], ma26.iloc[-1 - i]
        cur9, cur26 = ma9.iloc[-i], ma26.iloc[-i]
        if pd.notna(prev9) and pd.notna(prev26) and pd.notna(cur9) and pd.notna(cur26):
            if prev9 <= prev26 and cur9 > cur26:
                golden_cross_recent = True
                break
    if golden_cross_recent:
        raw += 10
        details.append(f"golden cross MA9/MA26 dalam {cfg.MA_CROSS_RECENT_DAYS} hari terakhir")

    return {"raw": raw, "raw_max": raw_max, "details": details, "golden_cross_recent": golden_cross_recent}


def score_rsi(df) -> dict:
    """Bagian 5 -- RSI sebagai indikator momentum (BUKAN aturan RSI>70=sell)."""
    details = []
    raw = 0
    raw_max = 13  # 5+5+3

    rsi = df["RSI14"]
    if len(rsi) < 6 or pd.isna(rsi.iloc[-1]):
        return {"raw": 0, "raw_max": raw_max, "details": [], "extended": False, "last_rsi": None}

    last_rsi = float(rsi.iloc[-1])

    if last_rsi > cfg.RSI_MOMENTUM_LOW:
        raw += 5
        details.append(f"RSI > {cfg.RSI_MOMENTUM_LOW}")

    prior_rsi = rsi.iloc[-4] if pd.notna(rsi.iloc[-4]) else None  # ~3-5 hari lalu
    if prior_rsi is not None and last_rsi > prior_rsi:
        raw += 5
        details.append("RSI sedang naik")

    if cfg.RSI_MOMENTUM_LOW <= last_rsi <= cfg.RSI_MOMENTUM_HIGH:
        raw += 3
        details.append(f"RSI di zona optimal ({cfg.RSI_MOMENTUM_LOW}-{cfg.RSI_MOMENTUM_HIGH})")

    extended = last_rsi > cfg.RSI_EXTENDED
    if extended:
        raw -= 5  # pengurangan momentum, BUKAN sinyal sell otomatis
        details.append(f"RSI > {cfg.RSI_EXTENDED} (kemungkinan sudah extended)")

    return {
        "raw": max(raw, 0), "raw_max": raw_max, "details": details,
        "extended": extended, "last_rsi": round(last_rsi, 1),
    }


def score_volume(df) -> dict:
    """Bagian 6 -- analisa volume, harus dianalisis bareng arah candle."""
    details = []
    raw = 0
    raw_max = 20

    rel_vol = _last(df, "RelativeVolume")
    close = df["Close"]
    open_ = df["Open"]
    if rel_vol is None:
        return {"raw": 0, "raw_max": raw_max, "details": [], "relative_volume": None}

    is_bullish_candle = close.iloc[-1] > open_.iloc[-1]

    if rel_vol > cfg.REL_VOLUME_TIER3:
        vol_pts = 20
    elif rel_vol > cfg.REL_VOLUME_TIER2:
        vol_pts = 15
    elif rel_vol > cfg.REL_VOLUME_TIER1:
        vol_pts = 10
    else:
        vol_pts = 0

    if vol_pts > 0:
        if is_bullish_candle:
            raw += vol_pts
            details.append(f"volume {rel_vol:.1f}x rata-rata + candle bullish")
        else:
            # Volume besar + candle bearish -> JANGAN kasih skor bullish tinggi
            details.append(f"volume {rel_vol:.1f}x rata-rata TAPI candle bearish (skor ditahan)")

    vol = df["Volume"]
    if len(vol) >= 6:
        avg5 = vol.iloc[-6:-1].mean()
        if pd.notna(avg5) and vol.iloc[-1] > avg5:
            raw = min(raw + 5, raw_max)
            details.append("volume hari ini > rata-rata 5 hari")

    return {"raw": raw, "raw_max": raw_max, "details": details, "relative_volume": round(rel_vol, 2)}


def score_breakout(df) -> dict:
    """Bagian 7-8 -- resistance, breakout, breakout+volume confirmation."""
    details = []
    raw = 0
    raw_max = 55  # 20(breakout) + 20(confirm) + 5 + 10(tiering volume), dinormalisasi ke bobot 20

    resistance = _last(df, "Resistance20")
    close = _last(df, "Close")
    open_ = _last(df, "Open")
    rel_vol = _last(df, "RelativeVolume")

    if resistance is None or close is None:
        return {
            "raw": 0, "raw_max": raw_max, "details": details,
            "breakout": False, "breakout_confirmed": False,
            "resistance": resistance, "distance_pct": None,
        }

    breakout = close > resistance
    near_tier1 = not breakout and close >= resistance * (1 - cfg.BREAKOUT_NEAR_TIER1_PCT / 100)
    near_tier2 = not breakout and not near_tier1 and close >= resistance * (1 - cfg.BREAKOUT_NEAR_TIER2_PCT / 100)

    if breakout:
        raw += 20
        details.append("breakout resistance 20 hari")
    elif near_tier1:
        raw += 10
        details.append(f"harga <{cfg.BREAKOUT_NEAR_TIER1_PCT:.0f}% di bawah resistance")
    elif near_tier2:
        raw += 5
        details.append(f"harga <{cfg.BREAKOUT_NEAR_TIER2_PCT:.0f}% di bawah resistance")

    breakout_confirmed = False
    if breakout and rel_vol is not None and rel_vol > cfg.REL_VOLUME_TIER1 and close > open_:
        breakout_confirmed = True
        raw += 20
        details.append("BREAKOUT + VOLUME CONFIRMATION")
        if rel_vol > cfg.REL_VOLUME_TIER2:
            raw += 5
        if rel_vol > cfg.REL_VOLUME_TIER3:
            raw += 10

    return {
        "raw": raw, "raw_max": raw_max, "details": details,
        "breakout": breakout, "breakout_confirmed": breakout_confirmed,
        "resistance": round(resistance, 2),
        "distance_pct": round((close - resistance) / resistance * 100, 2),
    }


def score_price_action(df) -> dict:
    """Bagian 9 -- Higher High / Higher Low."""
    details = []
    raw = 0
    raw_max = 10

    if len(df) < 11:
        return {"raw": 0, "raw_max": raw_max, "details": details}

    recent_low = df["Low"].iloc[-5:].min()
    prior_low = df["Low"].iloc[-10:-5].min()
    recent_high = df["High"].iloc[-5:].max()
    prior_high = df["High"].iloc[-10:-5].max()

    higher_low = recent_low > prior_low
    higher_high = recent_high > prior_high

    if higher_low and higher_high:
        raw += 10
        details.append("struktur Higher High & Higher Low mulai terbentuk")
    elif higher_low or higher_high:
        raw += 5
        details.append("struktur bullish sebagian mulai terbentuk")

    return {"raw": raw, "raw_max": raw_max, "details": details}


def detect_false_breakout(df) -> dict:
    """Bagian 10 -- deteksi false breakout, hasilnya PENALTI (bukan kategori skor)."""
    details = []
    penalty = 0

    if len(df) < 4:
        return {"penalty": 0, "details": details, "is_false_breakout_risk": False}

    resistance = _last(df, "Resistance20")
    close = _last(df, "Close")
    open_ = _last(df, "Open")
    high = _last(df, "High")
    ma9 = _last(df, "MA9")
    rel_vol = _last(df, "RelativeVolume")

    if resistance is None or close is None:
        return {"penalty": 0, "details": details, "is_false_breakout_risk": False}

    body = abs(close - open_) if open_ is not None else 0
    upper_wick = (high - max(close, open_)) if (high is not None and open_ is not None) else 0
    if body > 0 and upper_wick > 2 * body:
        penalty += 10
        details.append("upper wick sangat panjang")

    if rel_vol is not None and rel_vol > cfg.REL_VOLUME_TIER1 and open_ is not None and close < open_:
        penalty += 15
        details.append("volume besar tapi candle bearish")

    if ma9 is not None and close < ma9:
        penalty += 10
        details.append("harga kembali di bawah MA9")

    window = min(cfg.FALSE_BREAKOUT_WINDOW_DAYS, len(df) - 1)
    for i in range(1, window + 1):
        past_close = df["Close"].iloc[-1 - i]
        past_resistance = df["Resistance20"].iloc[-1 - i]
        if pd.notna(past_close) and pd.notna(past_resistance) and past_close > past_resistance and close < resistance:
            penalty += 15
            details.append(f"breakout {i} hari lalu gagal dipertahankan")
            break

    penalty = min(penalty, 25)  # cap sesuai spek (-10 s/d -25)
    return {"penalty": penalty, "details": details, "is_false_breakout_risk": penalty > 0}


def detect_overextended(df) -> dict:
    """Bagian 11 -- overextended filter (rank diturunkan, BUKAN diblokir dari hasil)."""
    details = []
    penalty = 0
    warnings = []

    close = _last(df, "Close")
    ma9 = _last(df, "MA9")
    ma26 = _last(df, "MA26")
    resistance = _last(df, "Resistance20")

    if close is None:
        return {"penalty": 0, "warnings": warnings, "details": details, "do_not_chase": False}

    if ma9 and close > ma9 * cfg.EXTENDED_MA9_MULTIPLIER:
        penalty += 10
        warnings.append("EXTENDED (jauh di atas MA9)")
        details.append(f"harga > MA9 x {cfg.EXTENDED_MA9_MULTIPLIER}")

    if ma26 and close > ma26 * cfg.EXTENDED_MA26_MULTIPLIER:
        penalty += 10
        warnings.append("EXTENDED (jauh di atas MA26)")
        details.append(f"harga > MA26 x {cfg.EXTENDED_MA26_MULTIPLIER}")

    do_not_chase = False
    if resistance and resistance > 0:
        gain_from_resistance = (close - resistance) / resistance * 100
        if gain_from_resistance > cfg.DO_NOT_CHASE_PCT:
            do_not_chase = True
            warnings.append("DO NOT CHASE")
            details.append(f"naik {gain_from_resistance:.1f}% dari resistance")

    return {"penalty": penalty, "warnings": warnings, "details": details, "do_not_chase": do_not_chase}


def compute_total_score(df) -> dict:
    """
    Gabungkan semua kategori (Bagian 13) jadi skor 0-100, lalu terapkan
    penalti false breakout & overextended.
    """
    liquidity = score_liquidity(df)
    base = score_base_sideways(df)
    ma = score_ma(df)
    rsi = score_rsi(df)
    volume = score_volume(df)
    breakout = score_breakout(df)
    price_action = score_price_action(df)
    false_breakout = detect_false_breakout(df)
    overextended = detect_overextended(df)

    def normalize(raw, raw_max, weight):
        if raw_max <= 0:
            return 0
        return max(0, min(weight, (raw / raw_max) * weight))

    total = 0
    total += normalize(base["raw"], base["raw_max"], cfg.WEIGHT_BASE)
    total += normalize(ma["raw"], ma["raw_max"], cfg.WEIGHT_MA)
    total += normalize(rsi["raw"], rsi["raw_max"], cfg.WEIGHT_RSI)
    total += normalize(volume["raw"], volume["raw_max"], cfg.WEIGHT_VOLUME)
    total += normalize(breakout["raw"], breakout["raw_max"], cfg.WEIGHT_BREAKOUT)
    total += normalize(price_action["raw"], price_action["raw_max"], cfg.WEIGHT_PRICE_ACTION)
    total += liquidity["raw"]  # sudah dalam skala penuh bobot liquidity (0 atau 10)

    total -= false_breakout["penalty"]
    total -= overextended["penalty"]
    total = max(0, min(100, round(total, 1)))

    category = "PASS"
    for threshold, label in cfg.CATEGORY_THRESHOLDS:
        if total >= threshold:
            category = label
            break

    return {
        "score": total,
        "category": category,
        "components": {
            "liquidity": liquidity, "base": base, "ma": ma, "rsi": rsi,
            "volume": volume, "breakout": breakout, "price_action": price_action,
            "false_breakout": false_breakout, "overextended": overextended,
        },
    }


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


def score_support_bounce(df) -> dict:
    """
    Mode BOUNCE -- TAMBAHAN di luar spek asli ISAT/TMPO (yang murni fokus
    ke breakout resistance). Ini filosofi beda: nyari saham yang lagi di
    area SUPPORT (bukan resistance) DAN nunjukin tanda pembalikan
    (candle Doji/Hammer + RSI oversold) -- support di sini dipakai
    sebagai sinyal MASUK, bukan cuma referensi stop loss seperti di
    mode-mode breakout lainnya.

    Return: {"is_bounce_setup": bool, "details": [...], "support_level": ...,
    "distance_pct": ...}
    """
    details = []
    if len(df) < 21:
        return {"is_bounce_setup": False, "details": details, "support_level": None, "distance_pct": None}

    support = _last(df, "Support20")
    close = _last(df, "Close")
    rsi = _last(df, "RSI14")
    if support is None or close is None or support <= 0:
        return {"is_bounce_setup": False, "details": details, "support_level": support, "distance_pct": None}

    distance_pct = (close - support) / support * 100
    near_support = 0 <= distance_pct <= cfg.SUPPORT_TOUCH_PCT

    last = df.iloc[-1]
    o, h, l, c = float(last["Open"]), float(last["High"]), float(last["Low"]), float(last["Close"])
    is_doji, is_hammer = _candle_shape(o, h, l, c)
    has_reversal_candle = is_doji or is_hammer

    is_oversold = rsi is not None and rsi < cfg.RSI_OVERSOLD_BOUNCE

    is_bounce_setup = near_support and has_reversal_candle and is_oversold

    if near_support:
        details.append(f"harga dekat support (jarak {distance_pct:.1f}%)")
    if has_reversal_candle:
        details.append(f"candle {'Hammer' if is_hammer else 'Doji'}")
    if is_oversold:
        details.append(f"RSI oversold ({rsi:.1f})")

    return {
        "is_bounce_setup": is_bounce_setup,
        "details": details,
        "support_level": round(support, 2),
        "distance_pct": round(distance_pct, 2),
    }
