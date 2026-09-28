#!/usr/bin/env python3
"""Informe acumulado de todas las liquidaciones: ¿dónde se equivoca bwin?

Por tipo de mercado y lado (Sí/No, Más/Menos, favorito/resto):
  n, prob. media según bwin (sin margen), frecuencia real, ROI de apostar 1 u a todas
  con la cuota de cierre y con la primera cuota capturada, y CLV medio.
Más una tabla de calibración global (¿los 20 % de bwin ocurren el 20 % de las veces?).
Estrategias fijas = filas de la tabla; se eligen ANTES de mirar resultados (ver PLAN.md).

Uso: python3 informe_mercados.py [--min-n 5]   → también escribe analisis/informe_mercados.txt
"""
import argparse, csv, glob, os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))


def lado(r, fav):
    s = r["seleccion"].strip().lower()
    if s in ("sí", "si", "no"):
        return "Sí" if s != "no" else "No"
    if s.startswith("más") or s.startswith("mas"):
        return "Más"
    if s.startswith("menos"):
        return "Menos"
    return "favorito" if fav else "resto"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--min-n", type=int, default=5); a = ap.parse_args()
    filas = []
    for f in sorted(glob.glob(os.path.join(BASE, "datos", "liquidaciones", "*.csv"))):
        gp = os.path.basename(f)[:-4]
        filas += [{**r, "gp": gp} for r in csv.DictReader(open(f, encoding="utf-8")) if r["resultado"] in ("0", "1")]
    if not filas:
        print("Sin liquidaciones todavía."); return 0
    # favorito por mercado y captura
    minc = defaultdict(lambda: 1e9)
    for r in filas:
        k = (r["gp"], r["ts_utc"], r["mercado_id"]); minc[k] = min(minc[k], float(r["cuota"]))
    # apertura y cierre por selección
    sel = defaultdict(list)
    for r in filas:
        sel[(r["gp"], r["mercado_id"], r["seleccion_id"])].append(r)
    grupos = defaultdict(list); calib = defaultdict(list)
    for k, rs in sel.items():
        rs.sort(key=lambda r: r["ts_utc"])
        ap_, ci = rs[0], rs[-1]
        fav = float(ci["cuota"]) == minc[(ci["gp"], ci["ts_utc"], ci["mercado_id"])]
        y = int(ci["resultado"]); p = float(ci["prob_justa"]) if ci["prob_justa"] else None
        g = (ci["tipo"], lado(ci, fav))
        grupos[g].append((y, p, float(ci["cuota"]), float(ap_["cuota"])))
        if p is not None:
            calib[min(int(p * 10), 9)].append((y, p))
    gps = len({r["gp"] for r in filas})
    lin = [f"GP liquidados: {gps} | selecciones: {len(sel)}", "",
           f"{'tipo':24s} {'lado':9s} {'n':>4s} {'bwin%':>6s} {'real%':>6s} {'ROIcierre':>9s} {'ROIapert':>8s} {'CLV':>6s}"]
    for (t, l), v in sorted(grupos.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(v) < a.min_n:
            continue
        n = len(v); real = sum(y for y, *_ in v) / n
        pb = [p for _, p, *_ in v if p is not None]; pbm = sum(pb) / len(pb) if pb else float("nan")
        roi_c = sum((c - 1) if y else -1 for y, _, c, _ in v) / n
        roi_a = sum((o - 1) if y else -1 for y, _, _, o in v) / n
        clv = sum(o / c - 1 for _, _, c, o in v) / n
        lin.append(f"{t:24s} {l:9s} {n:4d} {pbm*100:6.1f} {real*100:6.1f} {roi_c*100:8.1f}% {roi_a*100:7.1f}% {clv*100:5.1f}%")
    lin += ["", "Calibración global (prob. bwin sin margen → frecuencia real):"]
    for b in sorted(calib):
        v = calib[b]; lin.append(f"  {b*10:3d}-{b*10+10:3d}%  n={len(v):4d}  bwin {sum(p for _, p in v)/len(v)*100:5.1f}%  real {sum(y for y, _ in v)/len(v)*100:5.1f}%")
    lin += ["", f"(filas con n < {a.min_n} ocultas; con pocos GP todo esto es ruido)"]
    txt = "\n".join(lin); print(txt)
    os.makedirs(os.path.join(BASE, "analisis"), exist_ok=True)
    open(os.path.join(BASE, "analisis", "informe_mercados.txt"), "w", encoding="utf-8").write(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
