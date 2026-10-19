"""'Tüm hisse' Excel dosyasından (İş Yatırım tarzı bir export; bir sütunda
hisse kodlarının bulunduğu herhangi bir .xlsx) yfinance uyumlu (.IS sonekli)
BIST hisse listesi üretir ve data/bist_all_tickers.csv dosyasına yazar.

BIST'te yeni halka arzlar / kottan çıkmalar olduğunda listeyi güncellemek
için, güncel bir "tüm hisse" dosyasıyla bu script'i tekrar çalıştırın:

    python scripts/build_universe_from_excel.py tumhisse.xlsx
    python scripts/build_universe_from_excel.py tumhisse.xlsx --sheet isyatirim --column Hisse
"""

from __future__ import annotations

import argparse
import csv
import pathlib

import pandas as pd

_ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d", "\ufeff"]


def clean_ticker(raw) -> str:
    s = str(raw)
    for ch in _ZERO_WIDTH_CHARS:
        s = s.replace(ch, "")
    return s.strip().upper()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx_path", help="Hisse kodlarını içeren .xlsx dosyasının yolu")
    parser.add_argument("--sheet", default=0, help="Sayfa adı veya indeksi (varsayılan: ilk sayfa)")
    parser.add_argument("--column", default="Hisse", help="Hisse kodu sütununun adı (varsayılan: 'Hisse')")
    args = parser.parse_args()

    df = pd.read_excel(args.xlsx_path, sheet_name=args.sheet)
    if args.column not in df.columns:
        raise SystemExit(
            f"'{args.column}' sütunu bulunamadı. Mevcut sütunlar: {list(df.columns)}\n"
            f"Doğru sütun adını --column ile belirtin."
        )

    tickers = sorted({clean_ticker(v) for v in df[args.column] if str(v).strip()})
    if not tickers:
        raise SystemExit("Hiç geçerli hisse kodu bulunamadı.")

    out_path = pathlib.Path(__file__).resolve().parent.parent / "data" / "bist_all_tickers.csv"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Kod", "Ticker"])
        for t in tickers:
            writer.writerow([t, f"{t}.IS"])

    print(f"{len(tickers)} hisse yazıldı -> {out_path}")


if __name__ == "__main__":
    main()
