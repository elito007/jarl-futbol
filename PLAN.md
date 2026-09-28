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

## Propuestas en papel (29-sep-2026, pedido por Elito)
- Aunque aún no hay datos objetivos, se envían propuestas diarias para ir midiendo el acierto (SOLO PAPEL).
- Tras la captura de la mañana: `propuestas_futbol.py` → Telegram. Reglas fijas: solo córners y tarjetas (modelo); EV ≥ 10 %, prob ≥ 25 %, cuota ≤ 5; 1 por mercado, máx. 2 por partido y 12 al día; partidos de las próximas 24 h.
- Validación fuera de muestra (entrenado hasta 24/25, probado en 25/26): el modelo mejora a la constante en «más córners» (Brier 0,235 vs 0,247) y «ambos equipos 2+ tarjetas» (0,235 vs 0,244, aunque infraestima ~5 pp); en «más tarjetas», rangos de córners y «ambos 4+ córners» no mejora. Por eso confianza «media» solo en los dos primeros.
- Importe sugerido: banca 200 € (propia del fútbol), ¼ Kelly, tope 1 %/apuesta (más partidos que en F1) y 5 %/día; ×0,5 en confianza baja.
- Liquidación automática en `papel/apuestas.csv` y resumen del papel en el informe de los lunes.

## Banca viva (29-sep-2026, Elito)
- `banca.py`: banca teórica = inicial (200 €) + resultado de TODAS las propuestas liquidadas, capitalizando día a día con la fracción de banca de cada una (lo que habría pasado siguiendo el sistema al 100 %).
- Banca real: la declara Elito cuando quiera (recalibración): `python3 banca.py --real <€>` (vía Jarl). Si existe, los importes sugeridos se calculan sobre ella; si no, sobre la teórica. `--sin-real` vuelve a la teórica.
- Los resúmenes muestran ambas.
