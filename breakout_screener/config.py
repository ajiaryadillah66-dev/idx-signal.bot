"""
Konfigurasi terpusat untuk Early Breakout Screener.
Semua threshold & bobot scoring bisa diubah di sini tanpa menyentuh
kode utama (sesuai Bagian 22 spek: semua parameter harus configurable).
"""

# --- Data ---
HISTORY_DAYS_LIVE = 200          # histori minimum untuk screening live (Bagian 1)
HISTORY_PERIOD_BACKTEST = "5y"   # histori untuk backtest (Bagian 18: 2-5 tahun)

# --- Filter Likuiditas (Bagian 2) ---
MIN_AVG_VOLUME_20 = 1_000_000        # lembar saham
MIN_AVG_VALUE_20 = 1_000_000_000     # Rupiah
MIN_PRICE = 50                       # Rupiah

# --- Periode Indikator (Bagian 1) ---
MA_FAST = 9
MA_MED = 26
MA_20 = 20
MA_50 = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
VOLUME_AVG_SHORT = 20
VOLUME_AVG_LONG = 50
BREAKOUT_LOOKBACK = 20   # highest high / lowest low N hari
ADX_PERIOD = 14

# --- Base / Sideways (Bagian 3) ---
BASE_RANGE_TIGHT_PCT = 15.0    # range_20 dianggap "sempit" kalau <= ini (%)

# --- MA9/26 Scoring (Bagian 4) ---
MA_CROSS_RECENT_DAYS = 5        # bonus kalau golden cross terjadi dalam N hari terakhir

# --- RSI Scoring (Bagian 5) ---
RSI_MOMENTUM_LOW = 50
RSI_MOMENTUM_HIGH = 65
RSI_EXTENDED = 75

# --- Volume Scoring (Bagian 6) ---
REL_VOLUME_TIER1 = 1.5
REL_VOLUME_TIER2 = 2.0
REL_VOLUME_TIER3 = 3.0

# --- Breakout / Resistance (Bagian 7-8) ---
BREAKOUT_NEAR_TIER1_PCT = 3.0     # dalam 3% di bawah resistance
BREAKOUT_NEAR_TIER2_PCT = 5.0     # dalam 5% di bawah resistance

# --- Overextended Filter (Bagian 11) ---
EXTENDED_MA9_MULTIPLIER = 1.10
EXTENDED_MA26_MULTIPLIER = 1.20
DO_NOT_CHASE_PCT = 8.0            # naik >8-10% dari resistance -> "DO NOT CHASE"

# --- ATR Stop Loss (Bagian 12) ---
ATR_STOP_MULTIPLIER = 1.5

# --- Risk/Reward (Bagian 17) ---
MIN_RISK_REWARD = 2.0

# --- Scoring Weights (Bagian 13) -- total harus 100 ---
WEIGHT_BASE = 15
WEIGHT_MA = 15
WEIGHT_RSI = 10
WEIGHT_VOLUME = 20
WEIGHT_BREAKOUT = 20
WEIGHT_PRICE_ACTION = 10
WEIGHT_LIQUIDITY = 10

# --- Kategori Skor (Bagian 13), dicek berurutan dari threshold tertinggi ---
CATEGORY_THRESHOLDS = [
    (90, "PRIORITY BREAKOUT"),
    (80, "STRONG SETUP"),
    (65, "SETUP BULLISH"),
    (50, "WATCHLIST"),
    (0, "PASS"),
]

# --- Backtest (Bagian 18) ---
MAX_HOLDING_DAYS = 15
FALSE_BREAKOUT_WINDOW_DAYS = 3   # breakout dianggap "gagal" kalau balik di bawah resistance dalam N hari
