"""Laboratorio de optimización del Portafolio J. Autor: Andrés Alejandro Rodríguez Lozano.
Educativo, no es recomendación. Ejecutar: python -m src.lab_optim"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt
from . import config as C
from .data import get_prices
from .backtest import build_returns, run, contribution_dates
from .metrics import summarize, subperiod, monthly_returns
from . import validate as V
from .plots import save
from .optim import cut_and_redistribute, redundancy_table, walk_forward, optimize, CAP, FLOOR

OUT = Path(__file__).resolve().parents[1] / "output" / "optimizacion"
FIRMA = "Andrés Alejandro Rodríguez Lozano · laboratorio educativo, no es recomendación · datos Yahoo Adj Close"
J = C.PORTFOLIOS["Portafolio J (laboratorio)"]
UNIV = list(J)
SCEN_DEF = {"A original": [], "B sin REMX+MCHI": ["REMX", "MCHI"],
            "C sin REMX+MCHI+ITA": ["REMX", "MCHI", "ITA"],
            "D sin REMX+MCHI+ITA+BLK": ["REMX", "MCHI", "ITA", "BLK"],
            "E solo ETFs (sin COHR)": ["REMX", "MCHI", "ITA", "BLK", "COHR"]}
WINDOWS = {"10 años": ("2016-10-01", C.END), "15 años": ("2011-10-01", C.END)}
SENS = {"2016–2021": ("2016-10-01", "2021-09-30"), "2021–2026": ("2021-10-01", C.END)}

def expected_months(start, idx):
    s = pd.Timestamp(start); e = idx[-1]
    return (e.year - s.year) * 12 + (e.month - s.month)

def backtest(px, weights, start, end, validations, label):
    tick = list(weights.columns) if isinstance(weights, pd.DataFrame) else list(weights)
    if isinstance(weights, dict):
        V.check_weights(weights)
        if not (label.endswith("SPY") or "Core" in label):
            assert max(weights.values()) <= CAP + 1e-9, f"Peso > 50% en {label}"
    rets, mask = build_returns(px, tick, start, end, C.PROXY)
    V.check_panel(rets); V.check_monthly_range(rets)
    df, pnl, _ = run(rets, weights, C.INITIAL, C.MONTHLY, C.COST_BPS)
    n = V.check_flows(df, C.INITIAL, C.MONTHLY, expected_months(start, rets.index))
    V.check_accounting(df, pnl)
    V.check_no_lookahead(rets, weights, initial=C.INITIAL, monthly=C.MONTHLY, cost_bps=C.COST_BPS)
    validations.append(f"{label}: sin NaN, {n} aportes + inicial = US${df['aportado'].iloc[-1]:,.0f}, sin look-ahead, contabilidad OK")
    return df

def metric_row(df, n_assets, core_mr=None, subs=True):
    m = summarize(df, bench_monthly=core_mr)
    row = {"# activos": n_assets, "Aportado": m["Capital aportado"], "Valor final": m["Valor final"],
           "XIRR": m["XIRR (MWR)"], "CAGR TWR": m["CAGR (TWR)"], "Vol": m["Volatilidad"],
           "Sharpe rf=4%": m["Sharpe rf=4%"], "Sortino rf=4%": m["Sortino rf=4%"], "Max DD": m["Max DD"],
           "Calmar": m["Calmar"], "Ulcer": m["Ulcer"]}
    if subs:
        for y in ["2020", "2022"]:
            s = subperiod(df, f"{y}-01-01", f"{y}-12-31")
            row[f"{y} ret"] = s["Retorno"]; row[f"{y} DD"] = s["Max DD"]
    return row

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tick_all = sorted(set(UNIV) | set(C.PORTFOLIOS["Core Alejandro"]) | {"SPY"})
    px = get_prices(C.ALL_TICKERS)
    vals = []
    # ---- 1) escenarios ----
    scen = {k: cut_and_redistribute(J, d) for k, d in SCEN_DEF.items()}
    pd.DataFrame(scen).T.fillna(0)[UNIV].to_csv(OUT / "pesos_escenarios.csv")
    # ---- 3) walk-forward (necesita 59-60 meses de historia real de los 9) ----
    pxm = px[UNIV].resample("ME").last()
    mret = pxm.pct_change(fill_method=None)            # NaN donde no hay historia real (sin proxy)
    idx10 = px.loc["2016-10-01":C.END].index
    cds = contribution_dates(idx10)
    rebal = [d for d in cds if d.month == 10]
    wf, wflog = {}, {}
    for kind, lab in [("maxsharpe", "WF max-Sharpe (OOS)"), ("minvar", "WF mín. varianza (OOS)")]:
        sched, log = walk_forward(mret, rebal, kind)
        for _, r in sched.iterrows():
            assert abs(r.sum() - 1) < 1e-9 and r.max() <= CAP + 1e-9
            assert ((r == 0) | (r >= FLOOR - 1e-9)).all(), "Peso entre 0 y 2%"
        # prueba de look-ahead del walk-forward: alterar el futuro no cambia pesos pasados
        cut = pd.Timestamp("2020-12-31"); m2 = mret.copy(); m2.loc[m2.index > cut] *= -2
        s2, _ = walk_forward(m2, rebal, kind)
        early = sched.index[sched.index < pd.Timestamp("2021-01-01")]
        assert np.allclose(sched.loc[early], s2.loc[early]), "Look-ahead en walk-forward"
        vals.append(f"{lab}: pesos suman 1, ≤50%, 0 o ≥2%; ventana termina antes de cada fecha; alterar retornos >2020-12 no cambia pesos 2016-2020")
        wf[lab] = sched; wflog[lab] = log
        sched.to_csv(OUT / f"pesos_{kind}_walkforward.csv"); log.to_csv(OUT / f"ventanas_{kind}.csv", index=False)
    # in-sample (optimista, con look-ahead)
    ins = {}
    for h, (s, e) in WINDOWS.items():
        mw = mret.loc[pd.Timestamp(s) + pd.offsets.MonthEnd(0): "2026-09-30"].dropna()
        ins[h] = optimize(mw, "maxsharpe")
    pd.DataFrame(ins).T.to_csv(OUT / "pesos_insample_maxsharpe.csv")
    # ---- 4) métricas principales ----
    tables, dfs = {}, {}
    for h, (s, e) in WINDOWS.items():
        core_df = backtest(px, C.PORTFOLIOS["Core Alejandro"], s, e, vals, f"{h} · Core")
        core_mr = monthly_returns(core_df)
        rows, dd = {}, {}
        for k, w in scen.items():
            df = backtest(px, w, s, e, vals, f"{h} · {k}"); dd[k] = df
            rows[k] = metric_row(df, len(w), core_mr)
        if h == "10 años":
            for lab, sched in wf.items():
                df = backtest(px, sched, s, e, vals, f"{h} · {lab}"); dd[lab] = df
                rows[lab] = metric_row(df, f"{int((sched > 0).sum(axis=1).min())}–{int((sched > 0).sum(axis=1).max())}", core_mr)
        w_is = {k: v for k, v in ins[h].items() if v > 0}
        lab = "Max-Sharpe in-sample (optimista, con look-ahead)"
        df = backtest(px, w_is, s, e, vals, f"{h} · {lab}"); dd[lab] = df
        rows[lab] = metric_row(df, len(w_is), core_mr)
        for lab, w in [("SPY", C.PORTFOLIOS["SPY"])]:
            df = backtest(px, w, s, e, vals, f"{h} · SPY"); dd[lab] = df; rows[lab] = metric_row(df, 1, core_mr)
        dd["Core Alejandro"] = core_df; rows["Core Alejandro"] = metric_row(core_df, 5)
        t = pd.DataFrame(rows).T; tables[h] = t; dfs[h] = dd
        t.to_csv(OUT / f"metricas_escenarios_{h.split()[0]}a.csv")
    # ---- sensibilidad por subventanas ----
    sens_rows = []
    for w_lab, (s, e) in SENS.items():
        for k, w in list(scen.items()) + [("SPY", C.PORTFOLIOS["SPY"]), ("Core Alejandro", C.PORTFOLIOS["Core Alejandro"])]:
            df = backtest(px, w, s, e, vals, f"{w_lab} · {k}")
            r = metric_row(df, len(w), subs=False); r.update({"Ventana": w_lab, "Escenario": k}); sens_rows.append(r)
    sens = pd.DataFrame(sens_rows); sens.to_csv(OUT / "sensibilidad_subventanas.csv", index=False)
    # ---- 2) redundancia ----
    m10 = mret.loc["2016-10-31":"2026-09-30"]; m15 = mret.loc["2011-11-30":"2026-09-30"]
    assert not m10.isna().any().any() and not m15.isna().any().any()
    corr = m10.corr(); corr.to_csv(OUT / "correlacion_mensual_10a.csv"); m15.corr().to_csv(OUT / "correlacion_mensual_15a.csv")
    red, red_sum = {}, {}
    for k in ["A original", "D sin REMX+MCHI+ITA+BLK", "E solo ETFs (sin COHR)"]:
        red[k], red_sum[k] = redundancy_table(m10, scen[k])
        red[k].to_csv(OUT / f"redundancia_{k.split()[0]}.csv")
    pd.DataFrame(red_sum).to_csv(OUT / "diversificacion_resumen.csv")
    # ---- 5) gráficos ----
    plots(tables, wf, corr)
    return tables, sens, wf, wflog, ins, red, red_sum, corr, vals, scen

COLS = {"A": "#7b5cd6", "B": "#8e72de", "C": "#a18ae6", "D": "#b4a2ee", "E": "#c7baf5",
        "W": "#3a7bd5", "M": "#7fb3f0", "X": "#bbbbbb", "S": "#e07b39", "C2": "#1f9e89"}
def color(k):
    if k.startswith("WF max"): return COLS["W"]
    if k.startswith("WF mín"): return COLS["M"]
    if k.startswith("Max-Sharpe in"): return COLS["X"]
    if k == "SPY": return COLS["S"]
    if k.startswith("Core"): return COLS["C2"]
    return COLS[k[0]]

def short(k):
    return k.replace("Max-Sharpe in-sample (optimista, con look-ahead)", "Max-Sharpe IS*").replace(" (OOS)", "")

def plots(tables, wf, corr):
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, (h, t) in zip(axes, tables.items()):
        v = t["Valor final"].astype(float)
        ax.bar(range(len(v)), v.values, color=[color(k) for k in v.index])
        for i, x in enumerate(v.values): ax.text(i, x, f"{x/1000:,.1f}k", ha="center", va="bottom", fontsize=8)
        ax.axhline(t["Aportado"].iloc[0], color="grey", ls="--", lw=1)
        ax.set_xticks(range(len(v))); ax.set_xticklabels([short(k) for k in v.index], rotation=40, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mt.StrMethodFormatter("{x:,.0f}")); ax.grid(alpha=.3, axis="y")
        ax.set_title(f"Valor final por escenario · {h} (línea = aportado)")
    fig.text(0.01, 0.01, FIRMA + " · *IS = con look-ahead", fontsize=8, color="grey")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); save(fig, OUT / "valor_final_escenarios.png")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, (h, t) in zip(axes, tables.items()):
        for k, r in t.iterrows():
            ax.scatter(r["Vol"] * 100, r["CAGR TWR"] * 100, s=90, color=color(k), edgecolor="k", zorder=3)
            lbl = k.split()[0] if k[0] in "ABCDE" and k[1] == " " else short(k)
            ax.annotate(lbl, (r["Vol"] * 100, r["CAGR TWR"] * 100), fontsize=7, xytext=(4, 4), textcoords="offset points")
        ax.set_xlabel("Volatilidad anual (%)"); ax.set_ylabel("CAGR TWR (%)"); ax.grid(alpha=.3)
        ax.set_title(f"Riesgo vs retorno · {h}  (A original · B −REMX/MCHI · C −ITA · D −BLK · E −COHR)", fontsize=10)
    fig.text(0.01, 0.01, FIRMA, fontsize=8, color="grey")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); save(fig, OUT / "riesgo_retorno.png")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    cmap = plt.get_cmap("tab10")
    for ax, (lab, s) in zip(axes, wf.items()):
        years = [d.year for d in s.index]
        bottom = np.zeros(len(s))
        for i, t in enumerate(s.columns):
            ax.bar(years, s[t].values * 100, bottom=bottom, color=cmap(i), label=t, width=0.8)
            bottom += s[t].values * 100
        ax.set_title(f"{lab}: pesos aplicados cada octubre (ventana 60m previa)")
        ax.yaxis.set_major_formatter(mt.PercentFormatter()); ax.set_ylim(0, 100)
    axes[0].legend(ncol=9, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, 1.25))
    fig.text(0.01, 0.01, FIRMA, fontsize=8, color="grey")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); save(fig, OUT / "pesos_walkforward.png")

    fig, ax = plt.subplots(figsize=(8.5, 7))
    im = ax.imshow(corr.values, cmap="RdYlGn_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=45)
    ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.index)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, shrink=.8)
    ax.set_title("Correlación mensual · Portafolio J · oct-2016–sep-2026")
    fig.text(0.01, 0.01, FIRMA, fontsize=7, color="grey")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); save(fig, OUT / "correlacion.png")

if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    tables, sens, wf, wflog, ins, red, red_sum, corr, vals, scen = main()
    print(pd.DataFrame(scen).T.fillna(0).round(4))
    for h, t in tables.items(): print("\n==", h, "==\n", t.to_string(float_format=lambda x: f"{x:,.4f}"))
    print("\n", sens.set_index(["Ventana", "Escenario"])[["Valor final", "XIRR", "CAGR TWR", "Vol", "Sharpe rf=4%", "Max DD", "Calmar"]].to_string(float_format=lambda x: f"{x:,.4f}"))
    for k, v in wf.items(): print("\n", k, "\n", v.round(3)); print(wflog[k].iloc[[0, -1]])
    print("\nIn-sample:\n", pd.DataFrame(ins).T.round(3))
    for k, v in red.items(): print("\n", k, "\n", v.round(3), "\n", {a: round(b, 3) for a, b in red_sum[k].items()})
    print("\n", corr.round(2))
    print("\nValidaciones:", len(vals)); print("\n".join(vals[:3]), "...")
