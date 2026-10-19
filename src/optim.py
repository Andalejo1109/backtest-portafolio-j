"""Escenarios de corte, redundancia y optimización walk-forward (sin look-ahead).
Autor: Andrés Alejandro Rodríguez Lozano. Laboratorio educativo, no es recomendación."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

CAP, FLOOR = 0.50, 0.02

def cut_and_redistribute(base, drop, cap=CAP):
    """Quita 'drop' y reparte su peso proporcionalmente entre los que quedan, con tope 'cap'
    (el exceso sobre el tope se vuelve a repartir entre los no topados)."""
    w = {k: v for k, v in base.items() if k not in drop}
    s = sum(w.values()); w = {k: v / s for k, v in w.items()}
    for _ in range(50):
        over = {k: v for k, v in w.items() if v > cap + 1e-12}
        if not over: break
        excess = sum(v - cap for v in over.values())
        free = {k: v for k, v in w.items() if k not in over}
        fs = sum(free.values())
        w = {k: (cap if k in over else v + excess * v / fs) for k, v in w.items()}
    assert abs(sum(w.values()) - 1) < 1e-12 and max(w.values()) <= cap + 1e-12
    return w

def monthly_panel(daily_rets):
    return (1 + daily_rets).resample("ME").prod() - 1

# ---------- redundancia ----------
def risk_contrib(w, cov):
    w = np.asarray(w); sp2 = w @ cov @ w
    return w * (cov @ w) / sp2

def redundancy_table(mret, weights):
    tick = list(weights); X = mret[tick]
    cov = X.cov().to_numpy() * 12
    w = np.array([weights[t] for t in tick])
    rc = risk_contrib(w, cov)
    vol_i = np.sqrt(np.diag(cov)); vol_p = np.sqrt(w @ cov @ w)
    r2 = {}
    for t in tick:
        y = X[t].to_numpy(); Z = X.drop(columns=t).to_numpy()
        Z1 = np.column_stack([np.ones(len(Z)), Z])
        beta, *_ = np.linalg.lstsq(Z1, y, rcond=None)
        res = y - Z1 @ beta
        r2[t] = 1 - res.var() / y.var()
    df = pd.DataFrame({"Peso": w, "Vol anual": vol_i, "Contribución al riesgo": rc,
                       "Riesgo/Peso": rc / w, "R² vs los demás": [r2[t] for t in tick],
                       "Corr con VT": [X[t].corr(X["VT"]) for t in tick]}, index=tick)
    summary = {"Vol portafolio": vol_p, "Ratio diversificación (Σwσ/σp)": (w @ vol_i) / vol_p,
               "N efectivo por pesos (1/Σw²)": 1 / np.sum(w ** 2),
               "N efectivo por riesgo (1/Σrc²)": 1 / np.sum(rc ** 2)}
    return df, summary

# ---------- optimización ----------
def _solve(mu, cov, kind, rf_m, lb, ub, n_starts=8, seed=0):
    n = len(mu); rng = np.random.default_rng(seed)
    if kind == "maxsharpe":
        obj = lambda w: -((w @ mu - rf_m) / np.sqrt(w @ cov @ w))
    else:
        obj = lambda w: w @ cov @ w
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    best = None
    for k in range(n_starts):
        x0 = np.full(n, 1 / n) if k == 0 else rng.dirichlet(np.ones(n))
        x0 = np.clip(x0, lb, ub); x0 = x0 / x0.sum()
        r = minimize(obj, x0, method="SLSQP", bounds=list(zip(lb, ub)), constraints=cons,
                     options={"maxiter": 500, "ftol": 1e-12})
        if r.success and (best is None or r.fun < best.fun): best = r
    assert best is not None, "Optimizador no convergió"
    return best.x

def optimize(mret_window, kind, rf_annual=0.04, cap=CAP, floor=FLOOR):
    """Long-only, cada activo <= cap y >= floor si se incluye (semicontinuo):
    1) resolver con [0, cap]; 2) sacar activos < floor; 3) re-resolver con [floor, cap]; repetir."""
    tick = list(mret_window.columns)
    rf_m = (1 + rf_annual) ** (1 / 12) - 1
    active = tick[:]
    first = True
    for _ in range(10):
        X = mret_window[active]; mu = X.mean().to_numpy(); cov = X.cov().to_numpy()
        n = len(active)
        lb = np.zeros(n) if first else np.full(n, floor)
        ub = np.full(n, cap)
        w = _solve(mu, cov, kind, rf_m, lb, ub)
        keep = [a for a, x in zip(active, w) if x >= floor - 1e-9]
        if not first and len(keep) == len(active): break
        active = keep; first = False
    out = pd.Series(0.0, index=tick); out[active] = w
    out[out < 1e-10] = 0; out = out / out.sum()
    return out

def walk_forward(mret, rebal_dates, kind, window=60, min_window=59):
    """Para cada fecha de re-optimización d (día del aporte de octubre) usa SOLO meses
    completos que terminan antes de d (último = mes anterior). Devuelve calendario de pesos
    indexado por d y un log con la ventana usada."""
    rows, log = {}, []
    for d in rebal_dates:
        hist = mret[mret.index < d.to_period("M").to_timestamp()]  # meses cerrados antes del mes de d
        hist = hist.dropna().iloc[-window:]
        assert len(hist) >= min_window, f"Historia insuficiente en {d}: {len(hist)}"
        assert hist.index[-1] < d, "Look-ahead en la ventana de estimación"
        rows[d] = optimize(hist, kind)
        log.append({"Fecha aplicación": d.date(), "Ventana desde": hist.index[0].strftime("%Y-%m"),
                    "Ventana hasta": hist.index[-1].strftime("%Y-%m"), "Meses": len(hist)})
    sched = pd.DataFrame(rows).T
    return sched, pd.DataFrame(log)
