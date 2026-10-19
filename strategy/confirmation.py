"""Sabah teyidi: saat 10:30'dan sonra, akşamdan belirlenen izleme
listesindeki hisseler için ALIM KARARINDA KULLANILACAK HACİM EŞİĞİNİ üretir.

KULLANIM MODELİ: Bu uygulama bir broker/aracı kurum API'sine bağlı değildir
ve alım emri vermez. Tasarlandığı kullanım şekli şudur:

  1. Akşamdan izleme listesi oluşturulur (bkz. screening.py).
  2. Sabah saat 10:30 civarında bu uygulama açılır; her hisse için "ŞU AN
     itibarıyla, tipik günlerin `rvol_threshold` katı hacimle işlem görmüş
     sayılmak için gereken kümülatif hacim" hesaplanır (hem adet/lot hem de
     yaklaşık TL cinsinden).
  3. Kullanıcı bu rakamı, kendi banka/aracı kurum uygulamasında GÖRDÜĞÜ
     GERÇEK ZAMANLI (gecikmesiz) hacimle karşılaştırır.
  4. Gerçek hacim bu eşiğin üzerindeyse, hisse "tipik günlerin üzerinde
     ilgi görüyor" kabul edilip manuel olarak alınabilir.

Yani bu modülün ürettiği "Gerekli Hacim (Şu An)" rakamı NİHAİ KARAR
GİRDİSİDİR; uygulamanın kendi (yfinance kaynaklı, gecikmeli olabilen) hacim
okuması yalnızca YARDIMCI/ÇAPRAZ KONTROL amaçlıdır ve asıl karar için
kullanılmamalıdır.

Taban çizgisi yöntemi (`relative_volume.py`), geçmişte TAM OLARAK AYNI
SAATTE tipik olarak oluşan ortalama hacme dayanır; böylece "10:30'da hisse
yükselebilmesi için ne kadar hacme sahip olmalı" sorusuna somut bir sayısal
cevap üretilir."""

from __future__ import annotations

import pandas as pd

from . import indicators as ind
from . import relative_volume as rv
from .data import get_daily_history, get_intraday_history


def _normalize_ticker(ticker_short: str) -> str:
    t = ticker_short.strip().upper()
    return t if t.endswith(".IS") else f"{t}.IS"


def _fallback_volume_check(daily: pd.DataFrame, today_cum_volume: float) -> bool:
    """RVOL@Time hesaplanamadığında (ör. yeterli geçmiş gün içi veri yoksa)
    kullanılan basit yedek kontrol: uygulamanın kendi (gecikmeli) hacim
    okuması, 20 günlük ortalama günlük hacmin en az %15'ine ulaşmış mı?
    Bu yalnızca bir çapraz kontroldür; esas karar "Gerekli Hacim (Şu An)"
    rakamının banka uygulamasındaki gerçek hacimle kıyaslanmasıyla verilir."""
    if len(daily) < 21:
        return False
    avg_daily_vol_20 = float(daily["Volume"].iloc[-21:-1].mean())
    if not avg_daily_vol_20 or avg_daily_vol_20 <= 0:
        return False
    return today_cum_volume >= 0.15 * avg_daily_vol_20


def confirm_stock(
    ticker_short: str,
    trigger_price: float,
    index_trend_ok: bool,
    rvol_threshold: float = 1.2,
    rvol_lookback_days: int = 20,
    ceiling_warning_pct: float = 1.5,
) -> dict:
    """Tek bir hisse için sabah teyit kriterlerini değerlendirir ve en
    önemlisi, kullanıcının banka/aracı kurum uygulamasındaki gerçek zamanlı
    hacimle karşılaştıracağı eşik değerini ("Gerekli Hacim (Şu An)") üretir.
    """
    ticker = _normalize_ticker(ticker_short)
    intraday = get_intraday_history(ticker, period="1d", interval="5m")
    daily = get_daily_history(ticker, period="2mo")

    if intraday.empty or daily.empty:
        return {
            "Hisse": ticker_short,
            "Gerekli Hacim (Şu An, Adet)": None,
            "Gerekli Hacim (Şu An, TL)": None,
            "Ön Değerlendirme": "Veri Yok",
            "Son Fiyat (uygulama, gecikmeli olabilir)": None,
            "Uygulamanın Veri Saati": None,
            "Tahmini Gecikme (dk)": None,
            "RVOL (uygulamanın kendi verisine göre)": None,
            "Uygulamanın Gördüğü Hacim (gecikmeli)": None,
            "VWAP Üstü": None,
            "Tetik Üstü": None,
            "Tavan Riski": None,
            "Not": "Veri alınamadı (ticker kodunu veya bağlantıyı kontrol edin)",
        }

    last_price = float(intraday["Close"].iloc[-1])
    vwap_series = ind.vwap(intraday)
    last_vwap = float(vwap_series.iloc[-1]) if pd.notna(vwap_series.iloc[-1]) else None
    above_vwap = (last_vwap is not None) and (last_price >= last_vwap)
    above_trigger = last_price >= trigger_price

    today_cum_volume = float(intraday["Volume"].sum())

    # --- ASIL ÇIKTI: "ŞU AN" (gerçek duvar saati) için gereken hacim eşiği.
    # Kullanıcı bunu banka/aracı kurum uygulamasındaki GERÇEK ZAMANLI hacimle
    # karşılaştıracaktır; bu yüzden uygulamanın kendi (gecikmeli) verisinin
    # zaman damgasına değil, "şimdi"ye göre hesaplanır.
    required_volume_now = rv.required_volume_for_threshold(
        ticker, threshold=rvol_threshold, lookback_days=rvol_lookback_days
    )
    required_volume_now_tl = required_volume_now * last_price if required_volume_now else None

    # --- Uygulamanın KENDİ (gecikmeli olabilen) verisine göre ön/çapraz kontrol ---
    rvol_info = rv.get_relative_volume_at_time(ticker, lookback_days=rvol_lookback_days)
    if rvol_info is not None and rvol_info.get("rvol_at_data_time") is not None:
        rvol_value = rvol_info["rvol_at_data_time"]
        volume_ok_preliminary = rvol_value >= rvol_threshold
        data_time_str = rvol_info["data_time_str"]
        lag_minutes = rvol_info["estimated_lag_minutes"]
        volume_note = None
    else:
        volume_ok_preliminary = _fallback_volume_check(daily, today_cum_volume)
        rvol_value = None
        data_time_str = intraday.index[-1].strftime("%H:%M")
        lag_minutes = None
        volume_note = "RVOL@Time hesaplanamadı (yetersiz geçmiş veri); ön değerlendirme basit hacim kıyasına dayanıyor"

    prev_close = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else None
    ceiling_price = prev_close * 1.10 if prev_close else None
    ceiling_risk = False
    if ceiling_price:
        ceiling_risk = (ceiling_price - last_price) / ceiling_price * 100 <= ceiling_warning_pct

    passed_preliminary = (
        above_vwap and above_trigger and volume_ok_preliminary and index_trend_ok and not ceiling_risk
    )

    reasons = []
    if not above_vwap:
        reasons.append("VWAP altında")
    if not above_trigger:
        reasons.append("tetik seviyesinin altında")
    if not volume_ok_preliminary:
        if rvol_value is not None:
            reasons.append(f"uygulamanın kendi verisine göre RVOL yetersiz ({rvol_value:.2f} < eşik {rvol_threshold:.2f})")
        else:
            reasons.append("uygulamanın kendi verisine göre hacim teyidi yetersiz")
    if not index_trend_ok:
        reasons.append("genel piyasa yönü olumsuz")
    if ceiling_risk:
        reasons.append("tavana çok yakın (likidite riski)")
    if volume_note:
        reasons.append(volume_note)
    reasons.append("asıl kararı bankanızdaki GERÇEK ZAMANLI hacimle 'Gerekli Hacim (Şu An)' rakamını kıyaslayarak verin")

    return {
        "Hisse": ticker_short,
        "Gerekli Hacim (Şu An, Adet)": int(required_volume_now) if required_volume_now else None,
        "Gerekli Hacim (Şu An, TL)": round(required_volume_now_tl, 0) if required_volume_now_tl else None,
        "Ön Değerlendirme": "✅ Geçti" if passed_preliminary else "❌ Geçemedi",
        "Son Fiyat (uygulama, gecikmeli olabilir)": round(last_price, 2),
        "Uygulamanın Veri Saati": data_time_str,
        "Tahmini Gecikme (dk)": lag_minutes,
        "RVOL (uygulamanın kendi verisine göre)": round(rvol_value, 2) if rvol_value is not None else None,
        "Uygulamanın Gördüğü Hacim (gecikmeli)": int(today_cum_volume),
        "VWAP Üstü": "Evet" if above_vwap else "Hayır",
        "Tetik Üstü": "Evet" if above_trigger else "Hayır",
        "Tavan Riski": "Evet" if ceiling_risk else "Hayır",
        "Not": ", ".join(reasons),
    }


def get_index_trend_ok(index_ticker: str = "XU100.IS", threshold_pct: float = -1.0) -> bool:
    """BIST100 endeksinin gün içi performansının kabul edilebilir sınırın
    (varsayılan -%1) altına düşüp düşmediğini kontrol eder. Veri yoksa,
    hatalı biçimde işlem engellememek için varsayılan olarak True döner."""
    intraday = get_intraday_history(index_ticker, period="1d", interval="5m")
    if intraday.empty or len(intraday) < 2:
        return True
    change_pct = (intraday["Close"].iloc[-1] / intraday["Close"].iloc[0] - 1) * 100
    return change_pct > threshold_pct
