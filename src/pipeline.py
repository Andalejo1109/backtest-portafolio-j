"""Orquesta todo el laboratorio. Autor: Andrés Alejandro Rodríguez Lozano."""
from pathlib import Path
import pandas as pd
from . import config as C
from .data import get_prices, first_valid_dates
from .backtest import build_returns, run
from .metrics import summarize, subperiod, contributions, monthly_returns
from . import validate as V
from . import plots as P

OUT = Path(__file__).resolve().parents[1] / "output"

def expected_months(start, end_idx):
    s = pd.Timestamp(start); e = end_idx[-1]
    return (e.year - s.year) * 12 + (e.month - s.month)

def run_all(cost_bps=C.COST_BPS, make_plots=True, verbose=True):
    OUT.mkdir(exist_ok=True)
    px = get_prices(C.ALL_TICKERS + ([C.PROXY] if C.PROXY not in C.ALL_TICKERS else []))
    fv = first_valid_dates(px)
    log = {"primer_dato": fv, "proxy_dias": {}, "validaciones": []}
    all_res, tables, contribs = {}, {}, {}
    for h, start in C.HORIZONS.items():
        res = {}
        core_mr = None
        for name in ["Core Alejandro", "Portafolio J (laboratorio)", "SPY"]:
            w = C.PORTFOLIOS[name]
            V.check_weights(w)
            rets, mask = build_returns(px, list(w), start, C.END, C.PROXY)
            V.check_panel(rets)
            lo, hi = V.check_monthly_range(rets)
            df, pnl, holds = run(rets, w, C.INITIAL, C.MONTHLY, cost_bps)
            n = V.check_flows(df, C.INITIAL, C.MONTHLY, expected_months(start, rets.index))
            V.check_accounting(df, pnl)
            cut = V.check_no_lookahead(rets, w, initial=C.INITIAL, monthly=C.MONTHLY, cost_bps=cost_bps)
            log["validaciones"].append(f"{h} · {name}: panel sin NaN ({rets.shape[0]} sesiones × {rets.shape[1]}), "
                                       f"pesos suman 1, mensual en [{lo:.1%}, {hi:.1%}], {n} aportes mensuales + inicial, "
                                       f"aportado={df['aportado'].iloc[-1]:,.0f}=1000+200×{n}, sin look-ahead (corte {cut:%Y-%m-%d}), contabilidad cuadra")
            prox = {t: int(mask[t].sum()) for t in w if mask[t].sum() > 0}
            if prox: log["proxy_dias"][(h, name)] = {t: (int(mask[t].sum()), mask.index[mask[t]].min().date(), mask.index[mask[t]].max().date()) for t in prox}
            res[name] = {"df": df, "pnl": pnl, "holds": holds}
            if name == "Core Alejandro":
                core_mr = monthly_returns(df)
            res[name]["metrics"] = summarize(df, bench_monthly=core_mr if name != "Core Alejandro" else None)
            res[name]["2020"] = subperiod(df, "2020-01-01", "2020-12-31")
            res[name]["2022"] = subperiod(df, "2022-01-01", "2022-12-31")
        order = ["Portafolio J (laboratorio)", "Core Alejandro", "SPY"]
        res = {k: res[k] for k in order}
        all_res[h] = res
        t = pd.DataFrame({k: v["metrics"] for k, v in res.items()})
        for y in ["2020", "2022"]:
            t.loc[f"{y} retorno"] = [res[k][y]["Retorno"] for k in order]
            t.loc[f"{y} max DD"] = [res[k][y]["Max DD"] for k in order]
        tables[h] = t
        contribs[h] = contributions(res["Portafolio J (laboratorio)"]["pnl"], res["Portafolio J (laboratorio)"]["df"])
        if make_plots:
            tag = h.split()[0]
            P.curva(res, h, OUT / f"curva_valor_{tag}a.png")
    if make_plots:
        P.drawdowns(all_res, OUT / "drawdown.png")
        P.contribucion(contribs, OUT / "contribucion_activos.png")
    return all_res, tables, contribs, log

def cost_sensitivity():
    rows = []
    for bps in C.COST_SENS:
        _, tables, _, _ = run_all(cost_bps=bps, make_plots=False)
        for h, t in tables.items():
            for name in t.columns:
                rows.append({"Horizonte": h, "Portafolio": name, "bps": bps,
                             "Valor final": t.loc["Valor final", name], "XIRR": t.loc["XIRR (MWR)", name],
                             "CAGR TWR": t.loc["CAGR (TWR)", name], "Costos": t.loc["Costos acumulados", name]})
    return pd.DataFrame(rows)
