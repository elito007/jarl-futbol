#!/usr/bin/env python3
"""Pruebas sin red del planificador de fútbol."""
import os, tempfile
from datetime import datetime, timedelta, timezone
import captura_auto as ca

ok = True
def chk(n, c):
    global ok; print(("✓" if c else "✗"), n); ok &= bool(c)

llam = []
INICIOS = ["2026-10-10T12:00:00Z", "2026-10-10T14:15:00Z", "2026-10-10T14:30:00Z", "2026-10-10T16:30:00Z", "2026-10-10T19:00:00Z"]
def ej(args):
    llam.append(args)
    if args[0] == "bwin_futbol.py":
        return 0, ["fixtures", "INICIOS: " + ",".join(INICIOS), "Guardado datos/cuotas/x.csv.gz (10 filas, 1 partidos)"]
    if args[0] == "propuestas_futbol.py":
        return 0, ["⚽ Propuestas de hoy"]
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
chk("09:07 local → captura mañana + propuestas", correr("2026-10-10T08:07:00Z") == ["manana", "propuestas_futbol.py"])
chk("10:07 local → liquida (descarga+liquidar)", correr("2026-10-10T09:07:00Z") == ["descargar_futbol.py", "liquidar_futbol.py"])
chk("11:07 local (12:00 UTC −53 min) → pre_partido franja 12:00", correr("2026-10-10T11:07:00Z") == ["pre_partido"])
chk("12:07 → nada", correr("2026-10-10T12:07:00Z") == [])
chk("13:07 UTC → pre_partido franja 14:15/14:30 (una sola)", correr("2026-10-10T13:07:00Z") == ["pre_partido"])
chk("14:07 → nada (ya hecha)", correr("2026-10-10T14:07:00Z") == [])
chk("15:07 → pre_partido 16:30", correr("2026-10-10T15:07:00Z") == ["pre_partido"])
chk("17:47 → pre_partido 19:00", correr("2026-10-10T17:47:00Z") == ["pre_partido"])
chk("sábado entero: 5 peticiones a bwin", sum(1 for x in llam if x[0] == "bwin_futbol.py") == 5)
chk("lunes 10:07 → liquida + informe", correr("2026-10-12T09:07:00Z")[-3:] == ["descargar_futbol.py", "liquidar_futbol.py", "informe_mercados.py"])
raise SystemExit(0 if ok else 1)
