#!/usr/bin/env python3
"""Banca viva: teórica (siguiendo el sistema al 100 %) y real (la que declara Elito).

- Teórica: parte de la banca inicial y reproduce, día a día, todas las propuestas liquidadas con su
  fracción de banca (columna 'fraccion' de papel/apuestas.csv), capitalizando: el importe de cada día
  se calcula sobre la banca teórica de ese día. Es «lo que habría pasado si hubieras seguido todo».
- Real: último valor declarado por Elito (recalibración). Si existe, los importes sugeridos se
  calculan sobre ella; si no, sobre la teórica.

Uso:  python3 banca.py                 → muestra teórica, real e importe base
      python3 banca.py --real 185.40    → declara la banca real (hoy)
      python3 banca.py --sin-real       → vuelve a usar la teórica para los importes
Datos en banca.json (versionado).
"""
import argparse, csv, json, os
from collections import defaultdict
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(BASE, "banca.json")
PAPEL = os.path.join(BASE, "papel", "apuestas.csv")
INICIAL_DEF = 200.0


def leer():
    d = json.load(open(RUTA)) if os.path.exists(RUTA) else {}
    d.setdefault("inicial", INICIAL_DEF); d.setdefault("real", None)
    return d


def guardar(d):
    json.dump(d, open(RUTA, "w"), indent=1, ensure_ascii=False)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def teorica(d=None):
    """(banca_teorica, n_apuestas_contadas, pendientes)."""
    d = d or leer()
    if not os.path.exists(PAPEL):
        return d["inicial"], 0, 0
    por_dia = defaultdict(list)
    pend = 0
    for p in csv.DictReader(open(PAPEL, encoding="utf-8")):
        fr = _f(p.get("fraccion"))
        if fr is None:
            eur = _f(p.get("importe_eur"))
            fr = eur / d["inicial"] if eur else None   # propuestas antiguas sin fracción
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
    """(banca sobre la que se calculan los importes, etiqueta)."""
    d = leer()
    if d.get("real"):
        return float(d["real"]["valor"]), f"real declarada {d['real']['valor']:.2f} € ({d['real']['fecha']})"
    t, _, _ = teorica(d)
    return t, f"teórica {t:.2f} €"


def resumen():
    d = leer(); t, n, pend = teorica(d)
    lin = [f"💰 Banca teórica (siguiendo todo): {t:.2f} € (inicial {d['inicial']:.0f} €, {n} apuestas, {pend} pendientes)"]
    if d.get("real"):
        lin.append(f"   Banca real declarada: {d['real']['valor']:.2f} € ({d['real']['fecha']}) → base de los importes")
    return lin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=float); ap.add_argument("--sin-real", action="store_true")
    a = ap.parse_args()
    d = leer()
    if a.real is not None:
        d["real"] = {"valor": round(a.real, 2), "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d")}; guardar(d)
    elif a.sin_real:
        d["real"] = None; guardar(d)
    print("\n".join(resumen()))
    b, et = para_importes(); print(f"   Importes calculados sobre: {et}")


if __name__ == "__main__":
    main()
