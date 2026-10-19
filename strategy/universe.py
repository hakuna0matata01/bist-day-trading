"""BIST hisse evreni yönetimi.

`data/bist_all_tickers.csv` dosyası, kullanıcının yüklediği tüm-hisse
listesinden (`scripts/build_universe_from_excel.py` ile) üretilmiştir ve
yfinance formatında (".IS" sonekli) 634 BIST hissesi içerir. Liste zamanla
eskiyebilir (yeni halka arzlar, kottan çıkanlar); güncellemek için güncel bir
"tüm hisse" Excel dosyasıyla o script'i tekrar çalıştırmanız yeterlidir.
"""

from __future__ import annotations

import csv
import pathlib

_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
_UNIVERSE_FILE = _DATA_DIR / "bist_all_tickers.csv"

# CSV dosyası herhangi bir sebeple bulunamazsa kullanılacak küçük yedek liste
_FALLBACK_UNIVERSE = [
    "AKBNK", "GARAN", "ISCTR", "YKBNK", "VAKBN", "HALKB", "THYAO", "BIMAS",
    "EREGL", "KCHOL", "SAHOL", "ASELS", "FROTO", "TOASO", "ARCLK", "TCELL",
    "SISE", "KOZAL", "PETKM", "TUPRS", "SASA", "PGSUS", "TAVHL", "ENKAI",
]


def load_all_bist_tickers() -> list[str]:
    """`data/bist_all_tickers.csv` dosyasından yfinance formatında (.IS ekli)
    tüm BIST hisse kodlarını okur. Dosya yoksa/boşsa küçük bir yedek liste
    döndürülür."""
    if _UNIVERSE_FILE.exists():
        try:
            with open(_UNIVERSE_FILE, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                tickers = [row["Ticker"].strip() for row in reader if row.get("Ticker", "").strip()]
            if tickers:
                return tickers
        except Exception:
            pass
    return [f"{t}.IS" for t in _FALLBACK_UNIVERSE]
