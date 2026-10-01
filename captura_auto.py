#!/usr/bin/env python3
"""Planificador horario (cron sin LLM) de jarl-futbol.

- 'manana': una captura al día a partir de las 08:00 (hora Canarias; si falla o se pierde, se recupera hasta las 22:00) con los partidos de las
  próximas 30 h. De ahí salen las horas de inicio que se usan para el resto del día.
- 'pre_partido': una captura por franja de inicio (partidos que empiezan con ≤ 45 min de diferencia
  forman una franja), entre 100 y 30 min antes. Solo guarda los partidos de las próximas 3 h.
- Liquidación diaria (≥ 10:00): actualiza football-data y liquida. Si quedan propuestas de partidos ya jugados sin
  resultado, reintenta cada 4 h (hasta las 23:00). Cada vez que se liquidan propuestas, aviso corto por Telegram.
- Lunes: informe semanal corto (stdout → Telegram).
Tras cada captura de bwin: Betfair Exchange ES (API oficial) en el mismo momento; tras las propuestas,
OddsPapi (otras casas .es) solo para los partidos propuestos. Sin credenciales se omiten sin avisar.
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


def vencidas_pendientes(ahora):
    """¿Hay propuestas de papel sin resultado de partidos que empezaron hace más de 3 h?"""
    ruta = os.path.join(BASE, "papel", "apuestas.csv")
    if not os.path.exists(ruta):
        return False
    import csv
    for p in csv.DictReader(open(ruta, encoding="utf-8")):
        if not p.get("resultado") and p.get("inicio_utc") and ts(p["inicio_utc"]) < ahora - timedelta(hours=3):
            return True
    return False


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

    def otra_casa(args, nombre):
        """Betfair / OddsPapi: solo registran; sin credenciales (código 3) se ignoran; un fallo se avisa una vez al día."""
        rc, out = ejecutar(args)
        if rc == 0:
            hechos.append(f"{nombre} OK")
            return True
        elif rc != 3 and est.get(f"aviso_{nombre}") != local.strftime("%Y-%m-%d"):
            est[f"aviso_{nombre}"] = local.strftime("%Y-%m-%d")
            fallos.append(f"{nombre} FALLO {out[-1]}")

    def capturar(momento, horas):
        if a.no_ejecutar:
            hechos.append(f"tocaría {momento}"); return True
        if not a.simular_ahora:
            time.sleep(random.randint(0, 10 * 60))
        rc, out = ejecutar(["bwin_futbol.py", "--momento", momento, "--horas", str(horas)])
        if rc != 0:
            fallos.append(f"{momento} FALLO {out[-1]}"); return False
        ini = next((l[len("INICIOS: "):] for l in out if l.startswith("INICIOS: ")), "")
        otra_casa(["betfair_futbol.py", "--momento", momento, "--horas", str(horas)], "Betfair")
        if momento == "manana":
            est["inicios"] = [x for x in ini.split(",") if x]
            ruta = next((l.split("Guardado ", 1)[1].split(" (")[0] for l in out if l.startswith("Guardado ")), None)
            if ruta:  # propuestas del día (solo papel)
                rc4, o4 = ejecutar(["propuestas_futbol.py", "--captura", ruta])
                if rc4 == 0:
                    telegram.append("\n".join(o4))
                    if otra_casa(["oddspapi_futbol.py", "--propuestas"], "OddsPapi"):
                        rc5, o5 = ejecutar(["comparar_casas.py"])  # dónde paga más cada propuesta
                        if rc5 == 0 and any(l.strip() for l in o5):
                            telegram.append("\n".join(o5))
                else:
                    fallos.append(f"propuestas FALLO {o4[-1]}")
            else:  # sin partidos: una línea para saber que el sistema sigue vivo
                prox = sorted(x for x in est["inicios"] if ts(x) > ahora)
                cuando = (f" El próximo partido conocido es el {ts(prox[0]).astimezone(TZ):%d/%m a las %H:%M}"
                          " (entrará en la captura de mañana)." if prox else "")
                telegram.append("⚽ Hoy no hay partidos de las 7 ligas en las próximas 30 h." + cuando +
                                " Sistema OK; próxima revisión mañana a partir de las 08:00. (/estado para ver el detalle)")
        hechos.append(f"{momento} OK"); return True

    # 1) captura de la mañana
    hoy = local.strftime("%Y-%m-%d")
    if est.get("manana") != hoy and 8 <= local.hour < 22:  # si se perdió la de la mañana, se recupera en la siguiente hora
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
    ult = est.get("liq_intento")
    reintento = (vencidas_pendientes(ahora) and local.hour < 23 and (not ult or ahora - ts(ult) >= timedelta(hours=4)))
    if local.hour >= 10 and (est.get("liquidado") != hoy or reintento):
        est["liq_intento"] = iso(ahora)
        if a.no_ejecutar:
            hechos.append("tocaría liquidar")
        else:
            rc1, o1 = ejecutar(["descargar_futbol.py", "--desde", str(ahora.year - (0 if ahora.month >= 7 else 1))])
            rc2, o2 = ejecutar(["liquidar_futbol.py"])
            if rc1 or rc2:
                fallos.append(f"liquidación FALLO {o1[-1]} | {o2[-1]}")
            else:
                est["liquidado"] = hoy; hechos.append("liquidación OK")
                avisos = [l[len("AVISO_LIQ: "):] for l in o2 if l.startswith("AVISO_LIQ: ")]
                if avisos:
                    import banca as bk
                    tot = 0.0
                    for l in avisos:
                        try:
                            tot += float(l.rsplit("→ ", 1)[1].split(" €")[0])
                        except (IndexError, ValueError):
                            pass
                    telegram.append(f"⚽ Resultados — {len(avisos)} propuesta(s) liquidada(s) · 📝 SOLO PAPEL · balance {tot:+.2f} €\n"
                                    + "\n".join(avisos) + "\n" + "\n".join(bk.resumen()))
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
