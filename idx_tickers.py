"""
Modul untuk mengambil daftar seluruh kode saham yang tercatat di IDX.

Strategi:
1. Coba ambil daftar terbaru dari endpoint publik IDX.
2. Kalau gagal (endpoint berubah / rate limit / offline), pakai daftar
   cadangan (FALLBACK_TICKERS) yang sudah dibundel di file ini.

Semua kode saham akan dikembalikan dengan suffix ".JK" (format yfinance).
"""

import requests

IDX_LIST_ENDPOINT = (
    "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
    "?indexCode=&kodeEmiten=&start=0&length=2000"
)

# Daftar cadangan: saham-saham yang paling aktif diperdagangkan di IDX
# (mencakup LQ45, IDX30, dan saham populer lain). Bisa ditambah manual
# kalau mau menambah cakupan screening.
FALLBACK_TICKERS = [
    "BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "ARTO", "BJBR", "BJTM",
    "TLKM", "EXCL", "ISAT", "FREN", "TOWR", "MTEL",
    "ASII", "UNTR", "AUTO", "SMSM", "GJTL",
    "UNVR", "ICBP", "INDF", "MYOR", "CPIN", "JPFA", "AALI", "LSIP",
    "GGRM", "HMSP", "WIIM",
    "ANTM", "INCO", "TINS", "MDKA", "PSAB", "ADMR", "MBMA",
    "PTBA", "ADRO", "ITMG", "PGAS", "MEDC", "ELSA", "AKRA",
    "SMGR", "INTP", "SMBR",
    "KLBF", "SIDO", "TSPC", "PYFA", "MERK",
    "PWON", "BSDE", "CTRA", "SMRA", "ASRI", "APLN", "PANI",
    "BUKA", "GOTO", "EMTK", "MTDL", "DCII", "WIFI",
    "MAPI", "MAPA", "ACES", "RALS", "LPPF", "MPPA", "AMRT", "IPPE",
    "JSMR", "META", "TOTL", "WIKA", "WSKT", "PTPP", "ADHI",
    "BUMI", "DOID", "HRUM", "BYAN", "GEMS", "TAPG", "DSNG",
    "SCMA", "MNCN", "VIVA", "FILM",
    "CTRA", "DMAS", "SSIA", "KIJA", "BEST",
    "INKP", "TKIM", "SIMP", "SGRO",
    "PNBN", "BNGA", "BDMN", "BBTN", "BTPS", "BNLI", "AGRO",
    "CPRO", "STAA", "SSMS",
]


def _normalize(codes):
    seen = set()
    result = []
    for c in codes:
        c = c.strip().upper()
        if not c or c in seen:
            continue
        seen.add(c)
        result.append(c if c.endswith(".JK") else f"{c}.JK")
    return result


def get_idx_tickers(timeout=15):
    """
    Mengembalikan list kode saham IDX dalam format yfinance (mis. 'BBCA.JK').
    Mencoba sumber online dulu, fallback ke daftar statis kalau gagal.
    """
    try:
        resp = requests.get(IDX_LIST_ENDPOINT, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0"
        })
        resp.raise_for_status()
        data = resp.json()
        codes = [row["KodeEmiten"] for row in data.get("data", [])]
        if codes:
            print(f"[idx_tickers] Berhasil ambil {len(codes)} kode dari IDX online.")
            return _normalize(codes)
        raise ValueError("Response kosong")
    except Exception as e:
        print(f"[idx_tickers] Gagal ambil dari IDX online ({e}). Pakai fallback list.")
        return _normalize(FALLBACK_TICKERS)


if __name__ == "__main__":
    tickers = get_idx_tickers()
    print(f"Total saham dipantau: {len(tickers)}")
    print(tickers[:10])
