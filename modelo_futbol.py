#!/usr/bin/env python3
"""Probabilidades de córners y tarjetas por partido (modelo del backtest, ya calibrado en la fase 1).

Por equipo y condición (local/visitante), media exponencial de lo que GENERA y lo que CONCEDE el rival,
sobre todas las temporadas disponibles (el ritmo de la temporada actual pesa más por ser lo último).
Esperado de un lado = (genera_equipo + concede_rival) / 2. Distribución por lado: binomial negativa
con la dispersión de cada liga (tarjetas ≈ Poisson; córners más dispersos). Los dos lados se tratan
como independientes para calcular totales, «más córners/tarjetas» y «ambos equipos N+».
Goles NO: el mercado predice mejor que nuestro modelo (fase 1).
"""
import csv, math, os, re
from collections import defaultdict

import liquidar_futbol as lq

BASE = os.path.dirname(os.path.abspath(__file__))
ALFA = 0.08
MAXN = 40


def nb_pmf(mu, r, maxn=MAXN):
    if r > 1e4:  # Poisson
        return [math.exp(-mu + k * math.log(mu) - math.lgamma(k + 1)) if mu > 0 else float(k == 0) for k in range(maxn)]
    p = r / (r + mu)
    return [math.exp(math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1) + r * math.log(p) + k * math.log(1 - p)) for k in range(maxn)]


def dispersion(xs):
    mu = sum(xs) / len(xs); var = sum((x - mu) ** 2 for x in xs) / len(xs)
    return mu * mu / (var - mu) if var > mu * 1.05 else 1e6


class Modelo:
    def __init__(self, ruta=os.path.join(BASE, "datos", "historico", "partidos.csv")):
        self.gen = {"corners": {}, "tarjetas": {}}; self.con = {"corners": {}, "tarjetas": {}}
        self.n = defaultdict(int); self.r = {}; self.rt = {}; self.equipos = defaultdict(set)
        res_lado = defaultdict(list); res_tot = defaultdict(list)  # (x, mu predicho) para la dispersión condicional
        filas = [f for f in csv.DictReader(open(ruta, encoding="utf-8")) if f["fecha"] and f["corners_l"] != ""]
        for f in sorted(filas, key=lambda x: x["fecha"]):
            liga, l, v = f["liga"], f["local"], f["visitante"]
            self.equipos[liga] |= {l, v}
            try:
                vals = {"corners": (int(f["corners_l"]), int(f["corners_v"])),
                        "tarjetas": (int(f["amarillas_l"]) + int(f["rojas_l"] or 0), int(f["amarillas_v"]) + int(f["rojas_v"] or 0))}
            except ValueError:
                continue
            for q, (xl, xv) in vals.items():
                g, c = self.gen[q], self.con[q]
                kl, kv = (liga, l, "L"), (liga, v, "V")
                if kl in g and kv in g and kl in c and kv in c and self.n[(liga, l)] >= 6 and self.n[(liga, v)] >= 6:
                    ml = (g[kl] + c[kv]) / 2; mv = (g[kv] + c[kl]) / 2
                    res_lado[(liga, q)] += [(xl, ml), (xv, mv)]; res_tot[(liga, q)].append((xl + xv, ml + mv))
                for d, k, x in ((self.gen[q], (liga, l, "L"), xl), (self.gen[q], (liga, v, "V"), xv),
                                (self.con[q], (liga, v, "V"), xl), (self.con[q], (liga, l, "L"), xv)):
                    d[k] = x if k not in d else d[k] + ALFA * (x - d[k])
            self.n[(liga, l)] += 1; self.n[(liga, v)] += 1
        for d, dst in ((res_lado, self.r), (res_tot, self.rt)):
            for k, xs in d.items():
                xs = xs[-2000:]
                m2 = sum(mu * mu for _, mu in xs) / len(xs); mm = sum(mu for _, mu in xs) / len(xs)
                ex = sum((x - mu) ** 2 for x, mu in xs) / len(xs) - mm   # varianza extra sobre Poisson
                dst[k] = m2 / ex if ex > 0.02 * mm else 1e6

    def equipo(self, liga, nombre):
        cands = self.equipos.get(liga, set())
        mejor = max(cands, key=lambda e: lq.sim(nombre, e), default=None)
        return mejor if mejor and lq.sim(nombre, mejor) >= 0.65 else None

    def lados(self, liga, local, visit, q):
        """(pmf_local, pmf_visitante) o None si falta historia (equipo nuevo o < 6 partidos)."""
        l, v = self.equipo(liga, local), self.equipo(liga, visit)
        if not l or not v or self.n[(liga, l)] < 6 or self.n[(liga, v)] < 6:
            return None
        g, c = self.gen[q], self.con[q]
        try:
            ml = (g[(liga, l, "L")] + c[(liga, v, "V")]) / 2
            mv = (g[(liga, v, "V")] + c[(liga, l, "L")]) / 2
        except KeyError:
            return None
        r = self.r.get((liga, q), 1e6)
        return nb_pmf(ml, r), nb_pmf(mv, r), nb_pmf(ml + mv, self.rt.get((liga, q), 1e6), 2 * MAXN)

    @staticmethod
    def evento(local, visit, mercado, sel):
        """Clave canónica del suceso que gana la selección, para detectar apuestas equivalentes entre mercados
        distintos de bwin (p. ej. «Real Oviedo - Número de córners» «0-3» ≡ «Real Oviedo - Total de córners» «Menos de 3,5»).
        Rangos → (stat, ámbito L/V/T, mín, máx|None). Resto → (mercado, selección) normalizados."""
        m = lq.norm(mercado); s = lq.norm(sel)
        q = "corners" if "corner" in m else "tarjetas" if "tarjeta" in m else None
        def rango(s):
            mm = re.match(r"^(\d+)\s*-\s*(\d+)$", s)
            if mm:
                return int(mm.group(1)), int(mm.group(2))
            mm = re.match(r"^(\d+)\s*o mas$", s)
            if mm:
                return int(mm.group(1)), None
            if s.isdigit():
                return int(s), int(s)
            x = lq.num(re.sub(r"[^\d,\.]", "", s))
            if x is not None and s.startswith("mas de"):
                return math.floor(x) + 1, None
            if x is not None and s.startswith("menos de"):
                return 0, math.floor(x)
            return None
        if q and "parte" not in m:
            amb = None
            for nom, lado in ((lq.norm(local), "L"), (lq.norm(visit), "V")):
                if m.startswith(nom + " - ") and ("numero de" in m or "total de" in m):
                    amb = lado
            if amb is None and (m.startswith("numero de corners (") or m.startswith("numero de tarjetas")
                                or m.startswith("total de corners") or m.startswith("total de tarjetas")):
                amb = "T"
            r = rango(s) if amb else None
            if r:
                return (q, amb) + r
        return (m, s)

    def prob(self, liga, local, visit, mercado, sel):
        """Probabilidad de que gane la selección, o None si el mercado no es del modelo."""
        m = lq.norm(mercado); s = lq.norm(sel)
        q = "corners" if "corner" in m else "tarjetas" if "tarjeta" in m else None
        if not q or "parte" in m or "par o impar" in m or "1" + "°" in m or "1°" in mercado:
            return None
        ld = self.lados(liga, local, visit, q)
        if not ld:
            return None
        pl, pv, tot = ld  # total con su propia dispersión (calibrada en el backtest)
        L, V = lq.norm(local), lq.norm(visit)
        def dist_rango(pmf, s):
            mm = re.match(r"^(\d+)\s*-\s*(\d+)$", s)
            if mm:
                return sum(pmf[int(mm.group(1)):int(mm.group(2)) + 1])
            mm = re.match(r"^(\d+)\s*o mas$", s)
            if mm:
                return sum(pmf[int(mm.group(1)):])
            if s.isdigit():
                return pmf[int(s)]
            x = lq.num(re.sub(r"[^\d,\.]", "", s))
            if x is not None and s.startswith("mas de"):
                return sum(pmf[math.floor(x) + 1:])
            if x is not None and s.startswith("menos de"):
                return sum(pmf[:math.floor(x) + 1])
            return None
        # mercados de un equipo
        for nom, pmf in ((L, pl), (V, pv)):
            if m.startswith(nom + " - "):
                return dist_rango(pmf, s)
        mm = re.match(r"ambos equipos (\d+)\+ (corners|tarjetas)", m)
        if mm:
            n = int(mm.group(1)); pa = sum(pl[n:]) * sum(pv[n:])
            return pa if s in ("si", "sí") else 1 - pa if s == "no" else None
        if m in ("mas corners", "mas tarjetas"):
            gl = sum(a * sum(pv[:i]) for i, a in enumerate(pl))
            gv = sum(b * sum(pl[:j]) for j, b in enumerate(pv))
            lado = "X" if s in ("x", "empate") else "L" if lq.sim(s, L) > 0.85 else "V" if lq.sim(s, V) > 0.85 else None
            return {"L": gl, "V": gv, "X": 1 - gl - gv}.get(lado)
        if m.startswith("numero de corners (") or m.startswith("numero de tarjetas") or m.startswith("total de corners") or m.startswith("total de tarjetas"):
            return dist_rango(tot, s)
        return None
