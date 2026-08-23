"""
Menghitung skor keyakinan (confidence) khusus untuk sinyal BUY/REBOUND
di laporan sore (BSJP: beli sore, jual pagi).

Karena data broker summary (bandarmology per broker) DITUTUP oleh IDX
selama jam trading berlangsung -- baru bisa dilihat publik setelah market
tutup -- confidence score ini pakai gabungan faktor yang BENERAN tersedia
jam 15:30: foreign net buy, likuiditas, jarak ke resistance, dan tren IHSG.
Ini bukan bandarmology asli, tapi tujuannya sama: mengurangi kemungkinan
sinyal palsu yang berujung harga malah turun/gap-down besok pagi.
"""

MIN_LIQUIDITY_RUPIAH = 5_000_000_000  # Rp5 miliar/hari, ambang batas likuiditas


def score_confidence(code_no_suffix: str, info: dict, foreign_flow: dict, ihsg_trend: str) -> dict:
    """
    info: dict hasil classify_signal (sudah ada avg_value_20d, pct_below_high20, dst)
    foreign_flow: dict dari get_foreign_flow()
    ihsg_trend: 'uptrend' | 'downtrend' | 'unknown'

    Return: {"level": "Tinggi"|"Sedang"|"Rendah", "cautions": [...]}
    """
    cautions = []
    caution_count = 0

    # Faktor 1: foreign flow
    flow = foreign_flow.get(code_no_suffix)
    if flow and flow["net_foreign"] < 0:
        cautions.append("asing net sell hari ini")
        caution_count += 1

    # Faktor 2: likuiditas
    avg_value = info.get("avg_value_20d")
    if avg_value is not None and avg_value < MIN_LIQUIDITY_RUPIAH:
        cautions.append("likuiditas rendah (rawan gap tidak stabil)")
        caution_count += 1

    # Faktor 3: jarak ke resistance
    pct_below_high = info.get("pct_below_high20")
    if pct_below_high is not None and pct_below_high < 2:
        cautions.append("dekat resistance 20 hari (waspada profit taking)")
        caution_count += 1

    # Faktor 4: tren IHSG (market-wide, sama untuk semua saham)
    if ihsg_trend == "downtrend":
        cautions.append("IHSG sedang downtrend (risiko gap-down market-wide)")
        caution_count += 1

    if caution_count == 0:
        level = "Tinggi"
    elif caution_count <= 1:
        level = "Sedang"
    else:
        level = "Rendah"

    return {"level": level, "cautions": cautions}
