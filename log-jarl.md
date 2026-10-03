# Log de Jarl — jarl-futbol


## 28-sep-2026 — Tarea A: instalación, descarga y backtests

- Repo clonado en /opt/data/futbol (aparte de f1 y scripts). `descargar_futbol.py` → `partidos.csv: 19978 partidos, 56 liga-temporadas` (exit 0, sin fallos).
- `backtest_goles.py` exit 0: modelo log-loss 0.7020 vs mercado 0.6711 (el mercado gana); ROI negativo en todos los umbrales/fuentes (solo `max` ≈ -1.8%). Por liga, todo negativo (mejor E0 -2.5% y SP1 -3.5%).
- `backtest_corners_tarjetas.py` exit 0: frecuencias por liga y calibración del modelo; bien calibrado en el rango central (60-80%), peor en extremos. Salidas completas pegadas en conversacion/2026-09-28.md.
- Commit de datos/historico/ y analisis/, entrada en log, push. Sin cron todavía (la tarea no lo pide).

## 3-oct-2026 — Tarea G: arreglo de nombres de equipos (URGENTE) + propuestas de hoy

- Fix: desde el 2-oct bwin metía jugadores en participants; los equipos salen ahora de un mercado «local / X / visitante» (reparar_nombres.py; capturas 2-3 oct corregidas en repo).
- `git pull` futbol+F1. `test_captura_auto.py` ✓ exit 0.
- Propuestas de hoy: `.venv/bin/python propuestas_futbol.py --captura .../2026-10-03_0743_manana.csv.gz` → **2** (Sabadell-Andorra): Ambos equipos 4+ córners @2.95 y Total córners «Más de 10,5» @3.5. Antes 0 por el fallo.
- `oddspapi_futbol.py --propuestas` → 1/1 guardados (3 usos mes). `comparar_casas.py` → 🔎 comparativa (bwin 3.5 vs bet365 3.5) + enlace. Enviado a Elito por Telegram.
- Commit papel/+datos/ (apuestas.csv, comparativas/2026-10-03.csv, cuotas_oddspapi/) → `470a10e` + push.

## 28-sep-2026 — Tarea B: capturas de bwin y cron horario

- `git pull` → main `e94c802` (fase 2: bwin_base/bwin_futbol/captura_auto.sh+py/liquidar_futbol/informe_mercados/test_captura_auto). No toqué /opt/data/f1.
- `.venv` con `python3 -m venv` + `pip install curl_cffi` → curl_cffi 0.16.3 (Python 3.13.5). Igual que en F1. (La instalación pidió aprobación y el primer intento se bloqueó por timeout; se aprobó al reintentar.)
- `test_captura_auto.py` todo ✓ (franjas pre_partido, sábado=5 peticiones, sprint=una, OpenF1 caído=una diaria, informe semanal de ejemplo, lunes liquida+informe).
- `bwin_futbol.py --test` → 1 petición: `fixtures recibidos: 99 | en ventana 30 h: 1 partidos, 709 filas · INICIOS: 2026-09-28T18:30:00Z` (curl_cffi, sin 403).
- Cron horario **`ef75bd0912b4`** `37 * * * *` (min 37 para no coincidir con F1 en el 07). no_agent=true, deliver telegram (stdout no vacío → informe/fallos; vacío → nada; exit≠0 → alerta). Script `/opt/data/scripts/futbol-captura-auto.sh` (lanzador 1-línea → exec `/opt/data/futbol/captura_auto.sh`; igual que F1). Excluido del repo crypto vía `.git/info/exclude` → `git status` de scripts limpio. Primera ejecución 2026-09-28 17:37.
- `captura_auto.py --no-ejecutar` → "tocaría liquidar" (dry-run, sin escribir).
- Push a main con log + conversación.

## 30-sep-2026 — Tarea C: otras casas (Betfair Exchange ES + OddsPapi), solo lectura

- `git pull` → `3a909c2` (betfair_futbol.py, oddspapi_futbol.py, casas_base.py). No cambié el cron.
- `.env.casas`: `-rw------- 1 hermes hermes` (600, owner hermes) ✓ — NO abierto ni impreso. (Inicialmente llegó `root:root`; Elito lo pasó a hermes. Sin eso, casas_base.py daba PermissionError.)
- `test_captura_auto.py` todo ✓ exit 0 (incluye tests Betfair sin credenciales / con fallo → un solo aviso al día).
- **Betfair** `--diagnostico` exit 0: login OK, 96 competiciones, reconoce D1/E0/F1/I1/SP1/SP2 (SP2 ambigua: la española, portuguesa y venezolana). **E1 sin reconocer** (= división inglesa; candidatas English Sky Bet League 1/2). 0 partidos en 30 h.
- **OddsPapi** `--diagnostico` **exit 2**: responde (361 casas, 33.115 mercados fútbol, 570 córners/tarjetas, 136 fixtures hoy-mañana) pero **una llamada da HTTP 400 Bad Request**. Además `casas españolas: []`. Para que Claude lo revise.
- Salidas completas en `conversacion/2026-09-30.md`. Push.

## 30-sep-2026 — Tarea D: repetición de diagnósticos (fix de presupuesto OddsPapi)

- `git pull` → fix de presupuesto (betfair/oddspapi/casas_base). `test_captura_auto.py` ✓ exit 0.
- **Betfair** `--diagnostico` exit 0: **SP2 ahora = solo la española** (antes también pt/ve). E1 sin reconocer (candidatas Sky Bet League 1/2). 0 partidos en 30 h.
- **OddsPapi** `--diagnostico` **exit 2**: el fix funciona (361 casas + de interés, 5 partidos de nuestras ligas en 4 días), pero **cuota agotada** (presupuesto 8/8 mes 2026-09, los 8 hoy) al pedir las cuotas del 1er partido. **NO se generó `diagnostico_*.json.gz`** (el script lo guarda solo tras obtener cuotas, línea ~190; no llegó). No fabrico el fichero; repetir mañana.
- Commit: `datos/oddspapi_presupuesto.json` (m) + `datos/oddspapi_participantes.json` (nuevo). Salidas completas en `conversacion/2026-09-30.md`. Push.

## 30-sep-2026 — Tarea E: OddsPapi OK (guarda snapshot) + Betfair lista de las inglesas

- `git pull` → fix (oddspapi/betfair: 53+/16-). `test_captura_auto.py` ✓ exit 0.
- **OddsPapi** `--diagnostico` **exit 0** (presupuesto OK hoy): 361 casas con slugs de interés, 5 partidos de nuestras ligas en 4 días, 20.556 participantes, 260 casas con cuotas en Eldense–Real Oviedo (SP2 02-oct, bet365 162 mercados). **Generó `datos/cuotas_oddspapi/diagnostico_2026-09-30.json.gz` (1,8 MB)** ✓ subido. Peticiones mes: 12.
- **Betfair** `--diagnostico` exit 0: solo línea «NO reconocidas» → `['E1'] · inglesas en el exchange: [English Football League Cup, English Ladies League Cup, English National League, English Premier League, English Sky Bet League 1, English Sky Bet League 2, English WSL]`. E1 sin asignar; candidatas Sky Bet League 1/2.
- Salidas en `conversacion/2026-09-30.md`. Push (incluye el .json.gz nuevo).

## 1-oct-2026 — Tarea F: comparativa de cuotas (solo informativa)

- `git pull` → main (comparar_casas.py nuevo; oddspapi/captura_auto 22+). `test_captura_auto.py` ✓ exit 0.
- `git rm datos/cuotas_oddspapi/diagnostico_2026-09-30.json.gz` (Claude ya lo analizó) + push.
- No hay captura de la mañana con propuestas hoy (pendientes 0; CSVs del 28-sep) → bloque «🔎 Comparativa» aún no generado; `datos/comparativas/` no existe. PENDIENTE: pegarlo cuando salga en la próxima captura matinal.
- Qué hace: tras las propuestas, OddsPapi guarda 10 casas .es (~60 KB/partido) y comparar_casas.py envía la comparativa (mejor .es con ⭐ si supera bwin, Betfair neta, Pinnacle justa, enlace boleto bwin). No apuesta.
- Salidas en `conversacion/2026-09-30.md`. Push.