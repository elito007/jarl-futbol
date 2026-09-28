#!/usr/bin/env python3
"""Captura de cuotas de fútbol en bwin.es: UNA petición para las 7 ligas.

Guarda solo partidos que empiezan en la ventana pedida y solo los mercados que nos interesan
(goles, córners, tarjetas, resultado y sus variantes simples; fuera combinadas, marcadores
exactos e intervalos de minutos) en datos/cuotas/AAAA-MM-DD_HHMM_<momento>.csv.gz.

Imprime: 'Guardado <ruta> (N filas, P partidos)' e 'INICIOS: iso,iso,...' (próximas 40 h),
que usa el planificador.
Uso: python3 bwin_futbol.py --momento manana|pre_partido [--horas 30] [--test]
"""
import argparse, csv, gzip, os, re, sys, time
from datetime import datetime, timedelta, timezone

import bwin_base as bw

LIGAS_BWIN = {"102829": "SP1", "102830": "SP2", "102841": "E0", "102839": "E1",
              "102846": "I1", "102842": "D1", "102843": "F1"}
DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "cuotas")
FUERA = re.compile(r"entre el|marcador|margen|resultado del partido y|y total de goles|y ambos|doble oportunidad y|"
                   r"desarrollo|descanso o final|al min\.|empieza perdiendo|tras haber ido|gana y ambos|"
                   r"combin|crea tu|minuto|intervalo", re.I)
CAMPOS = ["ts_utc", "momento", "liga", "fixture_id", "local", "visitante", "inicio_utc", "mercado_id", "mercado",
          "seleccion_id", "seleccion", "cuota", "prob_implicita", "overround_mercado", "n_selecciones"]


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def capturar(horas):
    j = bw._get("fixtures", fixtureTypes="Standard", state="Latest", offerMapping="All",
                competitionIds=",".join(LIGAS_BWIN), sortBy="StartDate")
    return j.get("fixtures", [])


def filas(fx, ahora, momento, horas):
    out, inicios = [], []
    tsu = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    for f in fx:
        ini = ts(f["startDate"])
        if ini <= ahora:
            continue
        if ini <= ahora + timedelta(hours=40):
            inicios.append(f["startDate"])
        if ini > ahora + timedelta(hours=horas):
            continue
        parts = [p.get("name", {}).get("value", "") for p in f.get("participants", [])]
        if len(parts) < 2:
            continue
        liga = LIGAS_BWIN.get(str((f.get("competition") or {}).get("id")), "?")
        for m in f.get("optionMarkets", []) + f.get("games", []):
            nom = (m.get("name") or {}).get("value", "")
            if not nom or FUERA.search(nom):
                continue
            opts = m.get("options") or m.get("results") or []
            sel = []
            for o in opts:
                c = (o.get("price") or {}).get("odds") or o.get("odds")
                if c:
                    sel.append(((o.get("name") or {}).get("value", ""), o.get("id", ""), float(c)))
            if not sel:
                continue
            ovr = round(sum(1 / c for _, _, c in sel), 4) if len(sel) >= 2 else ""
            for n, i, c in sel:
                out.append({"ts_utc": tsu, "momento": momento, "liga": liga, "fixture_id": f["id"],
                            "local": parts[0], "visitante": parts[1], "inicio_utc": f["startDate"],
                            "mercado_id": m.get("id", ""), "mercado": nom, "seleccion_id": i, "seleccion": n,
                            "cuota": c, "prob_implicita": round(1 / c, 4), "overround_mercado": ovr,
                            "n_selecciones": len(sel)})
    return out, sorted(set(inicios))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--momento", default="manual")
    ap.add_argument("--horas", type=float, default=30)
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    ahora = datetime.now(timezone.utc)
    try:
        fx = capturar(a.horas)
    except Exception as e:
        print(f"ERROR conexión bwin: {e}"); return 2
    rows, inicios = filas(fx, ahora, a.momento, a.horas)
    partidos = len({r["fixture_id"] for r in rows})
    print(f"fixtures recibidos: {len(fx)} | en ventana {a.horas:.0f} h: {partidos} partidos, {len(rows)} filas")
    print("INICIOS: " + ",".join(inicios))
    if a.test or not rows:
        return 0
    os.makedirs(DIR, exist_ok=True)
    ruta = os.path.join(DIR, f"{ahora:%Y-%m-%d_%H%M}_{a.momento}.csv.gz")
    with gzip.open(ruta, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS); w.writeheader(); w.writerows(rows)
    print(f"Guardado {os.path.relpath(ruta, os.path.dirname(os.path.dirname(DIR)))} ({len(rows)} filas, {partidos} partidos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
