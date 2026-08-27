# Early Breakout Screener (Indonesian Stock Screener)

Screener saham IDX/BEI yang bertujuan mendeteksi saham **sebelum** mengalami kenaikan besar — fokus ke fase:

**BASE / SIDEWAYS → MOMENTUM MASUK → MA BULLISH → BREAKOUT → VOLUME CONFIRMATION**

⚠️ **PENTING**: Sistem ini menghasilkan **ranking probabilitas setup teknikal (0-100)**, BUKAN jaminan atau prediksi pasti bahwa saham akan naik. Skor 80+ tidak berarti saham pasti naik — itu cuma berarti karakteristik teknikalnya mirip pola breakout yang secara historis punya peluang lebih baik. Bukan rekomendasi finansial. DYOR.

Modul ini **terpisah** dari bot notifikasi jam-jaman (`main.py`) yang sudah ada di project ini — bisa dipakai berdampingan.

---

## Struktur Kode

```
breakout_screener/
├── config.py       # semua threshold & bobot scoring (configurable tanpa ubah kode)
├── indicators.py   # MA9/26/20/50, RSI14, ATR14, volume, resistance/support, OBV, ADX, VWAP
├── scoring.py       # sistem skor 0-100 (base, MA, RSI, volume, breakout, price action,
│                     false breakout, overextended)
├── modes.py        # klasifikasi 3 mode: RADAR / SIAGA / ENTRY
├── breakout.py     # entry zone, stop loss (ATR-based), target, risk/reward
├── backtest.py     # simulasi walk-forward, anti look-ahead bias
└── tests/          # unit test (16 test, jalan tanpa internet)

run_breakout_screener.py   # entry point screening live
run_backtest.py            # entry point backtest historis
```

## Cara Pakai

```bash
pip install -r requirements.txt

# Screening live (print ke terminal)
python run_breakout_screener.py

# Screening live + kirim ringkasan ke Telegram (butuh env var TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID)
python run_breakout_screener.py --telegram

# Backtest 1 saham (histori 5 tahun)
python run_backtest.py BBCA

# Backtest SEMUA saham IDX (lama, bisa puluhan menit)
python run_backtest.py --all
```

## Jalankan Unit Test

Tidak butuh `pytest` — bisa jalan pakai Python biasa:

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
for mod in ['breakout_screener.tests.test_indicators','breakout_screener.tests.test_breakout','breakout_screener.tests.test_scoring']:
    m = __import__(mod, fromlist=['*'])
    for name in dir(m):
        if name.startswith('test_'):
            getattr(m, name)()
            print('PASS:', name)
"
```

Atau kalau `pytest` tersedia di environment kamu: `pytest breakout_screener/tests/ -v`

---

## Sistem Scoring (0-100)

| Kategori | Bobot | Yang Dicek |
|---|---|---|
| Base/Consolidation | 15 | Range 20 hari sempit, MA9/26 mendatar, volatilitas menurun, volume kecil sebelumnya, harga dekat resistance |
| MA 9/26 | 15 | MA9 naik, MA9>MA26, MA26 naik, harga>MA9>MA26, bonus golden cross 1-5 hari terakhir |
| RSI Momentum | 10 | RSI>50, RSI naik, RSI di zona 50-65 optimal, pengurangan kalau RSI>75 (extended) |
| Volume | 20 | Relative volume >1.5x/2x/3x **dikombinasikan dengan arah candle** (volume besar+bearish tidak dapat skor) |
| Breakout | 20 | Close > resistance 20 hari, breakout+volume confirmation, tiering berdasar relative volume |
| Price Action | 10 | Struktur Higher High / Higher Low |
| Liquidity | 10 | Lolos filter likuiditas dasar |

**Penalti terpisah** (bukan bagian dari 100 poin di atas, mengurangi skor akhir):
- **False Breakout Detection**: -10 s/d -25 (upper wick panjang, volume besar+bearish, harga balik di bawah MA9, breakout gagal dipertahankan)
- **Overextended Filter**: -10 s/d -20 + warning `EXTENDED`/`DO NOT CHASE` (saham tetap muncul di hasil, tapi rank turun)

**Kategori Skor:**

| Skor | Kategori |
|---|---|
| 90-100 | PRIORITY BREAKOUT |
| 80-89 | STRONG SETUP |
| 65-79 | SETUP BULLISH |
| 50-64 | WATCHLIST |
| 0-49 | PASS |

## 3 Mode Screening

- **RADAR** — saham yang belum breakout tapi mulai menunjukkan base/akumulasi (RSI 45-60, base terbentuk)
- **SIAGA** — saham yang sudah mulai bergerak, mendekati breakout (MA9>MA26, RSI>50, volume mulai naik)
- **ENTRY** — breakout yang sudah dikonfirmasi volume, siap dieksekusi

## Anti Look-Ahead Bias

Resistance/support (HH20/LL20) dihitung dari data **SEBELUM** hari ini (`.shift(1)` sebelum `.rolling()`), supaya candle hari ini tidak "mengintip" dirinya sendiri saat menentukan level breakout. Modul backtest mensimulasikan ini dengan memotong data ke `df.iloc[:i+1]` di tiap hari `i`, bukan menghitung sekali di seluruh dataset.

## Keterbatasan / Catatan Jujur

- **VWAP** yang dihitung adalah pendekatan rolling 20-hari untuk data harian, BUKAN VWAP intraday asli (VWAP asli butuh data per-menit yang tidak tersedia dari `yfinance` untuk saham IDX).
- **Backtest belum pernah dijalankan ke data riil** di lingkungan pengembangan ini (sandbox tanpa akses internet) — sudah divalidasi dengan data sintetis (16 unit test lolos), tapi performa nyata di data historis IDX perlu kamu jalankan sendiri via `run_backtest.py`.
- Bobot normalisasi antar kategori (raw_max per kategori vs bobot akhir) adalah keputusan desain untuk menyelaraskan poin-poin individual di spek dengan total 100 — kalau kamu mau bobot berbeda, ubah `WEIGHT_*` di `config.py`.
- Filter likuiditas & semua threshold ada di `config.py` — ubah di situ, tidak perlu sentuh kode utama.
- Ini bukan sistem yang "belajar" dari hasil sebelumnya (bukan machine learning) — murni rule-based scoring sesuai spek. Akurasi sebenarnya baru bisa diketahui lewat backtest yang kamu jalankan ke data riil.
