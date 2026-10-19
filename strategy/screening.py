"""Akşam taraması: borsa kapalıyken, yükseliş potansiyeli yüksek hisseleri
puanlayıp bir izleme listesi oluşturan mantık. Tüm BIST evrenini (600+
hisse) makul sürede tarayabilmek için günlük veriler tek tek değil, toplu
(batch) olarak indirilir."""

from __future__ import annotations

import pandas as pd

from . import indicators as ind
from .data import fetch_universe_daily, get_daily_history


def score_stock(ticker: str, df: pd.DataFrame, index_df: pd.DataFrame, weights: dict) -> dict | None:
    """Önceden indirilmiş günlük veriden (`df`) tek bir hisse için alt
    skorları hesaplar ve ağırlıklı toplam skor üretir."""
    if df is None or df.empty or len(df) < 55:
        return None

    close = df["Close"]
    last_close = float(close.iloc[-1])

    rs = ind.relative_strength_score(df, index_df, lookback=5)
    vol_ratio = ind.volume_ratio(df, window=20)
    ma20 = ind.sma(close, 20).iloc[-1]
    ma50 = ind.sma(close, 50).iloc[-1]
    above_ma20 = pd.notna(ma20) and last_close > ma20
    above_ma50 = pd.notna(ma50) and last_close > ma50
    rsi_val = ind.rsi(close, 14).iloc[-1]
    dist_to_res = ind.distance_to_resistance_pct(df, lookback=20)

    # --- Alt skorlar: hepsi kabaca 0-100 arasına normalize edilmiş sezgisel ölçekler ---
    rs_score = max(0.0, min(100.0, 50 + rs * 5))
    vol_score = max(0.0, min(100.0, (vol_ratio - 0.5) * 66.7))
    trend_score = 100.0 if (above_ma20 and above_ma50) else (50.0 if above_ma20 else 0.0)
    rsi_score = max(0.0, min(100.0, 100 - abs(float(rsi_val) - 60) * 3.3)) if pd.notna(rsi_val) else 50.0
    breakout_score = max(0.0, min(100.0, 100 + dist_to_res * 10))

    weight_sum = sum(weights.values()) or 1
    total = (
        rs_score * weights.get("relative_strength", 0)
        + vol_score * weights.get("volume", 0)
        + trend_score * weights.get("trend", 0)
        + rsi_score * weights.get("momentum_rsi", 0)
        + breakout_score * weights.get("breakout_proximity", 0)
    ) / weight_sum

    swing_low = float(df["Low"].iloc[-10:].min())
    recent_high = float(df["High"].iloc[-21:-1].max()) if len(df) >= 21 else last_close
    entry_trigger = round(max(last_close, recent_high) * 1.001, 2)

    return {
        "Hisse": ticker.replace(".IS", ""),
        "Son Kapanış": round(last_close, 2),
        "Skor": round(total, 1),
        "Göreli Güç (5g,%)": round(rs, 2),
        "Hacim Oranı": round(vol_ratio, 2),
        "RSI(14)": round(float(rsi_val), 1) if pd.notna(rsi_val) else None,
        "Trend (MA20/50 üstü)": "Evet" if (above_ma20 and above_ma50) else "Kısmen" if above_ma20 else "Hayır",
        "Direnç Mesafesi (%)": round(dist_to_res, 2),
        "Önerilen Giriş Tetiği": entry_trigger,
        "Önerilen Stop": round(swing_low, 2),
        "Önerilen Hedef": round(max(last_close, recent_high) * 1.04, 2),
    }


def run_evening_screen(
    universe: list[str],
    weights: dict,
    top_n: int = 10,
    index_ticker: str = "XU100.IS",
    chunk_size: int = 100,
    progress_callback=None,
) -> pd.DataFrame:
    """Verilen hisse evrenini (tüm BIST olabilir, 600+ hisse) toplu olarak
    indirir, puanlar ve en iyi `top_n` hisseyi skoruna göre azalan sırada
    döndürür. `progress_callback(ratio)` verilirse tarama ilerlemesini
    0-1 arası bir oranla bildirir (veri indirme + puanlama birlikte)."""
    index_df = get_daily_history(index_ticker, period="4mo")

    def _download_progress(ratio: float) -> None:
        if progress_callback:
            progress_callback(ratio * 0.85)  # indirme, ilerlemenin ~%85'i

    batch = fetch_universe_daily(
        universe, period="4mo", chunk_size=chunk_size, progress_callback=_download_progress
    )

    rows = []
    total = len(universe) or 1
    for i, ticker in enumerate(universe):
        try:
            row = score_stock(ticker, batch.get(ticker), index_df, weights)
            if row is not None:
                rows.append(row)
        except Exception:
            continue
        if progress_callback and i % 25 == 0:
            progress_callback(0.85 + 0.15 * (i + 1) / total)

    if progress_callback:
        progress_callback(1.0)

    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows).sort_values("Skor", ascending=False).reset_index(drop=True)
    return result.head(top_n)
