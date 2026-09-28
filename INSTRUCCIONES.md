# Jarl — jarl-futbol

> Qué y por qué: `PLAN.md`. Claude programa; Jarl despliega y ejecuta. Despliegue con `git merge --no-edit`, nunca `--ff-only`, rebase ni force-push. Tras cada tarea: commit, entrada en `log-jarl.md` y `conversacion/AAAA-MM-DD.md`, push. Nunca leer ni imprimir `.env` ni tokens. Jarl nunca apuesta.

---

## TAREA ACTUAL (29-sep) — Tarea B: capturas de bwin y cron horario

1. En `/opt/data/futbol`: `git pull`. Crea `.venv` con `curl_cffi` (igual que en /opt/data/f1).
2. `python3 test_captura_auto.py` → todo ✓.
3. `.venv/bin/python bwin_futbol.py --test` → pega la salida (fixtures recibidos, partidos en ventana, INICIOS). Una sola petición.
4. Cron **horario en el minuto 37** (no el 07, para no coincidir con F1), `no_agent=true`, con un lanzador de una línea `/opt/data/scripts/futbol-captura-auto.sh` que ejecute `/opt/data/futbol/captura_auto.sh`. Exclúyelo con `.git/info/exclude` del repo crypto. Reenviar a Telegram cualquier salida no vacía (informe semanal y fallos). Confirma id y expresión.
5. `.venv/bin/python captura_auto.py --no-ejecutar` → pega la salida.
6. Anota en `log-jarl.md` y `conversacion/`, y push. No toques /opt/data/f1.

(Tarea A: hecha.)

## Tarea A (28-sep, hecha): instalación, descarga y backtests

1. Clona el repo en `/opt/data/futbol` (aparte de `/opt/data/f1` y `/opt/data/scripts`).
2. `python3 descargar_futbol.py` (≈ 1 min). Pega en `conversacion/` la línea final y los fallos si los hay.
3. `python3 backtest_goles.py` y `python3 backtest_corners_tarjetas.py`. Pega ambas salidas completas en `conversacion/`.
4. Commit de `datos/historico/partidos.csv` y `analisis/`, entrada en `log-jarl.md`, push.
5. Nada de cron todavía.
