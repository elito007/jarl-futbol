#!/usr/bin/env python3
"""Arreglo puntual (oct-2026): capturas en las que local/visitante son jugadores en vez de equipos.
Deduce local y visitante de un mercado a 3 bandas «A / X / B» del mismo partido y reescribe el CSV.
Uso: reparar_nombres.py datos/cuotas/2026-10-0*.csv.gz"""
import csv, gzip, sys
from collections import defaultdict

for ruta in sys.argv[1:]:
    rows = list(csv.DictReader(gzip.open(ruta, "rt", encoding="utf-8")))
    if not rows:
        continue
    sel = defaultdict(list)
    for r in rows:
        sel[(r["fixture_id"], r["mercado_id"])].append(r["seleccion"])
    eq = {}
    for (fid, _), s in sel.items():
        if len(s) == 3 and s[1] == "X" and fid not in eq:
            eq[fid] = (s[0], s[2])
    n = 0
    for r in rows:
        if r["fixture_id"] in eq and (r["local"], r["visitante"]) != eq[r["fixture_id"]]:
            r["local"], r["visitante"] = eq[r["fixture_id"]]; n += 1
    if n:
        with gzip.open(ruta, "wt", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"{ruta}: {n} filas corregidas, partidos {len(eq)}: {sorted(set(eq.values()))}")
