#!/usr/bin/env python3
"""Liquida todas las selecciones capturadas en bwin con los resultados de football-data.

Agrupa por fecha de inicio del partido: datos/liquidaciones/<AAAA-MM-DD>.csv (mismo formato que jarl-f1,
así sirve informe_mercados.py). Resultado: 1 gana, 0 pierde, V anulada, ? sin regla o sin dato.
Datos disponibles: goles (final y descanso), córners y tarjetas por equipo. No hay minuto de los goles
ni córners/tarjetas por parte: esos mercados quedan '?'.
Tarjetas = amarillas + rojas (football-data HY/HR). Pendiente confirmar cómo cuenta bwin la doble amarilla.

Uso: python3 liquidar_futbol.py [--todos]
"""
import argparse, csv, difflib, glob, gzip, os, re, unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(BASE, "datos", "historico", "partidos.csv")
CUOTAS = os.path.join(BASE, "datos", "cuotas")
SALIDA = os.path.join(BASE, "datos", "liquidaciones")

ALIAS = {"athletic club": "ath bilbao", "athletic bilbao": "ath bilbao", "atletico de madrid": "ath madrid",
         "atletico madrid": "ath madrid", "rayo vallecano": "vallecano", "espanyol": "espanol",
         "deportivo la coruna": "la coruna", "deportivo": "la coruna", "racing santander": "santander",
         "real sociedad": "sociedad", "real sociedad b": "sociedad b", "sporting gijon": "sp gijon",
         "sporting de gijon": "sp gijon", "celta de vigo": "celta", "celta vigo": "celta", "dep. alaves": "alaves",
         "deportivo alaves": "alaves", "real betis": "betis", "rcd mallorca": "mallorca",
         "manchester city": "man city", "manchester united": "man united", "nottingham forest": "nott'm forest",
         "wolverhampton": "wolves", "wolverhampton wanderers": "wolves", "west ham united": "west ham",
         "queens park rangers": "qpr", "west bromwich": "west brom", "west bromwich albion": "west brom",
         "sheffield utd": "sheffield united", "bayern munchen": "bayern munich", "fc bayern munchen": "bayern munich",
         "eintracht frankfurt": "ein frankfurt", "borussia monchengladbach": "m'gladbach", "1. fc koln": "fc koln",
         "borussia dortmund": "dortmund", "bayer leverkusen": "leverkusen", "werder bremen": "werder bremen",
         "1. fc union berlin": "union berlin", "vfb stuttgart": "stuttgart", "1. fsv mainz 05": "mainz",
         "paris saint-germain": "paris sg", "paris saint germain": "paris sg", "internazionale": "inter",
         "inter milan": "inter", "ac milan": "milan", "as roma": "roma", "ss lazio": "lazio"}


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def clave_equipo(t):
    t = norm(t)
    if t in ALIAS:
        return ALIAS[t]
    t = re.sub(r"\b(fc|cf|cd|ud|sd|rc|rcd|ac|afc|sc|ssc|as|us|club|calcio|1\.)\b", " ", t)
    return ALIAS.get(re.sub(r"\s+", " ", t).strip(), re.sub(r"\s+", " ", t).strip())


def sim(a, b):
    a, b = clave_equipo(a), clave_equipo(b)
    return 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()


def num(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


def cargar_resultados():
    por = defaultdict(list)
    if os.path.exists(HIST):
        for r in csv.DictReader(open(HIST, encoding="utf-8")):
            if r["gl"] != "":
                por[(r["liga"], r["fecha"])].append(r)
    return por


def emparejar(liga, inicio, local, visit, res):
    d = datetime.fromisoformat(inicio.replace("Z", "+00:00")).date()
    cands = []
    for k in (0, -1, 1):
        cands += res.get((liga, (d + timedelta(days=k)).isoformat()), [])
    mejor = max(cands, key=lambda r: sim(local, r["local"]) + sim(visit, r["visitante"]), default=None)
    if mejor and sim(local, mejor["local"]) + sim(visit, mejor["visitante"]) >= 1.3:
        return mejor
    return None


class Partido:
    def __init__(self, r, local, visit):
        i = lambda k: int(r[k]) if (r.get(k) or "").strip().isdigit() else None
        self.L, self.V = norm(local), norm(visit)
        self.gl, self.gv, self.gl1, self.gv1 = i("gl"), i("gv"), i("gl_1t"), i("gv_1t")
        self.gl2 = self.gl - self.gl1 if self.gl1 is not None else None
        self.gv2 = self.gv - self.gv1 if self.gv1 is not None else None
        self.cl, self.cv = i("corners_l"), i("corners_v")
        tl = [i("amarillas_l"), i("rojas_l")]; tv = [i("amarillas_v"), i("rojas_v")]
        self.tl = sum(tl) if None not in tl else None
        self.tv = sum(tv) if None not in tv else None

    def lado(self, sel):
        """'L', 'V', 'X' o None según el texto de la selección."""
        s = norm(sel)
        if s in ("x", "empate", "mismo numero"):
            return "X"
        if s == self.L or sim(s, self.L) > 0.85:
            return "L"
        if s == self.V or sim(s, self.V) > 0.85:
            return "V"
        return None


def linea(sel, n):
    s = norm(sel); x = num(re.sub(r"[^\d,\.]", "", s))
    if n is None or x is None:
        return None
    if s.startswith("mas de"):
        return int(n > x)
    if s.startswith("menos de"):
        return int(n < x)
    return None


def rango(sel, n):
    s = norm(sel)
    if n is None:
        return None
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", s)
    if m:
        return int(int(m.group(1)) <= n <= int(m.group(2)))
    m = re.match(r"^(\d+)\s*o mas$", s) or re.match(r"^(\d+)\+$", s)
    if m:
        return int(n >= int(m.group(1)))
    if s.isdigit():
        return int(n == int(s))
    return None


def sino(sel, v):
    if v is None:
        return None
    s = norm(sel)
    return int(v) if s in ("si", "sí") else (1 - int(v)) if s == "no" else None


def res_1x2(a, b):
    return None if a is None or b is None else ("L" if a > b else "V" if b > a else "X")


def resolver(mercado, sel, p):
    """(tipo, resultado) para una selección."""
    m = norm(mercado)
    for eq, g, g1, g2, c, t in (("L", p.gl, p.gl1, p.gl2, p.cl, p.tl), ("V", p.gv, p.gv1, p.gv2, p.cv, p.tv)):
        nom = p.L if eq == "L" else p.V
        if m.startswith(nom + " - "):
            resto = m[len(nom) + 3:]
            if resto == "total de goles":
                return "equipo_goles", linea(sel, g)
            if resto == "total de goles - 1a parte":
                return "equipo_goles_1t", linea(sel, g1)
            if resto == "total de goles - 2a parte":
                return "equipo_goles_2t", linea(sel, g2)
            if resto.startswith("numero de corners ("):
                return "equipo_corners_rango", rango(sel, c)
            if resto.startswith("numero de tarjetas") or resto.startswith("total de tarjetas"):
                return "equipo_tarjetas", linea(sel, t) if norm(sel).startswith(("mas", "menos")) else rango(sel, t)
            return None, None
        if m == nom + " marca":
            return "equipo_marca", sino(sel, None if g is None else g > 0)
        if m == nom + " marca en ambas partes":
            return "equipo_marca_ambas", sino(sel, None if g1 is None else (g1 > 0 and g2 > 0))
        if m == nom + " no cuenta":  # si gana ese equipo, anulada
            r = res_1x2(p.gl, p.gv)
            if r is None:
                return "sin_equipo", None
            if r == eq:
                return "sin_equipo", "V"
            return "sin_equipo", int(p.lado(sel) == r)
    T, T1 = p.gl + p.gv, (p.gl1 + p.gv1 if p.gl1 is not None else None)
    T2 = T - T1 if T1 is not None else None
    C = p.cl + p.cv if p.cl is not None else None
    TT = p.tl + p.tv if p.tl is not None else None
    if m == "total de goles":
        return "goles", linea(sel, T)
    if m == "total de goles - 1a parte":
        return "goles_1t", linea(sel, T1)
    if m == "total de goles - 2a parte":
        return "goles_2t", linea(sel, T2)
    if m == "numero exacto de goles":
        return "goles_exacto", rango(sel, T)
    if m in ("total de goles par o impar", "goles totales par o impar"):
        return "goles_par", int((T % 2 == 0) == (norm(sel) == "par"))
    if m == "goles totales par o impar - 1a parte":
        return "goles_par_1t", None if T1 is None else int((T1 % 2 == 0) == (norm(sel) == "par"))
    if m == "ambos equipos marcan":
        return "btts", sino(sel, p.gl > 0 and p.gv > 0)
    if m == "ambos equipos marcan en la 1a parte":
        return "btts_1t", sino(sel, None if p.gl1 is None else p.gl1 > 0 and p.gv1 > 0)
    if m == "ambos equipos marcan en la 2a parte":
        return "btts_2t", sino(sel, None if p.gl2 is None else p.gl2 > 0 and p.gv2 > 0)
    if m == "¿habra gol en ambas partes?":
        return "gol_ambas_partes", sino(sel, None if T1 is None else T1 > 0 and T2 > 0)
    if m.startswith("gana el partido exactamente por"):
        n = int(re.search(r"(\d+)", m).group(1))
        return "gana_por_n", sino(sel, abs(p.gl - p.gv) == n)
    if m in ("resultado del partido", "resultado", "1x2", "resultado final"):
        return "1x2", int(p.lado(sel) == res_1x2(p.gl, p.gv))
    if m == "resultado - 1a parte":
        r = res_1x2(p.gl1, p.gv1); return "1x2_1t", None if r is None else int(p.lado(sel) == r)
    if m == "resultado - 2a parte":
        r = res_1x2(p.gl2, p.gv2); return "1x2_2t", None if r is None else int(p.lado(sel) == r)
    if m.startswith("doble oportunidad"):
        a, b = {"doble oportunidad": (p.gl, p.gv), "doble oportunidad - 1a parte": (p.gl1, p.gv1),
                "doble oportunidad - 2a parte": (p.gl2, p.gv2)}.get(m, (None, None))
        r = res_1x2(a, b)
        partes = [p.lado(x.strip()) for x in re.split(r"\bo\b", norm(sel))]
        return "doble_oportunidad" + ("" if m == "doble oportunidad" else "_parte"), None if r is None or None in partes else int(r in partes)
    if m.startswith("ganador sin empate"):
        a, b = {"ganador sin empate": (p.gl, p.gv), "ganador sin empate - 1a parte": (p.gl1, p.gv1),
                "ganador sin empate - 2a parte": (p.gl2, p.gv2)}.get(m, (None, None))
        r = res_1x2(a, b)
        return "dnb", None if r is None else ("V" if r == "X" else int(p.lado(sel) == r))
    if m == "gana ambas partes":
        a, b = res_1x2(p.gl1, p.gv1), res_1x2(p.gl2, p.gv2)
        if a is None:
            return "gana_ambas_partes", None
        g = a if a == b and a != "X" else None
        l = p.lado(sel)
        return "gana_ambas_partes", int(l == g) if l else int(g is None)
    # córners
    if m.startswith("numero de corners (") :
        return "corners_rango", rango(sel, C)
    if m in ("total de corners", "numero de corners", "total de corners lanzados"):
        return "corners_linea", linea(sel, C)
    if m == "total de corners lanzados par o impar":
        return "corners_par", None if C is None else int((C % 2 == 0) == (norm(sel) == "par"))
    if m == "mas corners":
        return "mas_corners", None if C is None else int(p.lado(sel) == res_1x2(p.cl, p.cv))
    mm = re.match(r"ambos equipos (\d+)\+ corners", m)
    if mm:
        n = int(mm.group(1)); return f"ambos_{n}_corners", sino(sel, None if C is None else p.cl >= n and p.cv >= n)
    # tarjetas
    if m == "mas tarjetas":
        return "mas_tarjetas", None if TT is None else int(p.lado(sel) == res_1x2(p.tl, p.tv))
    mm = re.match(r"ambos equipos (\d+)\+ tarjetas", m)
    if mm:
        n = int(mm.group(1)); return f"ambos_{n}_tarjetas", sino(sel, None if TT is None else p.tl >= n and p.tv >= n)
    if m in ("total de tarjetas", "numero de tarjetas", "total de tarjetas mostradas"):
        s = norm(sel)
        return "tarjetas_total", linea(sel, TT) if s.startswith(("mas", "menos")) else rango(sel, TT)
    return None, None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--todos", action="store_true"); a = ap.parse_args()
    res = cargar_resultados()
    por_fecha = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(CUOTAS, "*.csv.gz"))):
        for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8")):
            if r["ts_utc"] < r["inicio_utc"]:
                por_fecha[r["inicio_utc"][:10]].append(r)
    os.makedirs(SALIDA, exist_ok=True)
    hoy = datetime.now(timezone.utc).date()
    for fecha, rows in sorted(por_fecha.items()):
        destino = os.path.join(SALIDA, f"{fecha}.csv")
        if os.path.exists(destino) and not a.todos and date.fromisoformat(fecha) < hoy - timedelta(days=10):
            continue
        partidos = {}
        for r in rows:
            k = r["fixture_id"]
            if k not in partidos:
                fd = emparejar(r["liga"], r["inicio_utc"], r["local"], r["visitante"], res)
                partidos[k] = Partido(fd, r["local"], r["visitante"]) if fd else None
        if not any(partidos.values()):
            continue
        # overround por mercado y captura (ya viene en la fila)
        out, st = [], defaultdict(int)
        for r in rows:
            p = partidos[r["fixture_id"]]
            tipo, v = (None, None)
            if p:
                try:
                    tipo, v = resolver(r["mercado"], r["seleccion"], p)
                except Exception:
                    tipo, v = "error", None
            ovr = num(r["overround_mercado"]); c = float(r["cuota"])
            pj = round(float(r["prob_implicita"]) / ovr, 4) if ovr else ""
            ben = (c - 1 if v == 1 else -1 if v == 0 else 0) if v in (0, 1, "V") else ""
            out.append({"ts_utc": r["ts_utc"], "momento": r["momento"], "liga": r["liga"], "fixture_id": r["fixture_id"],
                        "fixture": f"{r['local']} - {r['visitante']}", "mercado_id": r["mercado_id"], "mercado": r["mercado"],
                        "seleccion_id": r["seleccion_id"], "seleccion": r["seleccion"], "cuota": r["cuota"],
                        "overround_mercado": r["overround_mercado"], "n_selecciones": r["n_selecciones"],
                        "tipo": tipo or ("sin_regla" if p else "sin_resultado"), "prob_justa": pj,
                        "resultado": "?" if v is None else v, "beneficio_1u": round(ben, 3) if ben != "" else ""})
            st["resuelta" if v in (0, 1) else "anulada" if v == "V" else "sin_resultado" if not p else "sin_regla/dato"] += 1
        with open(destino, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
        emp = sum(1 for v in partidos.values() if v)
        print(f"{fecha}: {emp}/{len(partidos)} partidos con resultado | {dict(st)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
