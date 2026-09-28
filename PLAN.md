# Plan — jarl-futbol (28-sep-2026)

- Decidido por Elito: segundo deporte = fútbol (más volumen y mercados que tenis). Repo aparte de jarl-f1.
- Ligas: Premier, Championship, LaLiga, LaLiga 2, Serie A, Bundesliga, Ligue 1. Temporadas desde 2019/20.
- Mercados de la fase 1: goles más/menos 2,5 (con cuotas históricas reales) y córners/tarjetas (solo frecuencias y calibración).
- Combinadas y «Crea tu apuesta»: fuera. El margen se multiplica; solo interesan simples con ventaja propia.
- Criterio: el modelo solo vale si, walk-forward, bate al mercado o gana dinero con cuota de Bet365 (casa blanda, lo más parecido a bwin) con n suficiente (ROI > 0 y > 2 errores estándar). Si no, se descarta sin pena.
- Si córners/tarjetas salen bien calibrados, la fase 2 los compara con cuotas de bwin capturadas (como la F1).

## Resultados fase 1 (28-sep-2026, 19.978 partidos)
- Goles más/menos 2,5: el mercado predice mejor que el modelo (log-loss 0,671 vs 0,702). ROI −6 % con Bet365, −1,8 % con la mejor cuota. Descartado como modelo.
- Córners: el modelo por equipo no mejora a la media de la liga; lo que varía es la liga y la temporada (Serie A >9,5: 49 % histórico, 40 % la última).
- Tarjetas: el modelo sí mejora a la media y está bien calibrado; ligas españolas las más tarjeteras. Falta el árbitro (solo Premier en football-data).

## Fase 2 (29-sep-2026, decidido por Elito)
- Capturar las 7 ligas (no solo España): una petición por captura trae todas.
- Capturas agrupadas por franja de inicio, no por partido: ~20 peticiones a bwin por semana.
- Guardar solo partidos de la ventana y mercados simples (sin combinadas) para no inflar el repo.
- Liquidar todo lo resoluble con football-data; informe semanal. Sin propuestas hasta que el informe muestre algo (n ≥ 30 por fila y ROI de cierre > 0).
- Tarjetas = amarillas + rojas; pendiente confirmar cómo cuenta bwin la doble amarilla.
