#!/usr/bin/env python3
"""Planificador horario (cron sin LLM) de jarl-futbol.

- 'manana': una captura al día entre las 08:00 y las 12:00 (hora Canarias) con los partidos de las
  próximas 30 h. De ahí salen las horas de inicio que se usan para el resto del día.
- 'pre_partido': una captura por franja de inicio (partidos que empiezan con ≤ 45 min de diferencia
  forman una franja), entre 100 y 30 min antes. Solo guarda los partidos de las próximas 3 h.
- Liquidación diaria (≥ 10:00): actualiza football-data y liquida. Silenciosa.
- Lunes: informe semanal corto (stdout → Telegram).
bwin solo se consulta en esas capturas (unas 4-6 un sábado, 1-2 entre semana), con retraso aleatorio.
Estado en datos/estado_futbol.json.
"""
import argparse, json, os, random, subprocess, sys, time
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
ESTADO = os.path.join(BASE, "datos", "estado_futbol.json")
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Atlantic/Canary")
except Exception:
    TZ = timezone.utc


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def ejecutar(args):
    r = subprocess.run([sys.executable] + args, cwd=BASE, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip().splitlines() or [""]


def franjas(inicios, hueco=timedelta(minutes=45)):
    """Agrupa horas de inicio: devuelve la primera hora de cada franja."""
    out, ult = [], None
    for t in sorted(ts(x) for x in inicios):
        if ult is None or t - ult > hueco:
            out.append(t)
        ult = t
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simular-ahora"); ap.add_argument("--no-ejecutar", action="store_true")
    a = ap.parse_args()
    ahora = ts(a.simular_ahora) if a.simular_ahora else datetime.now(timezone.utc)
    local = ahora.astimezone(TZ)
    est = json.load(open(ESTADO)) if os.path.exists(ESTADO) else {}
    est.setdefault("inicios", []); est.setdefault("hechas", [])
    hechos, fallos, telegram = [], [], []

    def capturar(momento, horas):
        if a.no_ejecutar:
            hechos.append(f"tocaría {momento}"); return True
        if not a.simular_ahora:
            time.sleep(random.randint(0, 10 * 60))
        rc, out = ejecutar(["bwin_futbol.py", "--momento", momento, "--horas", str(horas)])
        if rc != 0:
            fallos.append(f"{momento} FALLO {out[-1]}"); return False
        ini = next((l[len("INICIOS: "):] for l in out if l.startswith("INICIOS: ")), "")
        if momento == "manana":
            est["inicios"] = [x for x in ini.split(",") if x]
            ruta = next((l.split("Guardado ", 1)[1].split(" (")[0] for l in out if l.startswith("Guardado ")), None)
            if ruta:  # propuestas del día (solo papel)
                rc4, o4 = ejecutar(["propuestas_futbol.py", "--captura", ruta])
                if rc4 == 0:
                    telegram.append("\n".join(o4))
                else:
                    fallos.append(f"propuestas FALLO {o4[-1]}")
        hechos.append(f"{momento} OK"); return True

    # 1) captura de la mañana
    hoy = local.strftime("%Y-%m-%d")
    if est.get("manana") != hoy and 8 <= local.hour < 12:
        if capturar("manana", 30):
            est["manana"] = hoy

    # 2) captura por franja
    for f in franjas([x for x in est["inicios"] if ts(x) > ahora]):
        clave = iso(f)
        if clave in est["hechas"]:
            continue
        if f - timedelta(minutes=100) <= ahora < f - timedelta(minutes=30):
            if capturar("pre_partido", 3):
                est["hechas"].append(clave)
            break  # como mucho una captura por ejecución
    est["hechas"] = [h for h in est["hechas"] if ts(h) > ahora - timedelta(days=3)]

    # 3) liquidación diaria (silenciosa) e informe semanal (lunes)
    if est.get("liquidado") != hoy and local.hour >= 10:
        if a.no_ejecutar:
            hechos.append("tocaría liquidar")
        else:
            rc1, o1 = ejecutar(["descargar_futbol.py", "--desde", str(ahora.year - (0 if ahora.month >= 7 else 1))])
            rc2, o2 = ejecutar(["liquidar_futbol.py"])
            if rc1 or rc2:
                fallos.append(f"liquidación FALLO {o1[-1]} | {o2[-1]}")
            else:
                est["liquidado"] = hoy; hechos.append("liquidación OK")
                semana = local.strftime("%G-W%V")
                if local.weekday() == 0 and est.get("informe") != semana:
                    rc3, o3 = ejecutar(["informe_mercados.py", "--min-n", "30"])
                    est["informe"] = semana
                    cab = [l for l in o3 if l.startswith("GP liquidados")]
                    filas = [l for l in o3 if len(l.split()) >= 8 and l.split()[2].isdigit()]
                    pos = [l for l in filas if l.split()[5].endswith("%") and float(l.split()[5][:-1]) > 0]
                    import liquidar_futbol as lqf
                    telegram.append("⚽ Informe semanal jarl-futbol: " + (cab[0].replace("GP liquidados", "días liquidados") if cab else "") +
                                    f"\nTipos de mercado con n≥30: {len(filas)}; con ROI de cierre > 0: {len(pos)}" +
                                    ("".join("\n  " + " ".join(l.split()[:6]) for l in pos[:5]) if pos else "") +
                                    "\n" + "\n".join(lqf.resumen_papel()))

    if not a.no_ejecutar:
        os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
        json.dump(est, open(ESTADO, "w"), indent=1)
        with open(os.path.join(BASE, "captura_auto.log"), "a") as fh:
            fh.write(f"{iso(ahora)} {' | '.join(hechos + fallos) or 'nada'}\n")
    salida = telegram + ([" | ".join(fallos)] if fallos else []) + (hechos if a.no_ejecutar else [])
    if salida:
        print("\n".join(salida))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
