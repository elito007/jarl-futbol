# Log de Jarl — jarl-futbol


## 28-sep-2026 — Tarea A: instalación, descarga y backtests

- Repo clonado en /opt/data/futbol (aparte de f1 y scripts). `descargar_futbol.py` → `partidos.csv: 19978 partidos, 56 liga-temporadas` (exit 0, sin fallos).
- `backtest_goles.py` exit 0: modelo log-loss 0.7020 vs mercado 0.6711 (el mercado gana); ROI negativo en todos los umbrales/fuentes (solo `max` ≈ -1.8%). Por liga, todo negativo (mejor E0 -2.5% y SP1 -3.5%).
- `backtest_corners_tarjetas.py` exit 0: frecuencias por liga y calibración del modelo; bien calibrado en el rango central (60-80%), peor en extremos. Salidas completas pegadas en conversacion/2026-09-28.md.
- Commit de datos/historico/ y analisis/, entrada en log, push. Sin cron todavía (la tarea no lo pide).