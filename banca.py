#!/usr/bin/env python3
"""Banca viva COMÚN para jarl-f1 y jarl-futbol (Elito tiene una sola cuenta en bwin).

Fichero común fuera de los repos: /opt/data/banca_comun.json (ruta cambiable con BANCA_COMUN).
  {"inicial": 200, "real": null | {"valor": €, "fecha": "AAAA-MM-DD"},
   "papeles": ["/opt/data/f1/papel/apuestas.csv", "/opt/data/futbol/papel/apuestas.csv"]}
Si no existe (p. ej. en pruebas), usa banca.json y papel/apuestas.csv del repo actual.

- Teórica: inicial + TODAS las propuestas liquidadas de F1 y fútbol, día a día y capitalizando
  (cada importe sobre la banca teórica de ese día): lo que habría pasado siguiendo todo.
- Real: la que declara Elito (recalibración). Si existe, es la base de los importes; si no, la teórica.

Uso:  python3 banca.py | --real 185.40 | --sin-real | --inicial 200
Cada cambio se registra también en banca_historial.log junto al fichero común.
"""
import argparse, csv, json, os
from collections import defaultdict
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
COMUN = os.environ.get("BANCA_COMUN", "/opt/data/banca_comun.json")
LOCAL = os.path.join(BASE, "banca.json")
PAPELES_DEF = ["/opt/data/f1/papel/apuestas.csv", "/opt/data/futbol/papel/apuestas.csv"]


def ruta():
    return COMUN if os.path.exists(COMUN) or os.path.isdir(os.path.dirname(COMUN)) and os.path.isdir("/opt/data/f1") else LOCAL


def leer():
    r = ruta()
    d = json.load(open(r)) if os.path.exists(r) else {}
    d.setdefault("inicial", 200.0); d.setdefault("real", None)
    if r == COMUN:
        d.setdefault("papeles", PAPELES_DEF)
    else:
        d["papeles"] = [os.path.join(BASE, "papel", "apuestas.csv")]
    return d


def guardar(d, motivo):
    r = ruta()
    json.dump(d if r == COMUN else {k: v for k, v in d.items() if k != "papeles"}, open(r, "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(os.path.dirname(r), "banca_historial.log"), "a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {motivo}\n")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def teorica(d=None):
    """(banca_teorica, n_apuestas, pendientes) sumando todos los papeles."""
    d = d or leer()
    por_dia, pend = defaultdict(list), 0
    for pp in d["papeles"]:
        if not os.path.exists(pp):
            continue
        for p in csv.DictReader(open(pp, encoding="utf-8")):
            fr = _f(p.get("fraccion"))
            if fr is None:
                eur = _f(p.get("importe_eur")); fr = eur / d["inicial"] if eur else None
            if fr is None:
                continue
            if p.get("resultado") not in ("0", "1", "V"):
                pend += 1; continue
            por_dia[p["fecha"]].append((fr, p["resultado"], float(p["cuota_tomada"])))
    banca, n = d["inicial"], 0
    for dia in sorted(por_dia):
        base = banca
        for fr, res, c in por_dia[dia]:
            st = base * fr
            banca += st * (c - 1) if res == "1" else -st if res == "0" else 0
            n += 1
    return round(banca, 2), n, pend


def para_importes():
    d = leer()
    t, _, _ = teorica(d)
    if d.get("real"):
        return float(d["real"]["valor"]), f"real {d['real']['valor']:.2f} € ({d['real']['fecha']}; teórica {t:.2f} €)"
    return t, f"teórica {t:.2f} € (sin real declarada)"


def bases():
    """(real o None, teórica): la real da el importe a poner en bwin; la teórica, el de la simulación."""
    d = leer()
    return (float(d["real"]["valor"]) if d.get("real") else None), teorica(d)[0]


def secuencial(fracs):
    """Cada apuesta sobre lo que queda de banca tras las anteriores: f_i · (1 − suma de las ya puestas)."""
    out, resto = [], 1.0
    for f in fracs:
        out.append(f * resto); resto -= f * resto
    return out


def resumen():
    d = leer(); t, n, pend = teorica(d)
    lin = [f"💰 Banca común F1+fútbol — teórica (siguiendo todo): {t:.2f} € (inicial {d['inicial']:.0f} €, {n} apuestas liquidadas, {pend} pendientes)"]
    lin.append(f"   Real declarada: {d['real']['valor']:.2f} € ({d['real']['fecha']}) → base de los importes" if d.get("real")
               else "   Sin banca real declarada → los importes usan la teórica")
    return lin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=float); ap.add_argument("--sin-real", action="store_true"); ap.add_argument("--inicial", type=float)
    a = ap.parse_args()
    d = leer()
    if a.real is not None:
        d["real"] = {"valor": round(a.real, 2), "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d")}; guardar(d, f"real = {a.real:.2f}")
    if a.sin_real:
        d["real"] = None; guardar(d, "real eliminada (usa teórica)")
    if a.inicial is not None:
        d["inicial"] = a.inicial; guardar(d, f"inicial = {a.inicial:.2f}")
    print(f"(fichero: {ruta()})")
    print("\n".join(resumen()))
    print(f"   Importes calculados sobre: {para_importes()[1]}")


if __name__ == "__main__":
    main()
