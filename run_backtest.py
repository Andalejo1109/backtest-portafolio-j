"""Ejecuta el laboratorio completo y guarda tablas en output/. Autor: Andrés Alejandro Rodríguez Lozano."""
import pandas as pd
from src.pipeline import run_all, cost_sensitivity, OUT

pd.set_option("display.width", 200); pd.set_option("display.max_columns", 20)
all_res, tables, contribs, log = run_all()
for h, t in tables.items():
    t.to_csv(OUT / f"metricas_{h.split()[0]}a.csv"); print(f"\n=== {h} ===\n", t)
    contribs[h].to_csv(OUT / f"contribucion_{h.split()[0]}a.csv"); print(contribs[h])
cs = cost_sensitivity(); cs.to_csv(OUT / "sensibilidad_costos.csv", index=False)
print(cs.pivot_table(index=["Horizonte", "Portafolio"], columns="bps", values=["Valor final", "XIRR", "Costos"]))
print("\nProxy:", log["proxy_dias"]); print("\n".join(log["validaciones"]))
