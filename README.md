# IDX Signal Bot

Bot screening otomatis semua saham IDX, kirim notifikasi buy/sell/rebound ke Telegram.
- **15:30 WIB (market masih buka)**: prediksi saham yang kemungkinan masih lanjut naik besok (BUY & REBOUND WATCH), berdasarkan data hari itu sebelum market tutup.
- **08:15 WIB (sebelum market buka)**: screening sinyal SELL (overbought/momentum melemah).
- **Tiap 15 menit selama jam trading (09:00-15:30 WIB)**: alert real-time begitu ada saham yang baru mulai bullish hari itu. Tiap saham cuma dinotif sekali per hari (gak spam berulang).

⚠️ **Disclaimer**: ini alat bantu analisa teknikal, bukan rekomendasi finansial. Selalu riset sendiri (DYOR) dan pertimbangkan risiko sebelum transaksi.

## 1. Setup Bot Telegram (5 menit)

1. Chat **@BotFather** di Telegram → `/newbot` → ikuti instruksi → dapat **token** (bentuknya `123456:ABC-xxxxx`).
2. Chat **@userinfobot** di Telegram → catat **chat ID** kamu (angka).
3. Kirim 1 pesan apa saja ke bot yang baru kamu buat (biar bot bisa mulai kirim ke kamu).

## 2. Setup Repo GitHub

1. Buat repo baru (bisa private), push semua file di folder ini ke repo tersebut.
2. Buka **Settings → Secrets and variables → Actions → New repository secret**, tambahkan:
   - `TELEGRAM_BOT_TOKEN` = token dari BotFather
   - `TELEGRAM_CHAT_ID` = chat ID kamu
3. Selesai — workflow di `.github/workflows/idx-signals.yml` akan otomatis jalan:
   - jam 08:15 WIB (sell screening)
   - jam 15:30 WIB (prediksi lanjut naik besok)
   - tiap 15 menit dari jam 09:00-15:30 WIB (alert real-time bullish)
4. Mau tes manual? Buka tab **Actions** di repo → pilih workflow **IDX Signal Screening** → **Run workflow** → pilih mode (`evening`/`morning`/`intraday`).

## 3. Jalankan Manual di Komputer Sendiri (opsional, buat testing)

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="token_kamu"
export TELEGRAM_CHAT_ID="chat_id_kamu"
python main.py evening   # atau: python main.py morning
```

## 4. Struktur Sinyal

| Sinyal | Arti | Kapan muncul |
|---|---|---|
| **BUY** | Momentum naik / breakout | golden cross MA5>MA20, MACD bullish cross + harga naik, volume spike |
| **REBOUND WATCH** | Kandidat rebound dari oversold | RSI < 35, atau baru saja oversold + mulai ada candle pembalikan |
| **SELL** | Overbought / momentum melemah | RSI > 70, atau MACD bearish cross |
| **⚡ BULLISH ALERT** (intraday) | Baru mulai berbalik naik hari ini | EMA9 cross ke atas EMA21 di data 15 menit + harga naik |
| **🕯️ CANDLE BULLISH REVERSAL** (khusus pagi) | Candle kemarin (saat market tutup) indikasi pembalikan naik | Doji/Hammer setelah sideway ~1 minggu, sideway ~1 bulan, atau downtrend |

## 6. Data Foreign Flow & Tag BUMN

Kedua laporan (sore & pagi) sekarang nampilin data foreign flow, tapi beda cakupan:

| | Laporan Sore (15:30) | Laporan Pagi (08:15) |
|---|---|---|
| Data dari | Hari ini (market masih buka) | Hari trading terakhir (market SUDAH tutup) |
| Sifat data | Masih bisa berubah dikit sampai closing | **Final/settled** |
| Top saham ditampilkan | Top 5 buy & top 5 sell | Top 20 buy & top 20 sell (lebih lengkap) |

Tiap saham yang muncul di sinyal BUY/REBOUND/SELL/Candle juga dikasih tag `[asing net buy/sell Rp...]` dan `[BUMN]` kalau relevan.

⚠️ **Catatan jujur soal data foreign flow**: fungsi ini (`foreign_flow.py`) mengambil data dari endpoint IDX (`GetStockSummary`) berdasarkan pola yang umum dipakai komunitas untuk scraping data ini — **bukan dari dokumentasi API resmi publik IDX**. Kemungkinan ada penyesuaian nama field/parameter yang dibutuhkan setelah kamu coba jalankan (cek log `[foreign_flow]` di output Actions kalau datanya kosong/gagal). Kalau gagal, laporan tetap terkirim tanpa data foreign flow (tidak bikin seluruh proses gagal).

## 7. Confidence Score untuk BSJP (Beli Sore Jual Pagi)

⚠️ **Penting untuk dipahami**: IDX **menutup data broker summary (bandarmology per kode broker) selama jam trading berlangsung** sejak Desember 2021 — data itu baru bisa dilihat publik SETELAH market tutup. Karena laporan sore kita jalan jam 15:30 (market masih buka), data broker-level beneran gak tersedia saat itu, jadi ini BUKAN true bandarmology.

Sebagai gantinya, tiap saham BUY/REBOUND WATCH di laporan sore dikasih **Confidence Score** (Tinggi/Sedang/Rendah) berdasarkan 4 faktor yang BENERAN tersedia jam 15:30:

| Faktor | Yang dicek |
|---|---|
| Foreign flow | Apakah asing net buy atau net sell hari itu |
| Likuiditas | Rata-rata value transaksi 20 hari (di bawah Rp5 miliar/hari = rawan gap tidak stabil) |
| Jarak ke resistance | Kalau harga sudah <2% dari harga tertinggi 20 hari = rawan profit taking |
| Tren IHSG | Kalau IHSG sendiri downtrend = risiko gap-down market-wide buat semua saham |

Tiap saham mulai dari confidence **Tinggi**, turun ke **Sedang**/**Rendah** kalau ada 1/2+ faktor "waspada" (`⚠️`) yang muncul. List saham di laporan sore otomatis di-sort dari confidence tertinggi ke terendah.

Ambang batas likuiditas (`MIN_LIQUIDITY_RUPIAH` di `bsjp_confidence.py`) dan threshold resistance (di `bsjp_confidence.py`) bisa disesuaikan kalau ternyata kurang pas.

**Tetap diingat**: confidence score ini murni gabungan indikator, BUKAN jaminan harga gak akan turun. Gap-down bisa tetap terjadi karena sentimen global/berita mendadak yang gak bisa diprediksi indikator manapun.

## 8. Yang Bisa Dikembangkan Selanjutnya

- Tambah lebih banyak kode saham di `idx_tickers.py` (`FALLBACK_TICKERS`) kalau mau cakupan lebih luas.
- Tambah filter likuiditas (minimal volume/value transaksi) biar gak dapat saham gorengan.
- Tambah tracking portofolio biar sinyal SELL bisa berbasis target profit/stop-loss kamu sendiri, bukan cuma indikator umum.
- Tambah backtest buat ngecek akurasi sinyal sebelum dipakai beneran.

## ⚠️ Catatan Soal Jadwal Tiap 15 Menit

- Job intraday jalan ~26x/hari (jam 09:00-15:30 WIB) x 5 hari kerja = ~130x/minggu. Kalau repo kamu **public**, GitHub Actions gratis unlimited. Kalau **private**, ada limit 2000 menit/bulan gratis — cek dulu biar gak kepotong kuota di tengah bulan.
- State dedup (`state/notified_today.json`) di-commit balik ke repo tiap run, jadi pastikan branch default gak di-protect dari push langsung oleh Actions bot.
- GitHub cron kadang delay beberapa menit di jam-jam sibuk — jangan berharap presisi ke detik.

## Catatan Teknis

- Data harga diambil dari Yahoo Finance (`yfinance`), interval harian — bukan real-time intraday, jadi sinyal sore dihitung dari harga penutupan hari itu.
- Daftar saham diambil otomatis dari endpoint publik IDX, dengan fallback ke daftar saham populer kalau endpoint gagal diakses.
