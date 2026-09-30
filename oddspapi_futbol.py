#!/usr/bin/env python3
"""Cuotas de otras casas españolas vía OddsPapi (agregador; no toca las webs de las casas). Solo lectura.

Plan gratuito: 250 peticiones/mes → solo se consultan los partidos con propuestas del día, con presupuesto:
máx. ODDSPAPI_MAX_MES (230) al mes y ODDSPAPI_MAX_DIA (8) al día, contadas en datos/oddspapi_presupuesto.json.
Casas (slugs, máx. 3 por consulta): ODDSPAPI_CASAS, por defecto "bet365-es,codere-es,winamax-es".

Fase 1: guarda la respuesta cruda de cada partido en datos/cuotas_oddspapi/<fecha>_<fixture>.json.gz.
El parser de córners/tarjetas se escribe cuando veamos la estructura real (--diagnostico).

Uso:
  oddspapi_futbol.py --diagnostico       # ≈5 peticiones: casas .es, mercados de córners/tarjetas, estructura de un partido
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


def emparejar(fixtures, local, visit, ini):
    """Mejor fixture de OddsPapi para (local, visitante, hora): hora ±2 h y parecido de nombres ≥ 0,55 en ambos."""
    mejor, pmejor = None, 0
    for f in fixtures:
        t = inicio(f)
        if t and abs((t - ini).total_seconds()) > 7200:
            continue
        tx = [norm(s) for s in textos(f) if 2 < len(s) < 60]
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
    casas = cfg("ODDSPAPI_CASAS", "bet365-es,codere-es,winamax-es")
    hoy, manana = ahora.strftime("%Y-%m-%d"), (ahora + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        if a.diagnostico:
            bks = lista(op.get("bookmakers"))
            slugs = sorted({str(b.get("slug") or b.get("id") or b) for b in bks if isinstance(b, dict)} or {str(b) for b in bks})
            print(f"casas: {len(slugs)} · españolas: {[s for s in slugs if re.search(r'(^|-)es$|spain', s)]}")
            try:
                mk = lista(op.get("markets", sportId=SPORT))
                cor = [m for m in mk if re.search(r"corner|card|booking", json.dumps(m, ensure_ascii=False), re.I)]
                print(f"mercados de fútbol: {len(mk)} · de córners/tarjetas: {len(cor)}")
                for m in cor[:30]:
                    print("  ", json.dumps(m, ensure_ascii=False)[:160])
            except Exception as e:
                print(f"/markets no disponible: {cb.sin_secretos(e, key)}")
            try:  # ids de nuestras 7 ligas (para «odds by tournaments»: una liga entera por consulta)
                tn = lista(op.get("tournaments", sportId=SPORT))
                rx = re.compile(r"laliga|la liga|segunda|premier league|championship|serie a|bundesliga|ligue 1", re.I)
                print("torneos candidatos: " + "; ".join(json.dumps(t, ensure_ascii=False)[:140] for t in tn
                                                          if rx.search(json.dumps(t, ensure_ascii=False)))[:3000])
            except Exception as e:
                print(f"/tournaments no disponible: {cb.sin_secretos(e, key)}")
            fx = lista(op.get("fixtures", sportId=SPORT, **{"from": hoy, "to": manana}, hasOdds="true"))
            print(f"fixtures hoy-mañana: {len(fx)} · ejemplo: {json.dumps(fx[0], ensure_ascii=False)[:400] if fx else '—'}")
            if fx:
                fid = fixture_id(fx[0])
                od = op.get("odds", fixtureId=fid, bookmakers=casas)
                print(f"odds de {fid} ({casas}): claves {list(od)[:10] if isinstance(od, dict) else type(od).__name__}")
                print("  " + json.dumps(od, ensure_ascii=False)[:1500])
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
            fx = lista(op.get("fixtures", sportId=SPORT, **{"from": hoy, "to": manana}, hasOdds="true"))
            os.makedirs(DIR, exist_ok=True)
            hechos, sin = 0, []
            for fid_bwin, p in partidos.items():
                if presu.quedan() <= 0:
                    sin.append(f"{p['partido']} (sin presupuesto)"); continue
                loc, _, vis = p["partido"].partition(" - ")
                f = emparejar(fx, loc, vis, datetime.fromisoformat(p["inicio_utc"].replace("Z", "+00:00")))
                if not f:
                    sin.append(f"{p['partido']} (no emparejado)"); continue
                od = op.get("odds", fixtureId=fixture_id(f), bookmakers=casas)
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
