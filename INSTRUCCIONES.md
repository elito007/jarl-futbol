# Jarl — jarl-futbol

> Qué y por qué: `PLAN.md`. Claude programa; Jarl despliega y ejecuta. Despliegue con `git merge --no-edit`, nunca `--ff-only`, rebase ni force-push. Tras cada tarea: commit, entrada en `log-jarl.md` y `conversacion/AAAA-MM-DD.md`, push. Nunca leer ni imprimir `.env` ni tokens. Jarl nunca apuesta.

---

## TAREA ACTUAL (30-sep) — Tarea C: otras casas (Betfair Exchange ES + OddsPapi), SOLO LECTURA

Qué cambia: tras cada captura de bwin se guardan también las cuotas del Exchange español de Betfair (API oficial) y, tras las propuestas, las de otras casas .es vía OddsPapi (solo partidos propuestos; 250 peticiones/mes). Nada apuesta. Sin credenciales, los scripts salen con código 3 y el cron los ignora sin avisar.
Credenciales: `/opt/data/futbol/.env.casas` (fuera de git, chmod 600) **lo crea Elito a mano**. Tú NO lo abras, NO lo imprimas y NO hagas `cat`/`grep` sobre él; como mucho `ls -l` para ver que existe y tiene permisos 600.

1. `git pull` en `/opt/data/futbol`. `python3 test_captura_auto.py` → todo ✓.
2. Espera a que Elito confirme que ha creado `.env.casas`. Comprueba `ls -l /opt/data/futbol/.env.casas` (debe ser `-rw-------`).
3. Diagnóstico Betfair (1 login + 3-4 peticiones): `.venv/bin/python betfair_futbol.py --diagnostico` → pega la salida completa en `conversacion/`. Interesa: si reconoce las 7 ligas, los nombres de mercado (córners, tarjetas/bookings) y unas cuotas de ejemplo. Si el login falla, pega el error tal cual (ya sale sin secretos).
4. Diagnóstico OddsPapi (≈5 peticiones del presupuesto): `.venv/bin/python oddspapi_futbol.py --diagnostico` → pega la salida completa.
5. No cambies el cron: `captura_auto.sh` ya hace `git pull`. Añade `datos/cuotas_betfair/ datos/cuotas_oddspapi/ datos/oddspapi_presupuesto.json` a lo que se sube: ya van dentro de `datos/`.
6. Anota en `log-jarl.md` y `conversacion/`, y push. Con esas salidas Claude escribe el comparador (bwin vs Betfair neta vs otras casas).

(Tarea B: hecha.)

## Tarea B (29-sep, hecha): capturas de bwin y cron horario

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
