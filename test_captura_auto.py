#!/usr/bin/env python3
"""Pruebas sin red del planificador de fútbol."""
import os, tempfile
from datetime import datetime, timedelta, timezone
import captura_auto as ca

ok = True
def chk(n, c):
    global ok; print(("✓" if c else "✗"), n); ok &= bool(c)

llam = []
AVISO = False
INICIOS = ["2026-10-10T12:00:00Z", "2026-10-10T14:15:00Z", "2026-10-10T14:30:00Z", "2026-10-10T16:30:00Z", "2026-10-10T19:00:00Z"]
def ej(args):
    llam.append(args)
    if args[0] == "bwin_futbol.py":
        return 0, ["fixtures", "INICIOS: " + ",".join(INICIOS), "Guardado datos/cuotas/x.csv.gz (10 filas, 1 partidos)"]
    if args[0] == "propuestas_futbol.py":
        return 0, ["⚽ Propuestas de hoy"]
    if args[0] == "liquidar_futbol.py" and AVISO:
        return 0, ["papel: 1 apuestas liquidadas", "AVISO_LIQ: ✅ A - B · Total de córners «Más de 9,5» @ 2.0 → +1.00 € (de 1.0 €)"]
    if args[0] == "informe_mercados.py":
        return 0, ["GP liquidados: 3 | selecciones: 900", "goles No 40 50.0 55.0 4.0% 3.0% 1.0%"]
    return 0, ["ok"]
ca.ejecutar = ej
ca.ESTADO = os.path.join(tempfile.mkdtemp(), "e.json"); ca.BASE = os.path.dirname(ca.ESTADO)

def correr(iso_utc):
    antes = len(llam)
    ca.main.__globals__["sys"].argv = ["x", "--simular-ahora", iso_utc]
    ca.main()
    return [x[0] if x[0] != "bwin_futbol.py" else x[2] for x in llam[antes:]]

# Canarias = UTC+1 en octubre
chk("06:00 local → nada", correr("2026-10-10T05:00:00Z") == [])
chk("09:07 local → captura mañana + propuestas", correr("2026-10-10T08:07:00Z") == ["manana", "betfair_futbol.py", "propuestas_futbol.py", "oddspapi_futbol.py"])
chk("10:07 local → liquida (descarga+liquidar)", correr("2026-10-10T09:07:00Z") == ["descargar_futbol.py", "liquidar_futbol.py"])
chk("11:07 local (12:00 UTC −53 min) → pre_partido franja 12:00", correr("2026-10-10T11:07:00Z") == ["pre_partido", "betfair_futbol.py"])
chk("12:07 → nada", correr("2026-10-10T12:07:00Z") == [])
chk("13:07 UTC → pre_partido franja 14:15/14:30 (una sola)", correr("2026-10-10T13:07:00Z") == ["pre_partido", "betfair_futbol.py"])
chk("14:07 → nada (ya hecha)", correr("2026-10-10T14:07:00Z") == [])
chk("15:07 → pre_partido 16:30", correr("2026-10-10T15:07:00Z") == ["pre_partido", "betfair_futbol.py"])
chk("17:47 → pre_partido 19:00", correr("2026-10-10T17:47:00Z") == ["pre_partido", "betfair_futbol.py"])
chk("sábado entero: 5 peticiones a bwin", sum(1 for x in llam if x[0] == "bwin_futbol.py") == 5)
chk("lunes 10:07 → liquida + informe", correr("2026-10-12T09:07:00Z")[-3:] == ["descargar_futbol.py", "liquidar_futbol.py", "informe_mercados.py"])
# reintentos si quedan propuestas vencidas sin resultado, y aviso al liquidar
os.makedirs(os.path.join(ca.BASE, "papel"), exist_ok=True)
with open(os.path.join(ca.BASE, "papel", "apuestas.csv"), "w") as fh:
    fh.write("fecha,partido,inicio_utc,mercado,seleccion,resultado\n2026-10-12,A - B,2026-10-12T18:00:00Z,x,y,\n")
chk("martes 10:07 → liquida (partido del lunes pendiente)", correr("2026-10-13T09:07:00Z")[-2:] == ["descargar_futbol.py", "liquidar_futbol.py"])
chk("martes 11:07 → no reintenta antes de 4 h", "liquidar_futbol.py" not in correr("2026-10-13T10:07:00Z"))
chk("martes 13:07 → reintenta (4 h)", "liquidar_futbol.py" in correr("2026-10-13T13:07:00Z"))
import io, contextlib
AVISO = True
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    correr("2026-10-13T17:07:00Z")
chk("aviso de resultados por Telegram", "⚽ Resultados — 1 propuesta(s)" in buf.getvalue() and "+1.00 €" in buf.getvalue())
# día sin partidos → una línea de «sistema OK»
INICIOS_BAK = list(INICIOS); INICIOS.clear(); SIN = True
ca.ejecutar = lambda args: (llam.append(args), (0, ["INICIOS: "]) if args[0] == "bwin_futbol.py" else (0, ["ok"]))[1]
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    correr("2026-10-14T08:07:00Z")
chk("día sin partidos → aviso de sistema OK", "Hoy no hay partidos" in buf.getvalue())
# otra casa sin credenciales (código 3) → silencio; con fallo → un aviso al día
def ej3(args):
    llam.append(args)
    if args[0] == "bwin_futbol.py":
        return 0, ["INICIOS: 2026-10-20T19:00:00Z,2026-10-20T21:30:00Z", "Guardado datos/cuotas/x.csv.gz (1 filas, 1 partidos)"]
    if args[0] == "betfair_futbol.py":
        return RC_BF, ["SIN CREDENCIALES" if RC_BF == 3 else "ERROR Betfair: login"]
    return 0, ["ok"]
ca.ejecutar = ej3; RC_BF = 3
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    correr("2026-10-20T08:07:00Z")
chk("Betfair sin credenciales → sin aviso", "Betfair" not in buf.getvalue())
RC_BF = 2; buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    n0 = len(llam); correr("2026-10-20T17:47:00Z"); correr("2026-10-20T20:07:00Z")
chk("Betfair con fallo → un solo aviso al día", buf.getvalue().count("Betfair FALLO") == 1 and sum(1 for x in llam[n0:] if x[0] == "betfair_futbol.py") == 2)
raise SystemExit(0 if ok else 1)
