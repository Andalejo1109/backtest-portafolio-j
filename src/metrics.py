"""Métricas de desempeño y riesgo. Autor: Andrés Alejandro Rodríguez Lozano."""
import numpy as np
import pandas as pd
from scipy.optimize import brentq

def xirr(dates, cfs):
    t = np.array([(d - dates[0]).days / 365.25 for d in dates])
    f = lambda r: np.sum(cfs / (1 + r) ** t)
    return brentq(f, -0.99, 10)

def twr_index(df):
    return (1 + df["ret"]).cumprod()

def monthly_returns(df):
    idx = twr_index(df)
    m = idx.resample("ME").last()
    first = pd.Series([1.0], index=[df.index[0] - pd.Timedelta(days=1)])
    return pd.concat([first, m]).pct_change().dropna()

def drawdown(series):
    return series / series.cummax() - 1

def underwater_stats(dd):
    uw = dd < 0
    longest, cur, start, best = 0, 0, None, (None, None)
    for d, u in uw.items():
        if u:
            if cur == 0: start = d
            cur += 1
            if cur > longest: longest, best = cur, (start, d)
        else:
            cur = 0
    days = (best[1] - best[0]).days if best[0] is not None else 0
    return uw.mean(), days, best

def summarize(df, bench_monthly=None, rf_annual=0.04):
    idx = twr_index(df)
    years = (df.index[-1] - df.index[0]).days / 365.25
    cagr = idx.iloc[-1] ** (1 / years) - 1
    flows = df.loc[df["flujo"] > 0, "flujo"]
    dates = list(flows.index) + [df.index[-1]]
    cfs = np.array(list(-flows.values) + [df["valor"].iloc[-1]])
    mr = monthly_returns(df)
    vol = mr.std() * np.sqrt(12)
    rf_m = (1 + rf_annual) ** (1 / 12) - 1
    sharpe0 = mr.mean() * 12 / vol
    sharpe4 = (mr - rf_m).mean() * 12 / vol
    dn0 = np.sqrt((np.minimum(mr, 0) ** 2).mean()) * np.sqrt(12)
    dn4 = np.sqrt((np.minimum(mr - rf_m, 0) ** 2).mean()) * np.sqrt(12)
    dd = drawdown(idx)
    mdd = dd.min()
    ulcer = float(np.sqrt(((dd * 100) ** 2).mean()))
    pct_uw, longest_days, (uw_s, uw_e) = underwater_stats(dd)
    avg_v = df["valor"].mean()
    out = {
        "Capital aportado": df["aportado"].iloc[-1],
        "Valor final": df["valor"].iloc[-1],
        "Ganancia": df["valor"].iloc[-1] - df["aportado"].iloc[-1],
        "CAGR (TWR)": cagr,
        "XIRR (MWR)": xirr(dates, cfs),
        "Volatilidad": vol,
        "Sharpe rf=0": sharpe0,
        "Sharpe rf=4%": sharpe4,
        "Sortino rf=0": mr.mean() * 12 / dn0,
        "Sortino rf=4%": (mr - rf_m).mean() * 12 / dn4,
        "Max DD": mdd,
        "Calmar": cagr / abs(mdd),
        "Ulcer": ulcer,
        "% tiempo bajo agua": pct_uw,
        "Racha bajo agua (días)": longest_days,
        "Racha bajo agua (periodo)": f"{uw_s:%Y-%m-%d} → {uw_e:%Y-%m-%d}" if uw_s is not None else "-",
        "Turnover anual (una vía)": df["ventas"].sum() / avg_v / years,
        "Costos acumulados": df["costo"].sum(),
    }
    if bench_monthly is not None:
        a = (mr - bench_monthly.reindex(mr.index)).dropna()
        out["Tracking error vs core"] = a.std() * np.sqrt(12)
    return out

def subperiod(df, start, end):
    """Retorno TWR y max drawdown dentro de un subperiodo."""
    idx = twr_index(df).loc[:end]
    before = idx[idx.index < pd.Timestamp(start)]
    base = before.iloc[-1] if len(before) else 1.0
    sub = idx.loc[start:end]
    path = pd.concat([pd.Series([base]), sub.reset_index(drop=True)])
    ddmin = (path / path.cummax() - 1).min()
    return {"Retorno": sub.iloc[-1] / base - 1, "Max DD": ddmin}

def contributions(pnl, df):
    c = pnl.sum()
    res = pd.DataFrame({"P&L USD": c})
    res.loc["Costos"] = -df["costo"].sum()
    gain = df["valor"].iloc[-1] - df["aportado"].iloc[-1]
    res["% de la ganancia"] = res["P&L USD"] / gain
    return res
