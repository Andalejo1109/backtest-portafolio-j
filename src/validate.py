"""Validaciones (asserts) antes de reportar. Autor: Andrés Alejandro Rodríguez Lozano."""
import numpy as np
import pandas as pd
from .backtest import run, contribution_dates

def check_panel(rets):
    assert not rets.isna().any().any(), "Hay NaN en el panel de retornos"
    assert np.isfinite(rets.to_numpy()).all()
    assert (rets.abs() < 0.5).all().all(), "Retorno diario fuera de rango (>50%)"

def check_monthly_range(rets):
    m = (1 + rets).resample("ME").prod() - 1
    assert (m > -0.6).all().all() and (m < 1.0).all().all(), "Retorno mensual fuera de rango"
    return m.min().min(), m.max().max()

def check_weights(w):
    assert abs(sum(w.values()) - 1) < 1e-12, "Pesos no suman 1"
    assert all(v >= 0 for v in w.values()), "Pesos negativos"

def check_flows(df, initial, monthly, n_expected):
    nflows = int((df["flujo"] > 0).sum())
    n = nflows - 1
    assert n == n_expected, f"Conteo de aportes mensuales {n} != {n_expected}"
    assert abs(df["aportado"].iloc[-1] - (initial + monthly * n)) < 1e-6, "Aportes totales no cuadran"
    return n

def check_no_lookahead(rets, w, cut_frac=0.5, **kw):
    """Si se alteran los retornos FUTUROS (después de una fecha), el camino hasta esa fecha
    debe ser idéntico. Si el motor usara información futura, cambiaría."""
    df1, _, _ = run(rets, w, **kw)
    cut = rets.index[int(len(rets) * cut_frac)]
    r2 = rets.copy()
    r2.loc[r2.index > cut] = r2.loc[r2.index > cut] * -3 + 0.01
    df2, _, _ = run(r2, w, **kw)
    assert np.allclose(df1.loc[:cut, "valor"], df2.loc[:cut, "valor"]), "Look-ahead detectado"
    return cut

def check_accounting(df, pnl):
    """Valor final = aportes + P&L de activos - costos."""
    lhs = df["valor"].iloc[-1]
    rhs = df["aportado"].iloc[-1] + pnl.to_numpy().sum() - df["costo"].sum()
    assert abs(lhs - rhs) < 1e-6 * max(1, lhs), f"Contabilidad no cuadra {lhs} vs {rhs}"
