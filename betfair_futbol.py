#!/usr/bin/env python3
"""Captura de cuotas del Exchange ESPAÑOL de Betfair (API oficial) para las 7 ligas. Solo lectura: nunca apuesta.

Mismos momentos que bwin (lo lanza captura_auto.py tras cada captura de bwin). Guarda en
datos/cuotas_betfair/AAAA-MM-DD_HHMM_<momento>.csv.gz, por selección: mejor cuota a favor (back) y en contra (lay),
dinero disponible en cada una, dinero ya cruzado en el mercado y la cuota NETA tras la comisión:
    neta = 1 + (back − 1) · (1 − COMISION)
COMISION por defecto 5 % (cambiable con BETFAIR_COMISION=0.05 en .env.casas o en el entorno).

Uso:
  betfair_futbol.py --diagnostico           # 1 login + 2-3 peticiones: competiciones reconocidas y nombres de mercados
  betfair_futbol.py --momento manana --horas 30
Salida con código 3 y 'SIN CREDENCIALES' si falta .env.casas (ver casas_base.py).
"""
import argparse, csv, gzip, os, re, sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import casas_base as cb

LOGIN = os.environ.get("BETFAIR_LOGIN_URL", "https://identitysso.betfair.es/api/login")
API = os.environ.get("BETFAIR_API_URL", "https://api.betfair.es/exchange/betting/json-rpc/v1")
DIR = os.path.join(cb.BASE, "datos", "cuotas_betfair")
# nombre de la competición en Betfair (inglés o español) → código football-data que usamos en todo el sistema
LIGAS = [(re.compile(r"^(?!.*(federaci|women|femen|rfef)).*((spanish|españa|espana).*(segunda|la ?liga ?2)|^la ?liga ?2|hypermotion)", re.I), "SP2"),  # antes que SP1 («Spanish La Liga 2»)
         (re.compile(r"^(?!.*(women|femen|feminin|liga f)).*((spanish|españa|espana).*(la ?liga|primera)|^la ?liga( ea sports)?$)", re.I), "SP1"),
         (re.compile(r"english premier league|^premier league$|inglaterra.*premier", re.I), "E0"),
         (re.compile(r"^(?!.*(women|ladies)).*(english.*championship|^championship$|inglaterra.*championship)", re.I), "E1"),
         (re.compile(r"italian serie a|^serie a$|italia.*serie a", re.I), "I1"),
         (re.compile(r"german bundesliga$|^bundesliga$|alemania.*bundesliga$", re.I), "D1"),
         (re.compile(r"french ligue 1|^ligue 1|francia.*ligue 1", re.I), "F1")]
# mercados que no nos sirven (marcador exacto, goleadores, etc.)
FUERA = re.compile(r"correct score|resultado exacto|marcador|scorer|goleador|half time/full time|descanso/final|"
                   r"winning margin|margen|minute|minuto|to qualify|asian|handicap|hándicap", re.I)
CAMPOS = ["ts_utc", "momento", "liga", "event_id", "local", "visitante", "inicio_utc", "market_id", "mercado",
          "selection_id", "seleccion", "back", "back_disp", "lay", "lay_disp", "cruzado_mercado", "neta_back",
          "estado"]


def liga_de(nombre):
    for rx, cod in LIGAS:
        if rx.search(nombre or ""):
            return cod
    return None


class Betfair:
    def __init__(self, cred):
        self.cred = cred
        r = cb.http_json(LOGIN, {"username": cred["BETFAIR_USER"], "password": cred["BETFAIR_PASS"]},
                         {"X-Application": cred["BETFAIR_APP_KEY"]}, form=True)
        if r.get("status") != "SUCCESS":
            raise RuntimeError(f"login Betfair: {r.get('error') or r.get('status')}")
        self.token = r["token"]

    def llamar(self, metodo, params):
        r = cb.http_json(API, {"jsonrpc": "2.0", "method": f"SportsAPING/v1.0/{metodo}", "params": params, "id": 1},
                         {"X-Application": self.cred["BETFAIR_APP_KEY"], "X-Authentication": self.token})
        if "error" in r:
            raise RuntimeError(f"{metodo}: {r['error']}")
        return r["result"]

    def competiciones(self):
        res = self.llamar("listCompetitions", {"filter": {"eventTypeIds": ["1"]}})
        return {c["competition"]["id"]: c["competition"]["name"] for c in res}

    def catalogo(self, comp_ids, desde, hasta):
        return self.llamar("listMarketCatalogue", {
            "filter": {"eventTypeIds": ["1"], "competitionIds": comp_ids,
                       "marketStartTime": {"from": desde, "to": hasta}},
            "marketProjection": ["EVENT", "COMPETITION", "RUNNER_DESCRIPTION", "MARKET_START_TIME"],
            "maxResults": 1000})

    def libros(self, market_ids):
        out = []
        for i in range(0, len(market_ids), 40):  # 40 mercados × peso 5 = 200 (límite por petición)
            out += self.llamar("listMarketBook", {"marketIds": market_ids[i:i + 40], "priceProjection": {
                "priceData": ["EX_BEST_OFFERS"], "exBestOffersOverrides": {"bestPricesDepth": 1}}})
        return out


def comision():
    try:
        return float(os.environ.get("BETFAIR_COMISION") or (cb.credenciales("BETFAIR_COMISION") or {}).get("BETFAIR_COMISION") or 0.05)
    except ValueError:
        return 0.05


def filas(cat, libros, ahora, momento, com):
    lib = {b["marketId"]: b for b in libros}
    tsu = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for m in cat:
        b = lib.get(m["marketId"])
        if not b:
            continue
        ev = (m.get("event") or {}).get("name", "")
        loc, _, vis = ev.partition(" v ")
        nombres = {r["selectionId"]: r.get("runnerName", "") for r in m.get("runners", [])}
        for r in b.get("runners", []):
            ex = r.get("ex") or {}
            bk = (ex.get("availableToBack") or [{}])[0]
            ly = (ex.get("availableToLay") or [{}])[0]
            back = bk.get("price")
            out.append({"ts_utc": tsu, "momento": momento, "liga": liga_de((m.get("competition") or {}).get("name")),
                        "event_id": (m.get("event") or {}).get("id"), "local": loc.strip(), "visitante": vis.strip(),
                        "inicio_utc": m.get("marketStartTime"), "market_id": m["marketId"], "mercado": m.get("marketName"),
                        "selection_id": r.get("selectionId"), "seleccion": nombres.get(r.get("selectionId"), ""),
                        "back": back or "", "back_disp": round(bk.get("size", 0), 2) if back else "",
                        "lay": ly.get("price", ""), "lay_disp": round(ly.get("size", 0), 2) if ly.get("price") else "",
                        "cruzado_mercado": round(b.get("totalMatched") or 0, 2),
                        "neta_back": round(1 + (back - 1) * (1 - com), 4) if back else "", "estado": b.get("status", "")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--momento", default="manual")
    ap.add_argument("--horas", type=float, default=30)
    ap.add_argument("--diagnostico", action="store_true")
    a = ap.parse_args()
    cred = cb.credenciales("BETFAIR_APP_KEY", "BETFAIR_USER", "BETFAIR_PASS")
    if not cred:
        print("SIN CREDENCIALES Betfair (.env.casas)"); return cb.SIN_CRED
    secretos = list(cred.values())
    ahora = datetime.now(timezone.utc)
    try:
        bf = Betfair(cred)
        comps = bf.competiciones()
        nuestras = {cid: liga_de(n) for cid, n in comps.items() if liga_de(n)}
        if a.diagnostico:
            print(f"login OK · competiciones de fútbol: {len(comps)} · reconocidas: " +
                  ", ".join(f"{cod}={comps[cid]}" for cid, cod in sorted(nuestras.items(), key=lambda x: x[1])))
            falta = {c for _, c in LIGAS} - set(nuestras.values())
            if falta:
                cand = [n for n in comps.values() if re.search(r"liga|league|serie|bundes|ligue|champion|segunda|premier", n, re.I)]
                print(f"NO reconocidas: {sorted(falta)} · inglesas en el exchange: {sorted(n for n in comps.values() if re.search(r'english|england', n, re.I))}")
        if not nuestras:
            print("ERROR: ninguna de las 7 ligas reconocida en Betfair (ver --diagnostico)"); return 2
        desde, hasta = ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), (ahora + timedelta(hours=a.horas)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cat = [m for m in bf.catalogo(list(nuestras), desde, hasta) if not FUERA.search(m.get("marketName", ""))]
        if a.diagnostico:
            ev = Counter((m.get("event") or {}).get("name") for m in cat)
            print(f"partidos en {a.horas:.0f} h: {len(ev)} · mercados útiles: {len(cat)}")
            print("nombres de mercado (frecuencia): " + "; ".join(f"{n} ×{c}" for n, c in
                                                                     Counter(m.get("marketName") for m in cat).most_common(60)))
            if not cat:
                return 0
            cat = [m for m in cat if (m.get("event") or {}).get("name") == ev.most_common(1)[0][0]]  # un solo partido
        lib = bf.libros([m["marketId"] for m in cat]) if cat else []
    except Exception as e:
        print(f"ERROR Betfair: {cb.sin_secretos(e, *secretos)}"); return 2
    rows = filas(cat, lib, ahora, a.momento, comision())
    partidos = len({r["event_id"] for r in rows})
    con_precio = sum(1 for r in rows if r["back"])
    print(f"Betfair: {partidos} partidos, {len(rows)} selecciones ({con_precio} con cuota a favor)")
    if a.diagnostico:
        for r in rows[:25]:
            print(f"  {r['local']}-{r['visitante']} | {r['mercado']} | {r['seleccion']} | back {r['back']} "
                  f"({r['back_disp']} €) lay {r['lay']} | cruzado {r['cruzado_mercado']} € | neta {r['neta_back']}")
        return 0
    if not rows:
        return 0
    os.makedirs(DIR, exist_ok=True)
    ruta = os.path.join(DIR, f"{ahora:%Y-%m-%d_%H%M}_{a.momento}.csv.gz")
    with gzip.open(ruta, "wt", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS); w.writeheader(); w.writerows(rows)
    print(f"Guardado {os.path.relpath(ruta, cb.BASE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
