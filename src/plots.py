"""Gráficos con nombres estables en output/. Autor: Andrés Alejandro Rodríguez Lozano."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt
from .metrics import twr_index, drawdown

COL = {"Portafolio J (laboratorio)": "#7b5cd6", "Core Alejandro": "#1f9e89", "SPY": "#e07b39"}
def save(fig, path):
    """Guarda PNG (150 dpi) y SVG con el mismo nombre (el SVG es texto: se ve en GitHub)."""
    from pathlib import Path
    path = Path(path)
    fig.savefig(path, dpi=150)
    matplotlib.rcParams["svg.hashsalt"] = "andres-alejandro"   # SVG reproducible
    fig.savefig(path.with_suffix(".svg"), metadata={"Date": None})
    plt.close(fig)

FIRMA = "Andrés Alejandro Rodríguez Lozano · educativo, no es recomendación · datos Yahoo Adj Close"

def curva(results, horizon, path):
    fig, ax = plt.subplots(figsize=(11, 6))
    any_df = None
    for name, r in results.items():
        df = r["df"]; any_df = df
        ax.plot(df.index, df["valor"], color=COL[name], lw=2,
                label=f"{name}: US${df['valor'].iloc[-1]:,.0f}")
    ax.plot(any_df.index, any_df["aportado"], color="grey", ls="--", lw=1.5,
            label=f"Aportado: US${any_df['aportado'].iloc[-1]:,.0f}")
    ax.set_title(f"US\\$1.000 inicial + US\\$200/mes · {horizon} · rebalanceo mensual, 5 bps", fontsize=13)
    ax.yaxis.set_major_formatter(mt.StrMethodFormatter("US${x:,.0f}"))
    ax.grid(alpha=.3); ax.legend(loc="upper left")
    fig.text(0.01, 0.01, FIRMA, fontsize=8, color="grey")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); save(fig, path)

def drawdowns(all_results, path):
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharey=True)
    for ax, (h, results) in zip(axes, all_results.items()):
        for name, r in results.items():
            dd = drawdown(twr_index(r["df"]))
            ax.plot(dd.index, dd * 100, color=COL[name], lw=1.4,
                    label=f"{name} (máx {dd.min():.1%})")
        ax.set_title(f"Drawdown (índice TWR) · {h}"); ax.grid(alpha=.3)
        ax.yaxis.set_major_formatter(mt.PercentFormatter()); ax.legend(loc="lower left")
    fig.text(0.01, 0.01, FIRMA, fontsize=8, color="grey")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); save(fig, path)

def contribucion(contribs, path, label="Portafolio J"):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, (h, c) in zip(axes, contribs.items()):
        s = c["P&L USD"].sort_values()
        colors = ["#c0392b" if v < 0 else "#7b5cd6" for v in s]
        ax.barh(s.index, s.values, color=colors)
        for y, v in enumerate(s.values):
            ax.text(v, y, f" {v:,.0f}", va="center", fontsize=8)
        ax.set_title(f"Contribución en USD a la ganancia · {label} · {h}")
        ax.xaxis.set_major_formatter(mt.StrMethodFormatter("{x:,.0f}")); ax.grid(alpha=.3, axis="x")
    fig.text(0.01, 0.01, FIRMA, fontsize=8, color="grey")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); save(fig, path)
