"""Descarga de precios ajustados (Yahoo vía yfinance) con caché parquet.
Autor: Andrés Alejandro Rodríguez Lozano. Uso educativo."""
from pathlib import Path
import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def get_prices(tickers, start="2011-01-01", end="2026-10-19", refresh=False):
    """Devuelve Adjusted Close diario (columnas = tickers). Cachea en data/precios.parquet."""
    DATA_DIR.mkdir(exist_ok=True)
    cache = DATA_DIR / "precios.parquet"
    if cache.exists() and not refresh:
        px = pd.read_parquet(cache)
        if set(tickers).issubset(px.columns):
            return px[list(tickers)]
    raw = yf.download(list(tickers), start=start, end=end, auto_adjust=False,
                      progress=False, threads=True)
    px = raw["Adj Close"].copy()
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px = px.sort_index()
    px.to_parquet(cache)
    return px[list(tickers)]

def first_valid_dates(px):
    return px.apply(lambda s: s.first_valid_index())
