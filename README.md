# IDX Signal Bot (v2 — Rebuild)

Screener otomatis semua saham IDX, kirim notifikasi ke Telegram **tiap 1 jam selama jam trading** (09:00, 10:00, 11:00, 13:00, 14:00, 15:00 WIB). **Tidak ada batasan/dedup** — saham yang sama bisa muncul lagi di jam berikutnya kalau masih memenuhi kriteria.

⚠️ **Disclaimer**: ini alat bantu analisa teknikal, bukan rekomendasi finansial. Selalu riset sendiri (DYOR) dan pertimbangkan risiko sebelum transaksi.

## Kriteria yang Dicek

| Kriteria | Penjelasan |
|---|---|
| 🎯 **Support + Candle Reversal** | Harga dalam radius 3% dari titik terendah 20 hari, DAN candle hari ini berbentuk Doji/Hammer |
| 🕯️ **Candle Doji/Hammer** | Doji/Hammer yang muncul setelah downtrend, sideway ~1 minggu, atau sideway ~1 bulan |
| 🔄 **Reversal Merah ke Hijau** | Candle kemarin merah, candle hari ini hijau, volume hari ini > rata-rata 1 minggu terakhir |
| 📉 **RSI Rendah (Oversold)** | RSI < 30 |
| 🌍 **Dibeli Asing & BUMN** | Top 20 saham dengan net foreign buy positif, ditandai `[BUMN]` kalau relevan |

## 1. Setup Bot Telegram (5 menit)

1. Chat **@BotFather** di Telegram → `/newbot` → ikuti instruksi → dapat **token** (bentuknya `123456:ABC-xxxxx`).
2. Chat **@userinfobot** di Telegram (atau tambahkan bot info serupa ke group) → catat **chat ID** kamu/group (angka, negatif kalau group).
3. Kirim 1 pesan apa saja ke bot yang baru kamu buat / masukkan ke group.

## 2. Setup Repo GitHub

1. Buat repo baru, push semua file di folder ini ke repo tersebut (termasuk folder `.github`).
2. Buka **Settings → Secrets and variables → Actions → New repository secret**, tambahkan:
   - `TELEGRAM_BOT_TOKEN` = token dari BotFather
   - `TELEGRAM_CHAT_ID` = chat ID kamu/group
3. Selesai — workflow di `.github/workflows/idx-signals.yml` otomatis jalan tiap 1 jam selama jam trading, hari kerja (Senin-Jumat).
4. Mau tes manual? Buka tab **Actions** → pilih workflow **IDX Signal Screening** → **Run workflow**.

## 3. Jalankan Manual di Komputer Sendiri (opsional, buat testing)

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="token_kamu"
export TELEGRAM_CHAT_ID="chat_id_kamu"
python main.py
```

## Struktur File

| File | Fungsi |
|---|---|
| `main.py` | Orkestrasi utama — download data, jalankan semua kriteria, format & kirim pesan |
| `signals.py` | Logika deteksi 4 dari 5 kriteria (candle, support, reversal, RSI) |
| `foreign_flow.py` | Ambil data net foreign buy/sell per saham dari IDX |
| `bumn_list.py` | Daftar manual kode saham BUMN & anak usaha BUMN |
| `idx_tickers.py` | Daftar semua kode saham IDX (fallback ke list manual kalau endpoint online gagal) |
| `notifier.py` | Kirim pesan ke Telegram |

## Catatan Jujur / Keterbatasan

- **Belum ada backtest** — kriteria di atas belum diuji ke data historis, jadi belum ada angka pasti soal akurasinya. Disarankan pantau dulu beberapa minggu sebelum dipakai serius.
- **Endpoint foreign flow** dari IDX berdasarkan pola komunitas, bukan API resmi publik — kalau gagal, laporan tetap lanjut tanpa data ini (tidak bikin error total).
- **Tidak ada dedup** artinya kalau saham masih memenuhi kriteria yang sama di jam berikutnya, dia akan muncul lagi di notifikasi berikutnya — ini disengaja sesuai permintaan, bukan bug.
- Data yang dipakai murni **candle harian**, jadi di jam-jam awal trading (09:00-11:00), "candle hari ini" masih mencerminkan harga yang sedang berjalan (belum final sampai market tutup).
