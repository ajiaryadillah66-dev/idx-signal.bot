"""
Daftar kode saham BUMN dan anak usaha/afiliasi BUMN yang tercatat di IDX.

Daftar ini disusun manual berdasarkan pengetahuan umum emiten pelat merah
Indonesia -- bukan hasil scraping resmi. Kalau ada BUMN yang baru IPO atau
ada yang delisting, silakan update list ini langsung.
"""

BUMN_TICKERS = {
    # Perbankan
    "BBRI", "BBNI", "BMRI", "BBTN", "BSSR",
    # Telekomunikasi & Media
    "TLKM",
    # Energi & Pertambangan
    "PGAS", "ANTM", "PTBA", "TINS", "MEDC", "ELSA",
    # Semen & Konstruksi
    "SMGR", "SMBR", "WIKA", "WSKT", "PTPP", "ADHI", "WEGE", "WSBP",
    # Infrastruktur & Transportasi
    "JSMR", "GIAA", "ASSA",
    # Pupuk & Perkebunan
    "SGRO",
    # Farmasi
    "KAEF", "INAF",
    # Perumahan & Properti BUMN
    "PPRO",
    # Lain-lain
    "PPGL", "GJTL",
}


def is_bumn(ticker: str) -> bool:
    """Cek apakah kode saham (dengan atau tanpa suffix .JK) termasuk BUMN."""
    code = ticker.replace(".JK", "").strip().upper()
    return code in BUMN_TICKERS
