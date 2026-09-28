# Log de Jarl — jarl-futbol


## 28-sep-2026 — Tarea A: instalación, descarga y backtests

- Repo clonado en /opt/data/futbol (aparte de f1 y scripts). `descargar_futbol.py` → `partidos.csv: 19978 partidos, 56 liga-temporadas` (exit 0, sin fallos).
- `backtest_goles.py` exit 0: modelo log-loss 0.7020 vs mercado 0.6711 (el mercado gana); ROI negativo en todos los umbrales/fuentes (solo `max` ≈ -1.8%). Por liga, todo negativo (mejor E0 -2.5% y SP1 -3.5%).
- `backtest_corners_tarjetas.py` exit 0: frecuencias por liga y calibración del modelo; bien calibrado en el rango central (60-80%), peor en extremos. Salidas completas pegadas en conversacion/2026-09-28.md.
- Commit de datos/historico/ y analisis/, entrada en log, push. Sin cron todavía (la tarea no lo pide).

## 28-sep-2026 — Tarea B: capturas de bwin y cron horario

- `git pull` → main `e94c802` (fase 2: bwin_base/bwin_futbol/captura_auto.sh+py/liquidar_futbol/informe_mercados/test_captura_auto). No toqué /opt/data/f1.
- `.venv` con `python3 -m venv` + `pip install curl_cffi` → curl_cffi 0.16.3 (Python 3.13.5). Igual que en F1. (La instalación pidió aprobación y el primer intento se bloqueó por timeout; se aprobó al reintentar.)
- `test_captura_auto.py` todo ✓ (franjas pre_partido, sábado=5 peticiones, sprint=una, OpenF1 caído=una diaria, informe semanal de ejemplo, lunes liquida+informe).
- `bwin_futbol.py --test` → 1 petición: `fixtures recibidos: 99 | en ventana 30 h: 1 partidos, 709 filas · INICIOS: 2026-09-28T18:30:00Z` (curl_cffi, sin 403).
- Cron horario **`ef75bd0912b4`** `37 * * * *` (min 37 para no coincidir con F1 en el 07). no_agent=true, deliver telegram (stdout no vacío → informe/fallos; vacío → nada; exit≠0 → alerta). Script `/opt/data/scripts/futbol-captura-auto.sh` (lanzador 1-línea → exec `/opt/data/futbol/captura_auto.sh`; igual que F1). Excluido del repo crypto vía `.git/info/exclude` → `git status` de scripts limpio. Primera ejecución 2026-09-28 17:37.
- `captura_auto.py --no-ejecutar` → "tocaría liquidar" (dry-run, sin escribir).
- Push a main con log + conversación.