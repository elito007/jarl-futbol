# jarl-futbol

Evaluación de apuestas de fútbol (bwin). Mismo método que `jarl-f1`: primero medir, sin dinero.
- **Claude** diseña y programa. **Jarl** despliega, descarga y ejecuta. **Elito** decide.

## Fase 1 — backtest con histórico (football-data.co.uk)
- `descargar_futbol.py` — resultados, estadísticas (córners, tarjetas) y cuotas de cierre de 7 ligas desde 2019 → `datos/historico/partidos.csv`.
- `backtest_goles.py` — más/menos 2,5 goles: modelo Poisson por equipo vs cuotas reales de cierre (media, Bet365, máxima).
- `backtest_corners_tarjetas.py` — frecuencias por liga/línea y calibración de un modelo por equipo (no hay cuotas históricas de estos mercados).
Resultados en `analisis/`.

## Fase 2 (si la fase 1 da algo) — capturas de bwin y papel, reutilizando lo de `jarl-f1`.
