#!/usr/bin/env python3
"""Comparativa de cuotas: cada propuesta de hoy (bwin) frente a otras casas españolas, Betfair y Pinnacle (vía OddsPapi).

Emparejado EXACTO, sin nombres: OddsPapi guarda para bwin.es el id de partido, mercado y selección de bwin
(bookmakerFixtureId / bookmakerMarketId / bookmakerOutcomeId), los mismos que tenemos en nuestra captura.
Con eso sabemos el marketId/outcomeId normalizado de OddsPapi y lo buscamos en las demás casas.

- Mejor cuota entre casas .es (bet365, Codere, Winamax, Betway, LeoVegas, Paf) → ⭐ si supera a bwin.
- Betfair Exchange: mejor cuota a favor, neta tras comisión (BETFAIR_COMISION, 5 %), y dinero disponible.
- Pinnacle (casa de referencia, margen bajo): cuota «justa» sin margen = 1 / prob. normalizada del mercado.
- Enlace directo al boleto de bwin (añade la selección con un clic).
Guarda datos/comparativas/<fecha>.csv para el informe. Imprime un bloque corto para Telegram (vacío si no hay nada).
Uso: comparar_casas.py [--fecha AAAA-MM-DD]
"""
import argparse, csv, glob, gzip, json, os, sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
PAPEL = os.path.join(BASE, "papel", "apuestas.csv")
CUOTAS = os.path.join(BASE, "datos", "cuotas")
OP = os.path.join(BASE, "datos", "cuotas_oddspapi")
SALIDA = os.path.join(BASE, "datos", "comparativas")
ES = {"bet365.es": "bet365", "codere.es": "Codere", "winamax.es": "Winamax", "betway.es": "Betway",
      "leovegas.es": "LeoVegas", "paf.es": "Paf"}
CAMPOS = ["fecha", "fixture_id", "partido", "mercado", "seleccion", "cuota_bwin", "mejor_es", "casa_mejor_es",
          "betfair_back", "betfair_neta", "betfair_disp", "pinnacle", "pinnacle_justa", "enlace_bwin"]


def comision():
    try:
        import casas_base as cb
        return float(os.environ.get("BETFAIR_COMISION") or (cb.credenciales("BETFAIR_COMISION") or {}).get("BETFAIR_COMISION") or 0.05)
    except Exception:
        return 0.05


def ids_bwin(fecha):
    """(fixture_id, mercado, seleccion) → (mercado_id, seleccion_id) desde las capturas de bwin del día."""
    out = {}
    for f in sorted(glob.glob(os.path.join(CUOTAS, f"{fecha}_*.csv.gz"))):
        for r in csv.DictReader(gzip.open(f, "rt", encoding="utf-8")):
            out[(r["fixture_id"], r["mercado"], r["seleccion"])] = (str(r["mercado_id"]), str(r["seleccion_id"]))
    return out


def precio(mk, market_id, outcome_id):
    o = ((mk.get(market_id) or {}).get("outcomes") or {}).get(outcome_id) or {}
    p = (o.get("players") or {}).get("0") or {}
    return p if p.get("active", True) and p.get("price") else None


def comparar(prop, idb, odds, com):
    bo = odds.get("bookmakerOdds", {})
    bw = (bo.get("bwin.es") or {}).get("markets", {})
    mid_b, oid_b = idb
    market_id = outcome_id = None
    for mid, m in bw.items():  # localizar el mercado/selección de bwin en el esquema de OddsPapi
        if str(m.get("bookmakerMarketId")) == mid_b:
            for oid, o in (m.get("outcomes") or {}).items():
                if str(((o.get("players") or {}).get("0") or {}).get("bookmakerOutcomeId")) == oid_b:
                    market_id, outcome_id = mid, oid
    if not market_id:
        return None
    pb = precio(bw, market_id, outcome_id)
    r = {"cuota_bwin": float(prop["cuota_tomada"]), "enlace_bwin": (pb or {}).get("betslip") or ""}
    mejores = [(precio((bo.get(c) or {}).get("markets", {}), market_id, outcome_id), n) for c, n in ES.items()]
    mejores = [(p["price"], n) for p, n in mejores if p]
    if mejores:
        r["mejor_es"], r["casa_mejor_es"] = max(mejores)
    for c in ("betfair.es", "betfair-ex"):
        p = precio((bo.get(c) or {}).get("markets", {}), market_id, outcome_id)
        if p:
            back = ((p.get("exchangeMeta") or {}).get("availableToBack") or [{}])[0]
            b = back.get("price") or p["price"]
            r.update(betfair_back=b, betfair_neta=round(1 + (b - 1) * (1 - com), 3), betfair_disp=back.get("size", ""))
            break
    pin = (bo.get("pinnacle") or {}).get("markets", {}).get(market_id)
    pp = precio((bo.get("pinnacle") or {}).get("markets", {}), market_id, outcome_id)
    if pin and pp:
        tot = sum(1 / q["price"] for q in (precio({market_id: pin}, market_id, o) for o in pin.get("outcomes", {})) if q)
        r["pinnacle"] = pp["price"]
        # solo mercados de selecciones excluyentes (suma de probabilidades ≈ 1 + margen); en «doble oportunidad» ≈ 2
        r["pinnacle_justa"] = round(pp["price"] * tot, 3) if 0.97 <= tot <= 1.2 else ""
    return r


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fecha"); a = ap.parse_args()
    fecha = a.fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not os.path.exists(PAPEL):
        return 0
    props = [p for p in csv.DictReader(open(PAPEL, encoding="utf-8")) if p.get("fecha") == fecha]
    if not props:
        return 0
    idx, com, filas, lin = ids_bwin(fecha), comision(), [], []
    for p in props:
        ruta = os.path.join(OP, f"{fecha}_{p['fixture_id'].replace(':', '-')}.json.gz")
        idb = idx.get((p["fixture_id"], p["mercado"], p["seleccion"]))
        if not os.path.exists(ruta) or not idb:
            continue
        r = comparar(p, idb, json.load(gzip.open(ruta, "rt", encoding="utf-8")).get("odds") or {}, com)
        if not r:
            continue
        filas.append({"fecha": fecha, "fixture_id": p["fixture_id"], "partido": p["partido"], "mercado": p["mercado"],
                      "seleccion": p["seleccion"], **r})
        t = [f"🎯 {p['mercado']} «{p['seleccion']}» — bwin {r['cuota_bwin']}"]
        if r.get("mejor_es"):
            t.append(f"{'⭐ ' if r['mejor_es'] > r['cuota_bwin'] else ''}{r['casa_mejor_es']} {r['mejor_es']}")
        if r.get("betfair_back"):
            t.append(f"Betfair {r['betfair_back']} (neta {r['betfair_neta']}, {r['betfair_disp']} €)")
        if r.get("pinnacle_justa"):
            t.append(f"Pinnacle justa {r['pinnacle_justa']}")
        lin.append(" · ".join(t))  # el enlace al boleto ya va en cada propuesta
    if filas:
        os.makedirs(SALIDA, exist_ok=True)
        with open(os.path.join(SALIDA, f"{fecha}.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=CAMPOS, restval=""); w.writeheader(); w.writerows(filas)
        print(f"🔎 Comparativa de cuotas ({len(filas)}/{len(props)} propuestas) · 📝 SOLO PAPEL\n" + "\n".join(lin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
