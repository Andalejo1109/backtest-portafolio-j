# Laboratorio de optimización · Portafolio J
Andrés Alejandro Rodríguez Lozano · educativo, no es recomendación. Generado con `python -m src.lab_optim` (código en `src/optim.py`, `src/lab_optim.py`).
- Escenarios A–E: se cortan activos y su peso se reparte proporcionalmente entre los que quedan (tope 50%).
- Walk-forward: cada octubre (2016–2026), pesos max-Sharpe (rf 4%) y mínima varianza estimados con los 60 meses cerrados previos (el primero, oct-2016, usa 59: nov-2011–sep-2016, porque SCHD no tiene oct-2011 completo). Long-only, 2% ≤ w ≤ 50% si se incluye. Ventana OOS: oct-2016–oct-2026 (no hay 15 años OOS sin inventar historia).
- Max-Sharpe in-sample: optimista, con look-ahead.
- Flujo US$1.000 + US$200/mes, rebalanceo mensual, 5 bps. Ver `log_corrida.txt` para todas las cifras.
