"""
Daftar watchlist saham pilihan pengguna untuk laporan gabungan (5 kriteria
signals.py + scoring breakout 0-100 breakout_screener). TIDAK melalui
filter likuiditas -- semua saham di list ini SELALU ditampilkan di
laporan, apapun kondisi likuiditasnya, karena ini pilihan manual.
"""

WATCHLIST_TICKERS = [
    "BIPI", "BUMI", "CBUT", "DEFI", "DEWA", "DFAM", "ESIP", "KAQI", "KBLV",
    "KIOS", "KJEN", "KOPI", "KOTA", "LAND", "MINA", "OILS", "PACK", "PADI",
    "PPRE", "PSAB", "PSDN", "PWON", "TMPO", "BRPT", "CDIA", "CUAN", "COIN",
]
