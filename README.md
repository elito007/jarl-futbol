# jarl-futbol

Evaluación de apuestas de fútbol (bwin). Mismo método que `jarl-f1`: primero medir, sin dinero.
- **Claude** diseña y programa. **Jarl** despliega, descarga y ejecuta. **Elito** decide.

## Fase 1 — backtest con histórico (football-data.co.uk)
- `descargar_futbol.py` — resultados, estadísticas (córners, tarjetas) y cuotas de cierre de 7 ligas desde 2019 → `datos/historico/partidos.csv`.
- `backtest_goles.py` — más/menos 2,5 goles: modelo Poisson por equipo vs cuotas reales de cierre (media, Bet365, máxima).
- `backtest_corners_tarjetas.py` — frecuencias por liga/línea y calibración de un modelo por equipo (no hay cuotas históricas de estos mercados).
Resultados en `analisis/`.

## Fase 2 — capturas de bwin y liquidación (desde 29-sep-2026)
- `bwin_futbol.py` — UNA petición trae las 7 ligas con todos sus mercados; guarda solo partidos de la ventana y mercados simples (goles, córners, tarjetas, resultado…) en `datos/cuotas/*.csv.gz`.
- `captura_auto.py` / `captura_auto.sh` — cron horario sin LLM: captura de la mañana + una por franja de inicio (≈5 un sábado, 1-2 entre semana); liquidación diaria; informe semanal los lunes a Telegram.
- `liquidar_futbol.py` — resuelve cada selección con football-data → `datos/liquidaciones/<fecha>.csv`.
- `informe_mercados.py` — el mismo de jarl-f1: bwin vs realidad por tipo de mercado y lado, ROI, CLV, calibración.
- `bwin_base.py` — copia de `bwin_snapshot.py` de jarl-f1 (cabeceras, curl_cffi).
