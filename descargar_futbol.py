#!/usr/bin/env python3
"""Descarga el histórico de football-data.co.uk (resultados, estadísticas y cuotas de cierre).

Guarda cada liga/temporada en datos/historico/<div>_<temporada>.csv (tal cual) y un fichero
unificado datos/historico/partidos.csv con las columnas que usan los backtests.
Uso: python3 descargar_futbol.py [--desde 2019] [--ligas E0,E1,SP1,SP2,I1,D1,F1]
Solo librería estándar. Incremental: las temporadas cerradas no se vuelven a pedir.
"""
import argparse, csv, io, os, sys, time, urllib.request
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, "datos", "historico")
URL = "https://www.football-data.co.uk/mmz4281/{t}/{d}.csv"
LIGAS = {"E0": "Premier League", "E1": "Championship", "SP1": "LaLiga", "SP2": "LaLiga 2",
         "I1": "Serie A", "D1": "Bundesliga", "F1": "Ligue 1"}
# columnas normalizadas (vacío si la liga/temporada no la trae)
CAMPOS = ["liga", "temporada", "fecha", "local", "visitante", "gl", "gv", "gl_1t", "gv_1t",
          "corners_l", "corners_v", "amarillas_l", "amarillas_v", "rojas_l", "rojas_v", "arbitro",
          "c_mas25_avg", "c_menos25_avg", "c_mas25_max", "c_menos25_max", "c_mas25_b365", "c_menos25_b365",
          "c_mas25_pin", "c_menos25_pin", "c_1_avg", "c_x_avg", "c_2_avg"]
ORIG = {"local": "HomeTeam", "visitante": "AwayTeam", "gl": "FTHG", "gv": "FTAG", "gl_1t": "HTHG", "gv_1t": "HTAG",
        "corners_l": "HC", "corners_v": "AC", "amarillas_l": "HY", "amarillas_v": "AY", "rojas_l": "HR", "rojas_v": "AR",
        "arbitro": "Referee",
        # cierre (C) si existe; si no, la columna antigua
        "c_mas25_avg": ["AvgC>2.5", "Avg>2.5", "BbAv>2.5"], "c_menos25_avg": ["AvgC<2.5", "Avg<2.5", "BbAv<2.5"],
        "c_mas25_max": ["MaxC>2.5", "Max>2.5", "BbMx>2.5"], "c_menos25_max": ["MaxC<2.5", "Max<2.5", "BbMx<2.5"],
        "c_mas25_b365": ["B365C>2.5", "B365>2.5"], "c_menos25_b365": ["B365C<2.5", "B365<2.5"],
        "c_mas25_pin": ["PC>2.5", "P>2.5"], "c_menos25_pin": ["PC<2.5", "P<2.5"],
        "c_1_avg": ["AvgCH", "AvgH", "BbAvH"], "c_x_avg": ["AvgCD", "AvgD", "BbAvD"], "c_2_avg": ["AvgCA", "AvgA", "BbAvA"]}


def temporadas(desde):
    hoy = datetime.now()
    ult = hoy.year if hoy.month >= 7 else hoy.year - 1   # temporada en curso empieza en verano
    return [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(desde, ult + 1)], f"{ult % 100:02d}{(ult + 1) % 100:02d}"


def fecha_iso(s):
    for f in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s.strip(), f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def normalizar(texto, div, temp):
    out = []
    for r in csv.DictReader(io.StringIO(texto)):
        if not r.get("HomeTeam"):
            continue
        f = {"liga": div, "temporada": temp, "fecha": fecha_iso(r.get("Date", ""))}
        for k, v in ORIG.items():
            cols = v if isinstance(v, list) else [v]
            f[k] = next((r[c].strip() for c in cols if (r.get(c) or "").strip()), "")
        out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2019)
    ap.add_argument("--ligas", default=",".join(LIGAS))
    a = ap.parse_args()
    os.makedirs(DIR, exist_ok=True)
    temps, actual = temporadas(a.desde)
    todos, fallos = [], []
    for d in a.ligas.split(","):
        for t in temps:
            ruta = os.path.join(DIR, f"{d}_{t}.csv")
            if not os.path.exists(ruta) or t == actual:
                try:
                    time.sleep(1)
                    req = urllib.request.Request(URL.format(t=t, d=d), headers={"User-Agent": "Mozilla/5.0 (jarl-futbol)"})
                    with urllib.request.urlopen(req, timeout=30) as r:
                        open(ruta, "wb").write(r.read())
                except Exception as e:
                    fallos.append(f"{d} {t}: {e}")
                    continue
            txt = open(ruta, "rb").read().decode("utf-8-sig", errors="replace")
            todos += normalizar(txt, d, t)
    todos.sort(key=lambda f: (f["liga"], f["fecha"]))
    with open(os.path.join(DIR, "partidos.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS); w.writeheader(); w.writerows(todos)
    print(f"partidos.csv: {len(todos)} partidos, {len({(f['liga'], f['temporada']) for f in todos})} liga-temporadas")
    for x in fallos:
        print("  fallo:", x)
    return 0 if todos else 1


if __name__ == "__main__":
    sys.exit(main())
