#!/usr/bin/env python3
"""Córners y tarjetas: frecuencias por liga y línea + calibración de un modelo por equipo.

No hay cuotas históricas de córners/tarjetas: el objetivo es tener probabilidades fiables que
comparar después con las cuotas de bwin que capturemos (como en la F1).
Modelo (walk-forward): media exponencial de lo que cada equipo genera y concede como local/visitante;
esperado del partido = (genera_local + concede_visitante)/2 + (genera_visitante + concede_local)/2.
Probabilidad con binomial negativa (los córners y tarjetas varían más que una Poisson).

Uso: python3 backtest_corners_tarjetas.py [--eval-desde 2020]
"""
import argparse, csv, math, os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
PARTIDOS = os.path.join(BASE, "datos", "historico", "partidos.csv")
LINEAS = {"corners": (7.5, 8.5, 9.5, 10.5, 11.5), "tarjetas": (2.5, 3.5, 4.5, 5.5, 6.5)}


def nb_cdf(k, mu, r):
    """P(X ≤ k) binomial negativa con media mu y parámetro de forma r (r→∞ = Poisson)."""
    p = r / (r + mu); s = 0.0
    for i in range(int(k) + 1):
        s += math.exp(math.lgamma(i + r) - math.lgamma(r) - math.lgamma(i + 1) + r * math.log(p) + i * math.log(1 - p))
    return s


def valor(f, que):
    try:
        if que == "corners":
            return int(f["corners_l"]) + int(f["corners_v"])
        return int(f["amarillas_l"]) + int(f["amarillas_v"]) + int(f["rojas_l"] or 0) + int(f["rojas_v"] or 0)
    except (TypeError, ValueError):
        return None


def lados(f, que):
    try:
        if que == "corners":
            return int(f["corners_l"]), int(f["corners_v"])
        return int(f["amarillas_l"]) + int(f["rojas_l"] or 0), int(f["amarillas_v"]) + int(f["rojas_v"] or 0)
    except (TypeError, ValueError):
        return None


def estimar_r(xs):
    """Forma de la binomial negativa por momentos: r = mu² / (var − mu)."""
    mu = sum(xs) / len(xs); var = sum((x - mu) ** 2 for x in xs) / len(xs)
    return mu * mu / (var - mu) if var > mu else 1e6


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--eval-desde", type=int, default=2020); a = ap.parse_args()
    filas = [f for f in csv.DictReader(open(PARTIDOS, encoding="utf-8")) if f["fecha"]]
    lin = []
    for que, lineas in LINEAS.items():
        lin += [f"==== {que.upper()} ====", "Frecuencia de 'más de' por liga (última temporada completa y todas):"]
        por_liga = defaultdict(list)
        for f in filas:
            if valor(f, que) is not None:
                por_liga[f["liga"]].append(f)
        for liga, fs in sorted(por_liga.items()):
            temps = sorted({f["temporada"] for f in fs}); ult = temps[-2] if len(temps) > 1 else temps[-1]
            xs = [valor(f, que) for f in fs]; xu = [valor(f, que) for f in fs if f["temporada"] == ult]
            celdas = "  ".join(f">{l}: {sum(x > l for x in xu)/len(xu)*100:4.0f}%/{sum(x > l for x in xs)/len(xs)*100:4.0f}%" for l in lineas)
            lin.append(f"  {liga:4s} media {sum(xs)/len(xs):4.1f} (r={estimar_r(xs):.0f}) | {celdas}")
        # modelo walk-forward y calibración
        cal = defaultdict(list)
        for liga, fs in por_liga.items():
            gen = defaultdict(lambda: None); con = defaultdict(lambda: None); n = defaultdict(int)
            hist = []
            for f in sorted(fs, key=lambda x: x["fecha"]):
                l, v = f["local"], f["visitante"]; xl, xv = lados(f, que)
                if int("20" + f["temporada"][:2]) >= a.eval_desde and n[l] >= 8 and n[v] >= 8 and len(hist) > 200:
                    mu = (gen[(l, "L")] + con[(v, "V")]) / 2 + (gen[(v, "V")] + con[(l, "L")]) / 2
                    r = estimar_r(hist[-760:])
                    for lnea in lineas:
                        cal[lnea].append((1 - nb_cdf(math.floor(lnea), mu, r), int(xl + xv > lnea)))
                for key, val in (((l, "L"), xl), ((v, "V"), xv)):
                    gen[key] = val if gen[key] is None else gen[key] + 0.08 * (val - gen[key])
                for key, val in (((v, "V"), xl), ((l, "L"), xv)):
                    con[key] = val if con[key] is None else con[key] + 0.08 * (val - con[key])
                n[l] += 1; n[v] += 1; hist.append(xl + xv)
        lin.append("Calibración del modelo (prob. predicha → frecuencia real), todas las ligas:")
        for lnea in lineas:
            cub = defaultdict(list)
            for p, y in cal[lnea]:
                cub[min(int(p * 5), 4)].append((p, y))
            celdas = "  ".join(f"{b*20}-{b*20+20}%: {sum(p for p, _ in s)/len(s)*100:.0f}→{sum(y for _, y in s)/len(s)*100:.0f} (n={len(s)})" for b, s in sorted(cub.items()))
            bs = sum((p - y) ** 2 for p, y in cal[lnea]) / max(len(cal[lnea]), 1)
            base = sum(y for _, y in cal[lnea]) / max(len(cal[lnea]), 1)
            lin.append(f"  >{lnea}: Brier {bs:.3f} (constante {base*(1-base):.3f}) | {celdas}")
        lin.append("")
    txt = "\n".join(lin); print(txt)
    open(os.path.join(BASE, "analisis", "backtest_corners_tarjetas.txt"), "w", encoding="utf-8").write(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
