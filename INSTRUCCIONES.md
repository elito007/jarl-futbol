# Jarl — jarl-futbol

> Qué y por qué: `PLAN.md`. Claude programa; Jarl despliega y ejecuta. Despliegue con `git merge --no-edit`, nunca `--ff-only`, rebase ni force-push. Tras cada tarea: commit, entrada en `log-jarl.md` y `conversacion/AAAA-MM-DD.md`, push. Nunca leer ni imprimir `.env` ni tokens. Jarl nunca apuesta.

---

## TAREA ACTUAL (28-sep) — Tarea A: instalación, descarga y backtests

1. Clona el repo en `/opt/data/futbol` (aparte de `/opt/data/f1` y `/opt/data/scripts`).
2. `python3 descargar_futbol.py` (≈ 1 min). Pega en `conversacion/` la línea final y los fallos si los hay.
3. `python3 backtest_goles.py` y `python3 backtest_corners_tarjetas.py`. Pega ambas salidas completas en `conversacion/`.
4. Commit de `datos/historico/partidos.csv` y `analisis/`, entrada en `log-jarl.md`, push.
5. Nada de cron todavía.
