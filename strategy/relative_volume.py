"""'Relative Volume at Time' (zamana göre göreli hacim, kısaca RVOL@Time).

PROBLEM: yfinance/Yahoo Finance verisi BIST için ~15 dakika gecikmeli
gelebilir. Uygulama saat 10:30'da çalıştırıldığında elinizdeki "son" bar
aslında ~10:15'e ait olabilir. Üstelik günün SADECE bir bölümü geçmişken
"bugünkü hacim" ile "günlük ortalama hacmi" kıyaslamak da yanıltıcıdır:
BIST'te hacim gün içinde düz dağılmaz, açılışta ve kapanışa yakın yoğunlaşan
bir "U" eğrisi izler; saat 10:30'a kadar normal bir günde bile günlük hacmin
ancak küçük bir kısmı gerçekleşmiş olabilir.

ÇÖZÜM: "Bugün saat X itibarıyla görülen hacmi", "geçmişte TAM OLARAK AYNI
SAATTE (X) tipik olarak görülen ortalama hacim" ile kıyaslıyoruz. Kıyaslama
noktası (X) olarak her zaman ELİMİZDEKİ EN SON VERİNİN KENDİ ZAMAN DAMGASI
kullanılır — "şu an" sabit varsayılmaz. Böylece veri ister 2 dakika ister 20
dakika gecikmeli gelsin, kıyaslama her zaman adil (zamanı eşlenmiş) kalır;
veri gecikmesi sonucu sistematik olarak bozmaz.

Örnek: Uygulamayı 10:30'da çalıştırdınız ama son bar 10:15'e ait.
    RVOL(10:15) = (bugün 10:15'e kadar oluşan hacim) / (son N günün
                   10:15'e kadar oluşturduğu ORTALAMA hacim)
Bu oran 1.0'ın üzerindeyse, hisse o ana kadar alışıldığından daha fazla
işlem görmüş demektir — momentum/ilgi sinyali. Ayrıca "eşik hacim" (bir RVOL
hedefini tutturmak için saat X'e kadar oluşması gereken hacim) de
hesaplanabilir, böylece "hacim şu rakamın üzerindeyse alabilirsin" şeklinde
somut bir karşılaştırma yapılabilir.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from .data import get_intraday_history, get_intraday_history_long


def _minute_of_day(ts) -> int:
    return ts.hour * 60 + ts.minute


def build_volume_time_profile(ticker: str, lookback_days: int = 20) -> pd.Series | None:
    """Son `lookback_days` tam işlem gününe ait 5 dakikalık barlardan, gün
    içindeki her zaman dilimi (dakika-of-day) için ORTALAMA KÜMÜLATİF hacim
    eğrisini üretir. Dönen Series'in indeksi dakika-of-day'dir (10:00 ->
    600); değeri, o saate kadar geçmişte tipik olarak biriken ortalama
    hacimdir. Bugünün kendisi hariç tutulur (henüz tamamlanmamış bir gün
    taban çizgisini bozar)."""
    hist = get_intraday_history_long(ticker, days=60, interval="5m")
    if hist.empty or "Volume" not in hist.columns:
        return None

    hist = hist.copy()
    hist["date"] = hist.index.date
    hist["minute_of_day"] = [_minute_of_day(ts) for ts in hist.index]

    today = dt.datetime.now().date()
    daily_frames = []
    for date, g in hist.groupby("date"):
        if date == today:
            continue
        g = g.sort_index()
        g = g.assign(cum_volume=g["Volume"].cumsum())
        daily_frames.append(g[["minute_of_day", "cum_volume"]])

    if not daily_frames:
        return None

    daily_frames = daily_frames[-lookback_days:] if len(daily_frames) > lookback_days else daily_frames
    combined = pd.concat(daily_frames)
    profile = combined.groupby("minute_of_day")["cum_volume"].mean().sort_index()
    return profile if not profile.empty else None


def _lookup_baseline(profile: pd.Series, minute_of_day: int) -> float | None:
    """Verilen dakika-of-day için profildeki en yakın (küçük-eşit) taban
    değerini döndürür; henüz o dakikaya ait veri yoksa profildeki ilk
    değeri kullanır (gün henüz başlamamışsa aşırı düşük bir değerle
    kıyaslamayı önlemek için)."""
    if profile is None or profile.empty:
        return None
    idx = profile.index[profile.index <= minute_of_day]
    if len(idx) == 0:
        return float(profile.iloc[0])
    return float(profile.loc[idx.max()])


def get_relative_volume_at_time(ticker: str, lookback_days: int = 20) -> dict | None:
    """Bugünün (gecikmeli gelebilecek) en güncel verisine göre, GERÇEK VERİ
    ZAMAN DAMGASI baz alınarak göreli hacmi (RVOL@Time) hesaplar.

    Döndürülen sözlük:
      - data_timestamp / data_time_str: elimizdeki en son barın zaman damgası
      - estimated_lag_minutes: bu zaman damgasının "şimdi"den kaç dakika
        geride olduğu (yaklaşık veri gecikmesi göstergesi)
      - today_cum_volume: bugün, data_timestamp'e kadar oluşan toplam hacim
      - baseline_at_data_time: geçmişte aynı saatte tipik ortalama hacim
      - rvol_at_data_time: today_cum_volume / baseline_at_data_time — ANA
        KARAR METRİĞİ, veri gecikmesinden bağımsız olarak adil bir kıyastır
      - baseline_at_now / conservative_rvol_now: "şu an" için taban ve bugünkü
        hacmin o tabana oranı — veri gecikmesi nedeniyle bu değer gerçek
        güncel RVOL'un ALT SINIRI (muhafazakâr tahmini) olarak okunmalıdır,
        çünkü aradan geçen dakikalarda gerçekte daha fazla işlem olmuş olabilir
    """
    intraday_today = get_intraday_history(ticker, period="1d", interval="5m")
    if intraday_today.empty or "Volume" not in intraday_today.columns:
        return None

    profile = build_volume_time_profile(ticker, lookback_days=lookback_days)
    if profile is None:
        return None

    last_ts = intraday_today.index[-1]
    data_minute = _minute_of_day(last_ts)
    now_minute = _minute_of_day(dt.datetime.now())

    today_cum_volume = float(intraday_today["Volume"].sum())
    baseline_at_data_time = _lookup_baseline(profile, data_minute)
    baseline_at_now = _lookup_baseline(profile, now_minute)

    rvol_at_data_time = (
        today_cum_volume / baseline_at_data_time
        if baseline_at_data_time and baseline_at_data_time > 0
        else None
    )
    conservative_rvol_now = (
        today_cum_volume / baseline_at_now
        if baseline_at_now and baseline_at_now > 0
        else None
    )

    return {
        "data_timestamp": last_ts,
        "data_time_str": last_ts.strftime("%H:%M"),
        "estimated_lag_minutes": max(0, now_minute - data_minute),
        "today_cum_volume": today_cum_volume,
        "baseline_at_data_time": baseline_at_data_time,
        "baseline_at_now": baseline_at_now,
        "rvol_at_data_time": rvol_at_data_time,
        "conservative_rvol_now": conservative_rvol_now,
    }


def required_volume_for_threshold(
    ticker: str,
    threshold: float,
    lookback_days: int = 20,
    at_minute: int | None = None,
) -> float | None:
    """Belirli bir RVOL eşiğini sağlamak için, verilen dakikaya (varsayılan:
    şu an) kadar oluşması gereken kümülatif hacmi döndürür. Örn. eşik=1.5 ve
    sonuç=820.000 ise: "bu hisse saat X'e kadar en az 820.000 lot işlem
    görmüşse, tipik günlerin 1,5 katı hacimle işlem görüyor" denebilir."""
    profile = build_volume_time_profile(ticker, lookback_days=lookback_days)
    if profile is None:
        return None
    minute = at_minute if at_minute is not None else _minute_of_day(dt.datetime.now())
    baseline = _lookup_baseline(profile, minute)
    if baseline is None:
        return None
    return baseline * threshold
