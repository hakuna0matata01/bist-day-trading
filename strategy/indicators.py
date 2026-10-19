"""Teknik gösterge hesaplamaları.

Tüm fonksiyonlar saf pandas/numpy ile yazılmıştır, ek bir teknik analiz
kütüphanesine ihtiyaç duymaz.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Basit hareketli ortalama."""
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Göreli Güç Endeksi (Relative Strength Index)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)


def relative_strength_score(stock_df: pd.DataFrame, index_df: pd.DataFrame, lookback: int = 5) -> float:
    """Son `lookback` işlem gününde hissenin BIST100 endeksine göre göreli
    performansı, yüzde puan cinsinden (hisse getirisi - endeks getirisi)."""
    if len(stock_df) < lookback + 1 or len(index_df) < lookback + 1:
        return 0.0
    stock_ret = stock_df["Close"].iloc[-1] / stock_df["Close"].iloc[-lookback - 1] - 1
    index_ret = index_df["Close"].iloc[-1] / index_df["Close"].iloc[-lookback - 1] - 1
    return float((stock_ret - index_ret) * 100)


def volume_ratio(df: pd.DataFrame, window: int = 20) -> float:
    """Son günün hacminin, kendisinden önceki `window` günlük ortalama
    hacme oranı. 1.0 = ortalama, 2.0 = ortalamanın iki katı hacim."""
    if len(df) < window + 1:
        return 1.0
    avg_vol = df["Volume"].iloc[-window - 1:-1].mean()
    if not avg_vol or np.isnan(avg_vol) or avg_vol == 0:
        return 1.0
    return float(df["Volume"].iloc[-1] / avg_vol)


def distance_to_resistance_pct(df: pd.DataFrame, lookback: int = 20) -> float:
    """Son kapanışın, kendisinden önceki `lookback` günlük en yüksek
    seviyeye (potansiyel direnç) olan uzaklığı, yüzde cinsinden.
    Negatif değer direncin altında, pozitif değer direncin üzerinde
    (kırılım gerçekleşmiş) olunduğu anlamına gelir."""
    if len(df) < lookback + 1:
        return 0.0
    recent_high = df["High"].iloc[-lookback - 1:-1].max()
    last_close = df["Close"].iloc[-1]
    if not recent_high or np.isnan(recent_high) or recent_high == 0:
        return 0.0
    return float((last_close - recent_high) / recent_high * 100)


def vwap(intraday_df: pd.DataFrame) -> pd.Series:
    """Gün içi veriden kümülatif Hacim Ağırlıklı Ortalama Fiyat (VWAP)."""
    typical_price = (intraday_df["High"] + intraday_df["Low"] + intraday_df["Close"]) / 3
    cum_vol = intraday_df["Volume"].cumsum()
    cum_vol_price = (typical_price * intraday_df["Volume"]).cumsum()
    return cum_vol_price / cum_vol.replace(0, np.nan)
