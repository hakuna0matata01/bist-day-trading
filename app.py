"""
BIST Day Trading Asistanı
==========================
Akşam Tarama -> Sabah Teyit (10:30+, RVOL@Time ile) -> Pozisyon Yönetimi ->
Gün Sonu Çıkış iş akışını uygulayan Streamlit uygulaması. Varsayılan olarak
tüm BIST evrenini (data/bist_all_tickers.csv, ~634 hisse) tarar.

ÖNEMLİ: Bu uygulama yatırım tavsiyesi VERMEZ. Yahoo Finance (yfinance)
üzerinden alınan veriler gecikmeli/eksik olabilir. Gerçek alım-satım
kararlarından önce kendi araştırmanızı yapın, profesyonel bir veri
sağlayıcısı kullanın ve riskleri değerlendirin.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from config import (
    BIST_INDEX_TICKER,
    CEILING_WARNING_THRESHOLD_PCT,
    CONFIRMATION_TIME,
    DEFAULT_RISK_PER_TRADE_PCT,
    DEFAULT_TARGET_RR,
    DEFAULT_WEIGHTS,
    FORCED_EXIT_TIME,
    RVOL_LOOKBACK_DAYS,
    RVOL_THRESHOLD,
    SCREEN_CHUNK_SIZE,
)
from strategy.confirmation import confirm_stock, get_index_trend_ok
from strategy.screening import run_evening_screen
from strategy.universe import load_all_bist_tickers

st.set_page_config(page_title="BIST Day Trading Asistanı", page_icon="📈", layout="wide")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = pd.DataFrame()
if "positions" not in st.session_state:
    st.session_state.positions = []

FULL_UNIVERSE = load_all_bist_tickers()

# ============================================================== Sidebar ===
st.sidebar.title("⚙️ Ayarlar")

st.sidebar.success(f"📋 {len(FULL_UNIVERSE)} BIST hissesi yüklendi (data/bist_all_tickers.csv)")

universe_mode = st.sidebar.radio(
    "Taranacak evren",
    ["Tüm BIST hisseleri", "İlk N hisse (hızlı test)", "Özel liste"],
    index=0,
)

if universe_mode == "Tüm BIST hisseleri":
    universe = FULL_UNIVERSE
elif universe_mode == "İlk N hisse (hızlı test)":
    n = st.sidebar.slider("Hisse sayısı", 10, len(FULL_UNIVERSE), min(100, len(FULL_UNIVERSE)))
    universe = FULL_UNIVERSE[:n]
else:
    custom_text = st.sidebar.text_area(
        "Hisse kodları (yfinance formatı, .IS ile, virgülle ayırın)",
        value=", ".join(FULL_UNIVERSE[:20]),
        height=120,
    )
    universe = [t.strip().upper() for t in custom_text.split(",") if t.strip()]

st.sidebar.caption(f"Bu çalıştırmada taranacak hisse sayısı: **{len(universe)}**")

top_n = st.sidebar.slider("İzleme listesine alınacak hisse sayısı", 3, 30, 10)

with st.sidebar.expander("Skor ağırlıkları (Akşam Tarama)", expanded=False):
    weights = {
        "relative_strength": st.slider("Göreli güç", 0, 50, DEFAULT_WEIGHTS["relative_strength"]),
        "volume": st.slider("Hacim", 0, 50, DEFAULT_WEIGHTS["volume"]),
        "trend": st.slider("Trend (MA20/50)", 0, 50, DEFAULT_WEIGHTS["trend"]),
        "momentum_rsi": st.slider("RSI momentumu", 0, 50, DEFAULT_WEIGHTS["momentum_rsi"]),
        "breakout_proximity": st.slider("Direnç/kırılım yakınlığı", 0, 50, DEFAULT_WEIGHTS["breakout_proximity"]),
    }

with st.sidebar.expander("RVOL@Time ayarları (Sabah Teyit)", expanded=False):
    st.caption(
        "Hacim teyidi, 'şu an' yerine elimizdeki en son verinin kendi zaman "
        "damgasıyla aynı saatteki tarihsel ortalamaya göre yapılır — bu, "
        "veri gecikmesi sorununu bertaraf eder."
    )
    rvol_threshold = st.slider("Minimum RVOL@Time eşiği", 0.5, 3.0, RVOL_THRESHOLD, 0.1)
    rvol_lookback_days = st.slider("Taban çizgisi için geçmiş gün sayısı", 5, 40, RVOL_LOOKBACK_DAYS)

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ Veriler Yahoo Finance (yfinance) üzerinden alınır, gecikmeli/eksik "
    "olabilir. Bu uygulama yatırım tavsiyesi değildir."
)

# ================================================================ Header ===
st.title("📈 BIST Day Trading Asistanı")
st.caption("Akşam Tarama → Sabah Teyit (10:30 sonrası, RVOL@Time ile) → Pozisyon Yönetimi → Gün Sonu Çıkış")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🌙 Akşam Tarama", "🌅 Sabah Teyit", "📋 Pozisyon Takip", "ℹ️ Strateji"]
)

# ------------------------------------------------------------------ Tab 1 --
with tab1:
    st.subheader("Akşam Taraması — Borsa Kapalıyken Hazırlık")
    st.write(
        f"Seçili evrendeki **{len(universe)} hisseyi** göreli güç (BIST100'e "
        "göre), hacim artışı, trend yapısı (MA20/MA50), RSI momentumu ve "
        "direnç yakınlığına göre puanlayarak bir izleme listesi oluşturur. "
        "Veriler toplu (batch) indirildiği için tüm BIST taraması birkaç "
        "dakika içinde tamamlanır; ilk çalıştırmadan sonra önbellek sayesinde "
        "tekrarlar daha hızlı olur."
    )
    if st.button("🔍 Taramayı Çalıştır", type="primary"):
        if not universe:
            st.error("Hisse evreni boş olamaz.")
        else:
            progress_bar = st.progress(0, text="Veriler indiriliyor...")

            def _update_progress(ratio: float) -> None:
                pct = min(100, int(ratio * 100))
                label = "Veriler indiriliyor..." if ratio < 0.85 else "Hisseler puanlanıyor..."
                progress_bar.progress(pct, text=f"{label} ({pct}%)")

            result = run_evening_screen(
                universe,
                weights,
                top_n=top_n,
                index_ticker=BIST_INDEX_TICKER,
                chunk_size=SCREEN_CHUNK_SIZE,
                progress_callback=_update_progress,
            )
            progress_bar.empty()

            if result.empty:
                st.error(
                    "Veri alınamadı. İnternet bağlantınızı, ticker listesini "
                    "veya yfinance/Yahoo Finance erişimini kontrol edin."
                )
            else:
                st.session_state.watchlist = result
                st.success(f"{len(result)} hisse izleme listesine eklendi (taranan: {len(universe)}).")

    if not st.session_state.watchlist.empty:
        st.dataframe(st.session_state.watchlist, use_container_width=True, hide_index=True)
        csv_bytes = st.session_state.watchlist.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Listeyi CSV olarak indir", csv_bytes, file_name="izleme_listesi.csv", mime="text/csv"
        )
    else:
        st.info("Henüz bir tarama çalıştırılmadı.")

# ------------------------------------------------------------------ Tab 2 --
with tab2:
    st.subheader(f"Sabah Teyidi — Saat {CONFIRMATION_TIME} Sonrası")
    st.markdown(
        "**Bu sekmenin asıl çıktısı, her hisse için hesaplanan "
        "'Gerekli Hacim (Şu An)' rakamıdır.** Bu sayıyı bankanızın/aracı "
        "kurumunuzun uygulamasında **gördüğünüz gerçek zamanlı (gecikmesiz) "
        "hacimle** karşılaştırın: gerçek hacim bu rakamın üzerindeyse, hisse "
        "tipik günlerin ortalamasının üzerinde bir ilgiyle işlem görüyor "
        "demektir ve alım için değerlendirilebilir."
    )
    st.caption(
        f"Açılıştan sonraki ilk yarım saat gürültülü kabul edilir; bu yüzden "
        f"kontrolü saat {CONFIRMATION_TIME} civarından önce çalıştırmamanız önerilir."
    )
    with st.expander("Bu rakam nasıl hesaplanıyor ve veri gecikmesini nasıl aşıyor?", expanded=False):
        st.markdown(
            """
Yahoo Finance verisi BIST için ~15 dakika gecikmeli gelebilir; bu yüzden
uygulamanın **kendi** anlık hacim okuması güvenilir bir karar girdisi
değildir. Bunu aşmak için uygulama, sizin ZATEN ERİŞİMİNİZ OLAN bir kaynağı
— banka/aracı kurum uygulamanızdaki GERÇEK ZAMANLI hacim ekranını —
kullanmanızı önerecek şekilde tasarlandı:

1. Son ~20-40 işlem gününün 5 dakikalık barlarından, gün içindeki her zaman
   dilimi için **ortalama kümülatif hacim eğrisini** (taban çizgisini) çıkarır.
2. Bu taban çizgisinden, **tam olarak şu an** (duvar saatiyle) için, seçtiğiniz
   RVOL eşiğini (ör. 1,2×) tutturmak üzere oluşması gereken hacmi hesaplar —
   bu, "Gerekli Hacim (Şu An)" rakamıdır.
3. Siz bu rakamı bankanızda gördüğünüz GERÇEK hacimle karşılaştırırsınız;
   uygulamanın kendi (gecikmeli) verisine ihtiyaç duymazsınız.

Uygulamanın kendi verisine dayanan "Ön Değerlendirme" sütunu yalnızca bir
çapraz kontrol amaçlıdır; nihai kararı bankanızdaki gerçek hacimle verin.
            """
        )

    uploaded = st.file_uploader("İzleme listesini yükle (opsiyonel, CSV)", type="csv")
    watchlist_df = pd.read_csv(uploaded) if uploaded is not None else st.session_state.watchlist

    if watchlist_df.empty:
        st.info("Önce 'Akşam Tarama' sekmesinden bir liste oluşturun ya da bir CSV yükleyin.")
    else:
        now_str = dt.datetime.now().strftime("%H:%M:%S")
        st.caption(f"Tarayıcınızın yerel saati: {now_str} — BIST saatiyle (Europe/Istanbul) karşılaştırın.")
        if st.button("✅ Gerekli Hacim Eşiklerini Hesapla", type="primary"):
            with st.spinner("Gün içi veriler ve RVOL@Time taban çizgileri hesaplanıyor..."):
                index_ok = get_index_trend_ok(BIST_INDEX_TICKER)
                rows = [
                    confirm_stock(
                        str(r["Hisse"]),
                        float(r["Önerilen Giriş Tetiği"]),
                        index_ok,
                        rvol_threshold=rvol_threshold,
                        rvol_lookback_days=rvol_lookback_days,
                        ceiling_warning_pct=CEILING_WARNING_THRESHOLD_PCT,
                    )
                    for _, r in watchlist_df.iterrows()
                ]
                st.session_state.confirm_df = pd.DataFrame(rows)
                st.session_state.confirm_index_ok = index_ok

        confirm_df = st.session_state.get("confirm_df", pd.DataFrame())
        if not confirm_df.empty:
            if not st.session_state.get("confirm_index_ok", True):
                st.warning(
                    "⚠️ BIST100 endeksi gün içinde belirgin negatif seyrediyor; "
                    "yeni long pozisyon açarken temkinli olun."
                )
            lags = confirm_df["Tahmini Gecikme (dk)"].dropna()
            if not lags.empty:
                st.caption(f"ℹ️ Uygulamanın kendi verisindeki tahmini gecikme: ~{lags.mean():.0f} dakika")

            st.markdown("### 🎯 Aksiyon Kartları — Bankanızdaki Gerçek Hacimle Karşılaştırın")
            for _, row in confirm_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1.3, 1, 1])
                    with c1:
                        st.markdown(f"#### {row['Hisse']}")
                        st.caption(f"Ön değerlendirme (uygulamanın kendi verisine göre): {row['Ön Değerlendirme']}")
                        last_p = row.get("Son Fiyat (uygulama, gecikmeli olabilir)")
                        if pd.notna(last_p):
                            st.caption(f"Son fiyat (gecikmeli olabilir): {last_p} TL")
                    with c2:
                        tl_val = row.get("Gerekli Hacim (Şu An, TL)")
                        st.metric("Gerekli Hacim (TL)", f"{tl_val:,.0f} TL" if pd.notna(tl_val) else "—")
                    with c3:
                        adet_val = row.get("Gerekli Hacim (Şu An, Adet)")
                        st.metric("Gerekli Hacim (Adet/Lot)", f"{adet_val:,.0f}" if pd.notna(adet_val) else "—")
                    st.caption(
                        f"Diğer kontroller — VWAP üstü: {row['VWAP Üstü']} · "
                        f"Tetik üstü: {row['Tetik Üstü']} · Tavan riski: {row['Tavan Riski']}"
                    )
                    st.caption(row["Not"])

            st.caption(
                "ℹ️ TL cinsinden gerekli hacim, uygulamanın en son gördüğü (gecikmeli "
                "olabilecek) fiyat kullanılarak yaklaşık hesaplanmıştır."
            )

            with st.expander("📋 Detaylı tablo (tüm sütunlar, CSV indir)", expanded=False):
                st.dataframe(confirm_df, use_container_width=True, hide_index=True)
                csv_bytes = confirm_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "⬇️ CSV olarak indir", csv_bytes, file_name="sabah_teyit.csv", mime="text/csv"
                )

# ------------------------------------------------------------------ Tab 3 --
with tab3:
    st.subheader("Pozisyon Takip ve Risk Hesaplayıcı")

    col1, col2 = st.columns(2)
    with col1:
        capital = st.number_input("Toplam sermaye (TL)", min_value=0.0, value=100000.0, step=1000.0)
        risk_pct = st.slider("İşlem başına risk (%)", 0.1, 5.0, DEFAULT_RISK_PER_TRADE_PCT)
        entry = st.number_input("Giriş fiyatı (TL)", min_value=0.0, value=0.0, step=0.01)
        stop = st.number_input("Stop-loss fiyatı (TL)", min_value=0.0, value=0.0, step=0.01)
    with col2:
        if entry > 0 and stop > 0 and entry > stop:
            risk_amount = capital * risk_pct / 100
            risk_per_share = entry - stop
            qty = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            target = entry + (entry - stop) * DEFAULT_TARGET_RR
            st.metric("Önerilen adet (risk bazlı)", qty)
            st.metric("Riske atılan tutar", f"{risk_amount:,.0f} TL")
            st.metric(f"Hedef fiyat (R:R 1:{DEFAULT_TARGET_RR:g})", f"{target:,.2f} TL")
        else:
            st.info("Giriş ve stop fiyatlarını girin (giriş, stoptan büyük olmalı).")

    st.markdown("---")
    st.write("**Açık pozisyon ekle**")
    with st.form("add_position", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        sym = c1.text_input("Hisse")
        qty_in = c2.number_input("Adet", min_value=0, step=1)
        entry_in = c3.number_input("Giriş", min_value=0.0, step=0.01)
        stop_in = c4.number_input("Stop", min_value=0.0, step=0.01)
        submitted = st.form_submit_button("Ekle")
        if submitted and sym:
            st.session_state.positions.append(
                {"Hisse": sym.upper(), "Adet": qty_in, "Giriş": entry_in, "Stop": stop_in}
            )

    if st.session_state.positions:
        st.dataframe(pd.DataFrame(st.session_state.positions), use_container_width=True, hide_index=True)
        if st.button("🧹 Tüm pozisyonları temizle"):
            st.session_state.positions = []
            st.rerun()

    st.caption(f"⏰ Unutmayın: tüm pozisyonlar kapanış seansından önce (≈{FORCED_EXIT_TIME}) kapatılmalıdır.")

# ------------------------------------------------------------------ Tab 4 --
with tab4:
    st.subheader("Strateji Özeti")
    st.markdown(
        f"""
Bu uygulama üç aşamalı bir BIST day trading çerçevesini uygular:

1. **🌙 Akşam Tarama** — Borsa kapalıyken, **tüm BIST evreni** ({len(FULL_UNIVERSE)}
   hisse) göreli güç, hacim artışı, trend yapısı, RSI momentumu ve direnç
   yakınlığına göre puanlanır; en güçlü adaylardan bir izleme listesi
   oluşturulur. Toplu (batch) veri indirme sayesinde bu büyüklükte bir evren
   makul sürede taranabilir.
2. **🌅 Sabah Teyidi (saat {CONFIRMATION_TIME} sonrası)** — Açılıştan sonraki
   ilk gürültülü yarım saat beklenir; ardından her hisse için **"Gerekli
   Hacim (Şu An)"** rakamı hesaplanır. Fiyatın VWAP ve önerilen giriş
   tetiğinin üzerinde olup olmadığı ile genel piyasa (BIST100) yönü de
   uygulamanın kendi verisiyle ayrıca kontrol edilir (çapraz kontrol).
3. **🏦 Manuel Alım Kararı** — Kullanıcı, "Gerekli Hacim (Şu An)" rakamını
   kendi banka/aracı kurum uygulamasında gördüğü **gerçek zamanlı hacimle**
   karşılaştırır; gerçek hacim bu eşiğin üzerindeyse alımı kendi
   uygulamasından manuel olarak gerçekleştirir. Bu araç bir broker'a bağlı
   değildir ve emir vermez.
4. **📋 Pozisyon Yönetimi ve Gün Sonu Çıkış** — Önceden belirlenen stop-loss
   ve hedef ile pozisyon yönetilir; tüm pozisyonlar kapanış seansından önce
   (≈{FORCED_EXIT_TIME}) kapatılır; gecelik (overnight) risk taşınmaz.

**RVOL@Time ve veri gecikmesi**

Yahoo Finance verisi gecikmeli olabileceğinden, uygulamanın kendi hacim
okuması güvenilir bir karar girdisi değildir. Bunun yerine "Gerekli Hacim
(Şu An)", geçmiş ~20-40 günün **tam olarak şu anki saatte** tipik olarak
oluşturduğu ortalama hacme dayanarak, seçilen RVOL eşiğini (ör. 1,2×)
tutturmak için gereken hacmi hesaplar. Siz bu sabit referans rakamı,
bankanızdaki GERÇEK ZAMANLI hacimle karşılaştırırsınız — bu da veri
gecikmesi sorununu tamamen devre dışı bırakır, çünkü nihai kıyas uygulamanın
verisiyle değil, sizin gördüğünüz gerçek veriyle yapılır (bkz. "Sabah
Teyit" sekmesindeki ayrıntılı açıklama).

**Riskler ve sınırlamalar**

- Strateji yalnızca **long (alış)** yönlüdür; BIST'te açığa satış kısıtlı
  ve zaman zaman geçici olarak tamamen yasaklanabilmektedir.
- Kullanılan veri kaynağı (Yahoo Finance / yfinance) gecikmeli veya eksik
  olabilir; gerçek zamanlı karar için profesyonel bir veri sağlayıcısı
  kullanmanız önerilir (`strategy/data.py` dosyasındaki fonksiyonları kendi
  veri kaynağınızla değiştirebilirsiniz).
- Hisse evreni (`data/bist_all_tickers.csv`) belirli bir tarihteki BIST
  listesinin anlık görüntüsüdür; yeni halka arzlar/kottan çıkmalar oldukça
  `scripts/build_universe_from_excel.py` ile güncellenmelidir.
- Akademik çalışmalar, day trading yapan bireysel yatırımcıların büyük
  çoğunluğunun zaman içinde zarar ettiğini göstermektedir. Bu araç bir
  karar verme çerçevesi sunar, kazanç garanti etmez.
- Bu uygulama **yatırım danışmanlığı değildir**; işlem maliyetleri (komisyon,
  BSMV) ve kişisel risk toleransınızı ayrıca değerlendirmelisiniz.
        """
    )
