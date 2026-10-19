"""Motor del backtest diario con aportes mensuales y rebalanceo en el día del aporte.
Autor: Andrés Alejandro Rodríguez Lozano. Uso educativo."""
import numpy as np
import pandas as pd

def build_returns(px, tickers, start, end, proxy="SPY"):
    """Retornos diarios simples de Adjusted Close. Si un ticker no existía, se rellena
    con el retorno diario del proxy (método sensibilidad). Devuelve (rets, mask_proxy)."""
    px = px.loc[:end]
    rets = px.pct_change(fill_method=None)
    rets = rets.loc[start:end]
    out, mask = {}, {}
    for t in tickers:
        r = rets[t].copy()
        m = r.isna()
        r[m] = rets[proxy][m]
        out[t], mask[t] = r, m
    return pd.DataFrame(out), pd.DataFrame(mask)

def contribution_dates(index):
    """Primer día hábil (primera sesión con precio) de cada mes."""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby([index.year, index.month]).first().values)

def run(rets, weights, initial=1000.0, monthly=200.0, cost_bps=5.0):
    """Simulación diaria.
    - Día del aporte (cierre): entra el flujo, se rebalancea a pesos objetivo, se cobra
      cost_bps sobre el nocional negociado (compras + ventas).
    - Los retornos del día t se aplican a las tenencias al cierre de t-1 (sin look-ahead).
    El primer día solo entra el aporte inicial (sin retorno previo)."""
    # weights: dict fijo {ticker: peso} o DataFrame de calendario (índice = fecha desde la que
    # aplica, columnas = tickers). Con calendario se usa la última fila con fecha <= día del aporte.
    sched = weights if isinstance(weights, pd.DataFrame) else None
    tick = list(sched.columns) if sched is not None else list(weights)
    if sched is None:
        w = np.array([weights[t] for t in tick])
        assert abs(w.sum() - 1) < 1e-9
    R = rets[tick].to_numpy()
    idx = rets.index
    cdates = set(contribution_dates(idx))
    n, k = len(idx), len(tick)
    hold = np.zeros(k)
    V = np.zeros(n); flow = np.zeros(n); cost = np.zeros(n); traded = np.zeros(n)
    sells = np.zeros(n); pnl = np.zeros((n, k)); hold_hist = np.zeros((n, k))
    for i, d in enumerate(idx):
        if i > 0:
            pnl[i] = hold * R[i]
            hold = hold * (1 + R[i])
        if d in cdates:
            if sched is not None:
                avail = sched.loc[:d]
                assert len(avail), f"Sin pesos disponibles para {d}"
                w = avail.iloc[-1][tick].to_numpy(dtype=float)
                assert abs(w.sum() - 1) < 1e-9
            f = initial if i == 0 else monthly
            tot = hold.sum() + f
            # costo aplicado sobre el nocional; se resuelve para que post-costo quede en pesos objetivo
            target = w * tot
            trade = target - hold
            c = cost_bps / 1e4 * np.abs(trade).sum()
            target = w * (tot - c)
            trade = target - hold
            hold = target
            flow[i], cost[i] = f, c
            traded[i] = np.abs(trade).sum(); sells[i] = -trade[trade < 0].sum()
        V[i] = hold.sum(); hold_hist[i] = hold
    df = pd.DataFrame({"valor": V, "flujo": flow, "costo": cost, "negociado": traded,
                       "ventas": sells}, index=idx)
    df["aportado"] = df["flujo"].cumsum()
    prev = df["valor"].shift(1)
    # TWR diario: (V_t - flujo_t) / V_{t-1} - 1 ; el costo queda dentro del retorno
    df["ret"] = (df["valor"] - df["flujo"]) / prev - 1
    df.iloc[0, df.columns.get_loc("ret")] = (df["valor"].iloc[0] - df["flujo"].iloc[0]) / df["flujo"].iloc[0]
    pnl = pd.DataFrame(pnl, index=idx, columns=tick)
    holds = pd.DataFrame(hold_hist, index=idx, columns=tick)
    return df, pnl, holds
