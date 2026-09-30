#!/usr/bin/env python3
"""Cuotas de otras casas españolas vía OddsPapi (agregador; no toca las webs de las casas). Solo lectura.

Plan gratuito: 250 peticiones/mes → solo se consultan los partidos con propuestas del día, con presupuesto:
máx. ODDSPAPI_MAX_MES (230) al mes y ODDSPAPI_MAX_DIA (8) al día, contadas en datos/oddspapi_presupuesto.json.
Casas: ODDSPAPI_CASAS (slugs separados por comas; vacío = todas). Los slugs reales salen del --diagnostico.

Fase 1: guarda la respuesta cruda de cada partido en datos/cuotas_oddspapi/<fecha>_<fixture>.json.gz.
El parser de córners/tarjetas se escribe cuando veamos la estructura real (--diagnostico).

Uso:
  oddspapi_futbol.py --diagnostico       # ≈4 peticiones: casas, partidos de nuestras ligas, nombres, cuotas de un partido
  oddspapi_futbol.py --propuestas        # partidos con propuestas pendientes de hoy
Código 3 y 'SIN CREDENCIALES' si falta ODDSPAPI_KEY en .env.casas.
"""
import argparse, csv, difflib, gzip, json, os, re, sys, time, unicodedata, urllib.parse
from datetime import datetime, timedelta, timezone

import casas_base as cb

API = os.environ.get("ODDSPAPI_URL", "https://api.oddspapi.io/v4")
SPORT = os.environ.get("ODDSPAPI_SPORT", "10")  # fútbol
DIR = os.path.join(cb.BASE, "datos", "cuotas_oddspapi")
PRESU = os.path.join(cb.BASE, "datos", "oddspapi_presupuesto.json")
PAPEL = os.path.join(cb.BASE, "papel", "apuestas.csv")
PARTICIPANTES = os.path.join(cb.BASE, "datos", "oddspapi_participantes.json")  # id → nombre (caché mensual)
# ids de torneo de OddsPapi (diagnóstico 30-sep-2026) → nuestros códigos
TORNEOS = {8: "SP1", 54: "SP2", 17: "E0", 18: "E1", 23: "I1", 35: "D1", 34: "F1"}
RX_CASAS = re.compile(r"bet365|codere|winamax|bwin|betfair|sportium|pinnacle|betway|leovegas|paf|william|marca|retabet|kirol|luckia", re.I)


def cfg(clave, defecto):
    return os.environ.get(clave) or (cb.credenciales(clave) or {}).get(clave) or defecto


class Presupuesto:
    def __init__(self, ahora):
        self.mes, self.dia = ahora.strftime("%Y-%m"), ahora.strftime("%Y-%m-%d")
        d = json.load(open(PRESU)) if os.path.exists(PRESU) else {}
        self.d = d if d.get("mes") == self.mes else {"mes": self.mes, "usadas": 0, "por_dia": {}}
        self.max_mes, self.max_dia = int(cfg("ODDSPAPI_MAX_MES", 230)), int(cfg("ODDSPAPI_MAX_DIA", 8))

    def quedan(self):
        return min(self.max_mes - self.d["usadas"], self.max_dia - self.d["por_dia"].get(self.dia, 0))

    def gastar(self):
        self.d["usadas"] += 1
        self.d["por_dia"][self.dia] = self.d["por_dia"].get(self.dia, 0) + 1
        os.makedirs(os.path.dirname(PRESU), exist_ok=True)
        json.dump(self.d, open(PRESU, "w"), indent=1)


class OddsPapi:
    def __init__(self, key, presu):
        self.key, self.presu = key, presu

    def get(self, ruta, **params):
        if self.presu.quedan() <= 0:
            raise RuntimeError("presupuesto de OddsPapi agotado (día o mes)")
        params["apiKey"] = self.key
        self.presu.gastar()
        time.sleep(1.2)  # ≥1 s entre llamadas
        return cb.http_json(f"{API}/{ruta}?{urllib.parse.urlencode(params)}")


def lista(r):
    if isinstance(r, list):
        return r
    if isinstance(r, dict):
        for k in ("data", "fixtures", "items", "results", "bookmakers", "markets"):
            if isinstance(r.get(k), list):
                return r[k]
        return list(r.values()) if all(isinstance(v, dict) for v in r.values()) else [r]
    return []


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", " ", t)


def textos(d):
    """Todas las cadenas de un fixture (nombres de equipos, torneo...) para emparejar sin conocer el esquema."""
    out = []
    if isinstance(d, dict):
        for v in d.values():
            out += textos(v)
    elif isinstance(d, list):
        for v in d:
            out += textos(v)
    elif isinstance(d, str):
        out.append(d)
    return out


def inicio(d):
    for k, v in (d.items() if isinstance(d, dict) else []):
        if "start" in k.lower() and isinstance(v, (str, int, float)):
            try:
                return datetime.fromtimestamp(v / (1000 if v > 1e11 else 1), timezone.utc) if isinstance(v, (int, float)) \
                    else datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                return None
    return None


def fixture_id(d):
    for k in ("fixtureId", "id", "fixture_id"):
        if isinstance(d, dict) and d.get(k):
            return d[k]
    return None


def nombres_participantes(op, ids, ahora):
    """Nombres de equipos por id, con caché en disco (1 petición al mes como mucho)."""
    cache = json.load(open(PARTICIPANTES)) if os.path.exists(PARTICIPANTES) else {}
    if cache.get("_mes") != ahora.strftime("%Y-%m") or any(str(i) not in cache for i in ids):
        for x in lista(op.get("participants", sportId=SPORT)):
            if isinstance(x, dict):
                pid = x.get("participantId") or x.get("id")
                nom = x.get("participantName") or x.get("name") or x.get("shortName")
                if pid and nom:
                    cache[str(pid)] = nom
        cache["_mes"] = ahora.strftime("%Y-%m")
        os.makedirs(os.path.dirname(PARTICIPANTES), exist_ok=True)
        json.dump(cache, open(PARTICIPANTES, "w"), ensure_ascii=False)
    return cache


def con_nombres(fx, nombres):
    for f in fx:
        f["_local"] = nombres.get(str(f.get("participant1Id")), "")
        f["_visitante"] = nombres.get(str(f.get("participant2Id")), "")
    return fx


def nuestros(fx):
    return [f for f in fx if isinstance(f, dict) and f.get("tournamentId") in TORNEOS]


def emparejar(fixtures, local, visit, ini):
    """Mejor fixture de OddsPapi para (local, visitante, hora): hora ±2 h y parecido de nombres ≥ 0,55 en ambos."""
    mejor, pmejor = None, 0
    for f in fixtures:
        t = inicio(f)
        if t and abs((t - ini).total_seconds()) > 7200:
            continue
        tx = [norm(s) for s in ([f.get("_local", ""), f.get("_visitante", "")] if f.get("_local") else textos(f)) if 2 < len(s) < 60]
        pl = max((difflib.SequenceMatcher(None, norm(local), s).ratio() for s in tx), default=0)
        pv = max((difflib.SequenceMatcher(None, norm(visit), s).ratio() for s in tx), default=0)
        if min(pl, pv) >= 0.55 and pl + pv > pmejor:
            mejor, pmejor = f, pl + pv
    return mejor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnostico", action="store_true")
    ap.add_argument("--propuestas", action="store_true")
    a = ap.parse_args()
    cred = cb.credenciales("ODDSPAPI_KEY")
    if not cred:
        print("SIN CREDENCIALES OddsPapi (.env.casas)"); return cb.SIN_CRED
    key = cred["ODDSPAPI_KEY"]
    ahora = datetime.now(timezone.utc)
    presu = Presupuesto(ahora)
    op = OddsPapi(key, presu)
    casas = cfg("ODDSPAPI_CASAS", "")  # vacío = todas; los slugs válidos salen del --diagnostico
    hoy, manana = ahora.strftime("%Y-%m-%d"), (ahora + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        if a.diagnostico:
            bks = [b for b in lista(op.get("bookmakers")) if isinstance(b, dict)]
            print(f"casas: {len(bks)} · de interés: " + "; ".join(json.dumps(b, ensure_ascii=False)[:150] for b in bks
                                                             if RX_CASAS.search(json.dumps(b, ensure_ascii=False)))[:3500])
            fx = nuestros(lista(op.get("fixtures", sportId=SPORT, **{"from": hoy, "to": (ahora + timedelta(days=4)).strftime("%Y-%m-%d")}, hasOdds="true")))
            print(f"partidos de nuestras 7 ligas en 4 días: {len(fx)}")
            if fx:
                nombres = nombres_participantes(op, [f.get("participant1Id") for f in fx], ahora)
                con_nombres(fx, nombres)
                f = fx[0]
                print(f"ejemplo: {f['_local']} - {f['_visitante']} {f.get('startTime')} (torneo {TORNEOS[f['tournamentId']]})")
                od = op.get("odds", fixtureId=fixture_id(f))  # sin filtro de casas: vemos qué slugs trae
                bo = od.get("bookmakerOdds", {}) if isinstance(od, dict) else {}
                print(f"casas con cuotas en ese partido: {len(bo)} · de interés: {[k for k in bo if RX_CASAS.search(k)]}")
                for slug in [k for k in bo if RX_CASAS.search(k)][:3]:
                    mk = (bo[slug] or {}).get("markets", {}) if isinstance(bo[slug], dict) else {}
                    print(f"  {slug}: {len(mk)} mercados · ids {list(mk)[:40]}")
                    print("  ejemplo: " + json.dumps(next(iter(mk.items()), None), ensure_ascii=False)[:400])
                os.makedirs(DIR, exist_ok=True)
                with gzip.open(os.path.join(DIR, f"diagnostico_{hoy}.json.gz"), "wt", encoding="utf-8") as fh:
                    json.dump({"fixture": f, "odds": od}, fh, ensure_ascii=False)
                print(f"respuesta completa guardada en datos/cuotas_oddspapi/diagnostico_{hoy}.json.gz")
            print(f"peticiones usadas este mes: {presu.d['usadas']}")
            return 0
        if a.propuestas:
            if not os.path.exists(PAPEL):
                return 0
            pend = [p for p in csv.DictReader(open(PAPEL, encoding="utf-8"))
                    if not p.get("resultado") and p.get("fecha") == hoy]
            partidos = {}
            for p in pend:
                partidos.setdefault(p["fixture_id"], p)
            if not partidos:
                return 0
            fx = nuestros(lista(op.get("fixtures", sportId=SPORT, **{"from": hoy, "to": manana}, hasOdds="true")))
            con_nombres(fx, nombres_participantes(op, [f.get("participant1Id") for f in fx], ahora))
            os.makedirs(DIR, exist_ok=True)
            hechos, sin = 0, []
            for fid_bwin, p in partidos.items():
                if presu.quedan() <= 0:
                    sin.append(f"{p['partido']} (sin presupuesto)"); continue
                loc, _, vis = p["partido"].partition(" - ")
                f = emparejar(fx, loc, vis, datetime.fromisoformat(p["inicio_utc"].replace("Z", "+00:00")))
                if not f:
                    sin.append(f"{p['partido']} (no emparejado)"); continue
                od = op.get("odds", fixtureId=fixture_id(f), **({"bookmakers": casas} if casas else {}))
                ruta = os.path.join(DIR, f"{hoy}_{str(fid_bwin).replace(':', '-')}.json.gz")
                with gzip.open(ruta, "wt", encoding="utf-8") as fh:
                    json.dump({"ts_utc": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "fixture_bwin": fid_bwin,
                               "partido": p["partido"], "fixture_oddspapi": f, "casas": casas, "odds": od}, fh, ensure_ascii=False)
                hechos += 1
            print(f"OddsPapi: {hechos}/{len(partidos)} partidos guardados · usadas este mes {presu.d['usadas']}"
                  + (f" · sin datos: {'; '.join(sin)}" if sin else ""))
            return 0
    except Exception as e:
        print(f"ERROR OddsPapi: {cb.sin_secretos(e, key)}"); return 2
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
