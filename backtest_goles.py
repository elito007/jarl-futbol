#!/usr/bin/env python3
"""Backtest de goles (más/menos 2,5) contra cuotas de cierre reales (football-data).

Modelo: Poisson con fuerza de ataque/defensa por equipo (media exponencial, se actualiza tras
cada partido, walk-forward: solo usa partidos anteriores). P(más de 2,5) = 1 − P(total ≤ 2).
Compara con el mercado (media de casas sin margen) y simula apostar cuando EV ≥ umbral,
con la cuota media, la de Bet365 (casa "blanda", lo más parecido a bwin) y la máxima.

Uso: python3 backtest_goles.py [--eval-desde 2020] [--alfa 0.07]
"""
import argparse, csv, math, os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
PARTIDOS = os.path.join(BASE, "datos", "historico", "partidos.csv")


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def p_mas25(lam):
    return 1 - math.exp(-lam) * (1 + lam + lam * lam / 2)


class Modelo:
    def __init__(self, alfa):
        self.a = alfa
        self.att = defaultdict(lambda: 0.9)   # equipo nuevo (ascendido): algo peor que la media
        self.dfn = defaultdict(lambda: 1.1)
        self.n = defaultdict(int)
        self.mu_l, self.mu_v = 1.5, 1.2

    def esperado(self, l, v):
        return self.mu_l * self.att[l] * self.dfn[v], self.mu_v * self.att[v] * self.dfn[l]

    def actualizar(self, l, v, gl, gv):
        a = self.a
        el, ev = self.esperado(l, v)
        # ataque: goles marcados / lo esperable dada la defensa rival; defensa: goles encajados / lo esperable
        self.att[l] += a * (gl / (self.mu_l * self.dfn[v]) - self.att[l])
        self.dfn[v] += a * (gl / (self.mu_l * self.att[l]) - self.dfn[v])
        self.att[v] += a * (gv / (self.mu_v * self.dfn[l]) - self.att[v])
        self.dfn[l] += a * (gv / (self.mu_v * self.att[v]) - self.dfn[l])
        self.mu_l += 0.01 * (gl - self.mu_l); self.mu_v += 0.01 * (gv - self.mu_v)
        self.n[l] += 1; self.n[v] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-desde", type=int, default=2020)
    ap.add_argument("--alfa", type=float, default=0.07)
    a = ap.parse_args()
    filas = list(csv.DictReader(open(PARTIDOS, encoding="utf-8")))
    por_liga = defaultdict(list)
    for f in filas:
        if f["fecha"] and f["gl"] != "":
            por_liga[f["liga"]].append(f)

    obs = []  # (liga, temporada, y, p_modelo, p_mercado, cuotas{fuente: (mas, menos)})
    for liga, fs in por_liga.items():
        m = Modelo(a.alfa)
        for f in sorted(fs, key=lambda x: x["fecha"]):
            l, v, gl, gv = f["local"], f["visitante"], int(f["gl"]), int(f["gv"])
            if int("20" + f["temporada"][:2]) >= a.eval_desde and m.n[l] >= 8 and m.n[v] >= 8:
                el, ev = m.esperado(l, v)
                p = p_mas25(el + ev)
                ma, me = num(f["c_mas25_avg"]), num(f["c_menos25_avg"])
                pm = (1 / ma) / (1 / ma + 1 / me) if ma and me else None
                cu = {k: (num(f[f"c_mas25_{k}"]), num(f[f"c_menos25_{k}"])) for k in ("avg", "b365", "max", "pin")}
                obs.append((liga, f["temporada"], int(gl + gv > 2), p, pm, cu))
            m.actualizar(l, v, gl, gv)

    con = [o for o in obs if o[4] is not None]
    lin = [f"Partidos evaluados: {len(obs)} (con cuotas: {len(con)}) desde {a.eval_desde}", ""]

    def ll(ps):
        return -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for y, p in ps) / len(ps)

    ps_mod = [(o[2], min(max(o[3], .01), .99)) for o in con]
    ps_mer = [(o[2], o[4]) for o in con]
    ps_mix = [(o[2], (o[3] + o[4]) / 2) for o in con]
    lin += ["Precisión (log-loss, menor = mejor):",
            f"  modelo {ll(ps_mod):.4f} | mercado {ll(ps_mer):.4f} | mezcla 50/50 {ll(ps_mix):.4f}",
            "  (si el mercado gana claramente, el modelo solo tiene sentido donde discrepa mucho)", ""]

    lin.append("Apostar cuando EV ≥ umbral (1 u por apuesta):")
    lin.append(f"  {'umbral':>6s} {'fuente':>5s} {'n':>6s} {'ROI':>7s} {'±err':>6s}")
    for umbral in (0.03, 0.05, 0.10):
        for fuente in ("avg", "b365", "max"):
            res = []
            for liga, t, y, p, pm, cu in con:
                o_mas, o_menos = cu[fuente]
                if not o_mas or not o_menos:
                    continue
                if p * o_mas - 1 >= umbral:
                    res.append((o_mas - 1) if y else -1.0)
                elif (1 - p) * o_menos - 1 >= umbral:
                    res.append((o_menos - 1) if not y else -1.0)
            if res:
                n = len(res); roi = sum(res) / n
                sd = (sum((r - roi) ** 2 for r in res) / n) ** 0.5 / n ** 0.5
                lin.append(f"  {umbral*100:5.0f}% {fuente:>5s} {n:6d} {roi*100:6.1f}% {sd*100:5.1f}")
    lin.append("")

    lin.append("Por liga (umbral 5 %, cuota Bet365) y referencia 'siempre más' / 'siempre menos' con cuota media:")
    for liga in sorted({o[0] for o in con}):
        sub = [o for o in con if o[0] == liga]
        res = [];
        for _, _, y, p, pm, cu in sub:
            om, on = cu["b365"]
            if om and on:
                if p * om - 1 >= .05: res.append((om - 1) if y else -1.0)
                elif (1 - p) * on - 1 >= .05: res.append((on - 1) if not y else -1.0)
        sm = [(cu["avg"][0] - 1) if y else -1.0 for _, _, y, _, _, cu in sub if cu["avg"][0]]
        sn = [(cu["avg"][1] - 1) if not y else -1.0 for _, _, y, _, _, cu in sub if cu["avg"][1]]
        f = lambda r: f"{sum(r)/len(r)*100:+.1f}% (n={len(r)})" if r else "-"
        lin.append(f"  {liga:4s} modelo {f(res):18s} siempre más {f(sm):18s} siempre menos {f(sn)}")
    lin.append("")

    # calibración del mercado: ¿los 60 % del mercado ocurren el 60 %?
    lin.append("Calibración del mercado (prob. sin margen → frecuencia real de 'más de 2,5'):")
    cub = defaultdict(list)
    for o in con:
        cub[min(int(o[4] * 10), 9)].append(o)
    for b in sorted(cub):
        s = cub[b]
        lin.append(f"  {b*10:3d}-{b*10+10:3d}%  n={len(s):5d}  mercado {sum(o[4] for o in s)/len(s)*100:5.1f}%  real {sum(o[2] for o in s)/len(s)*100:5.1f}%  modelo {sum(o[3] for o in s)/len(s)*100:5.1f}%")

    txt = "\n".join(lin); print(txt)
    os.makedirs(os.path.join(BASE, "analisis"), exist_ok=True)
    open(os.path.join(BASE, "analisis", "backtest_goles.txt"), "w", encoding="utf-8").write(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
