"""Veri çekme fonksiyonları (Yahoo Finance / yfinance üzerinden).

NOT: Yahoo Finance verileri Borsa İstanbul için genellikle gecikmeli olabilir
(pratikte ~15 dakika civarı) ve bazı hisselerde eksik/düzensiz gelebilir.
Gerçek zamanlı day trading kararları için profesyonel bir veri sağlayıcısı
(ör. Matriks, Foreks, TradingView, aracı kurumunuzun kendi API'si) kullanmanız
önerilir. Bu modül, stratejinin mantığını ücretsiz ve kolay erişilebilir bir
veri kaynağıyla çalışır hâle getirmek için tasarlanmıştır; `get_*`
fonksiyonlarının içini kendi veri kaynağınızla değiştirerek uygulamayı
canlı/gerçek zamanlı bir veri akışına bağlayabilirsiniz.

Veri gecikmesi handikapı `strategy/relative_volume.py` modülünde, hacmi
"şu anın" sabit bir referansıyla değil, ELİMİZDEKİ EN SON VERİNİN KENDİ ZAMAN
DAMGASIYLA aynı saatteki tarihsel ortalamayla kıyaslayarak ele alınır — bkz.
o modülün başındaki açıklama.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_daily_history(ticker: str, period: str = "4mo") -> pd.DataFrame:
    """Tek bir hisse için günlük OHLCV verisini döndürür."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df is None or df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_daily_history_batch(tickers: tuple[str, ...], period: str = "4mo") -> dict:
    """Birden fazla hisseyi TEK yfinance çağrısıyla indirir (günlük veri).

    Yüzlerce hisse için tekil `Ticker().history()` çağrısını tekrarlamaktan
    çok daha hızlıdır; tüm BIST evrenini (600+ hisse) akşam taramasında
    taramak için kullanılır. `tickers` bir tuple olmalıdır (Streamlit
    önbelleği için hashlenebilir olması gerekir); sıralamanın önemi yoktur.
    """
    if not tickers:
        return {}
    try:
        raw = yf.download(
            tickers=list(tickers),
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
    except Exception:
        return {}

    result: dict[str, pd.DataFrame] = {}

    if len(tickers) == 1:
        t = tickers[0]
        if raw is not None and not raw.empty:
            df = raw.dropna(how="all")
            if not df.empty and "Close" in df.columns:
                result[t] = df
        return result

    for t in tickers:
        try:
            df = raw[t].dropna(how="all")
        except Exception:
            continue
        if not df.empty and "Close" in df.columns and df["Close"].notna().any():
            result[t] = df
    return result


def fetch_universe_daily(
    tickers: Iterable[str],
    period: str = "4mo",
    chunk_size: int = 100,
    progress_callback=None,
) -> dict:
    """`tickers` listesini küçük gruplar (chunk) hâlinde indirir ve
    sonuçları birleştirir. Her grup ayrı önbelleklendiği için, tekrar
    çalıştırmalarda (ttl süresi içinde) zaten indirilmiş gruplar tekrar
    indirilmez. `progress_callback(ratio: float)` verilirse, her grup
    tamamlandığında 0-1 arası ilerleme oranıyla çağrılır (ör. Streamlit
    ilerleme çubuğunu güncellemek için)."""
    tickers = list(tickers)
    if not tickers:
        return {}
    chunks = [tickers[i : i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    all_results: dict[str, pd.DataFrame] = {}
    for i, chunk in enumerate(chunks):
        batch = get_daily_history_batch(tuple(chunk), period=period)
        all_results.update(batch)
        if progress_callback:
            progress_callback((i + 1) / len(chunks))
    return all_results


@st.cache_data(ttl=60 * 2, show_spinner=False)
def get_intraday_history(ticker: str, period: str = "1d", interval: str = "5m") -> pd.DataFrame:
    """Bugüne ait gün içi (intraday) OHLCV verisini döndürür (sabah teyidi
    için kullanılır). Not: Yahoo Finance bu veriyi gecikmeli sağlayabilir;
    dönen son barın zaman damgası, verinin gerçekte hangi ana ait olduğunu
    gösteren güvenilir referanstır."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        if df is None or df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def get_intraday_history_long(ticker: str, days: int = 60, interval: str = "5m") -> pd.DataFrame:
    """'Relative Volume at Time' taban çizgisini (geçmiş günlerin saat-bazlı
    kümülatif hacim eğrisini) hesaplamak için uzun dönemli gün içi veri
    çeker. Yahoo Finance, 5 dakikalık barlarda genelde son ~60 günü sağlar.
    Bu veri gün içinde pek değişmediğinden önbellek süresi (ttl) uzun
    tutulmuştur."""
    try:
        df = yf.Ticker(ticker).history(period=f"{days}d", interval=interval)
        if df is None or df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()


def get_last_price_and_prev_close(ticker: str) -> tuple:
    """Son kapanış ve bir önceki kapanış fiyatını döndürür."""
    df = get_daily_history(ticker, period="5d")
    if df.empty or len(df) < 2:
        return None, None
    return float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2])
