#!/usr/bin/env python3
"""Captura de cuotas de F1 en bwin.es (solo lectura, sin cuenta).

Lee la misma API JSON que usa la web (cds-api) y guarda una fila por
selección en datos/cuotas/AAAA-MM-DD_HHMM_<momento>.csv.

Uso:
  python3 bwin_snapshot.py --test            # conecta y resume, no escribe nada
  python3 bwin_snapshot.py --momento post_q  # captura y guarda CSV (+ JSON crudo local)

Requiere curl_cffi (Cloudflare da 403 a urllib). Poca frecuencia a propósito: unas pocas capturas por GP.
"""
import argparse, csv, gzip, json, os, statistics, sys, time
import urllib.parse, urllib.request
from datetime import datetime, timezone

BASE = "https://www.bwin.es/cds-api/bettingoffer"
# Identificador público de cliente que la web envía en cada petición (no es un secreto).
# Si bwin lo cambia, la API responde 401/403: sacarlo de nuevo de la web (parámetro x-bwin-accessid).
ACCESS_ID = os.environ.get("BWIN_ACCESS_ID", "OTdhMjU3MWQtYzI5Yi00NWQ5LWFmOGEtNmFhOTJjMWVhNmRl")
SPORT_F1 = "6"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
# Cloudflare devuelve 403 sin estas cabeceras de navegador (probado 25-sep-2026).
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://www.bwin.es/es/sports/f%C3%B3rmula-1-6",
    "Origin": "https://www.bwin.es",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "sec-ch-ua": '"Chromium";v="140", "Google Chrome";v="140"',
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-mobile": "?0",
}
DIR = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(DIR, "datos", "cuotas")
RAW_DIR = os.path.join(DIR, "datos", "raw")  # en .gitignore
PAUSA = 2.0  # segundos entre peticiones

CAMPOS = ["ts_utc", "momento", "competicion_id", "competicion", "fixture_id", "fixture",
          "inicio_utc", "mercado_id", "mercado", "template_id", "categoria",
          "seleccion_id", "seleccion", "cuota", "prob_implicita", "overround_mercado",
          "n_selecciones", "visible"]


def _get_urllib(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_cffi(url):
    # Plan B: imita la huella TLS de Chrome. Solo si está instalado (pip install curl_cffi).
    from curl_cffi import requests as cr
    r = cr.get(url, headers=HEADERS, impersonate="chrome", timeout=30)
    r.raise_for_status()
    return r.json()


_METODO = {"actual": None}  # recuerda qué método funcionó en esta ejecución


def _get(path, **params):
    q = {"x-bwin-accessid": ACCESS_ID, "lang": "es", "country": "ES", "userCountry": "ES", **params}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(q)}"
    metodos = [("curl_cffi", _get_cffi), ("urllib", _get_urllib)]
    if _METODO["actual"] == "urllib":
        metodos.reverse()
    errores = []
    for intento in range(2):
        for nombre, fn in metodos:
            try:
                j = fn(url)
                if _METODO["actual"] != nombre:
                    _METODO["actual"] = nombre
                    print(f"  (conexión vía {nombre})")
                return j
            except ImportError:
                continue
            except Exception as e:  # 403 de Cloudflare, red, JSON inválido...
                errores.append(f"{nombre}: {e}")
        time.sleep(5 * (intento + 1))
    raise RuntimeError(" | ".join(errores[-2:]))


def listar_fixtures():
    j = _get("fixtures", fixtureTypes="Standard", state="Latest", offerMapping="None",
             sortBy="StartDate", sportIds=SPORT_F1)
    return j.get("fixtures", [])


def vista_fixture(fid):
    return _get("fixture-view", fixtureIds=str(fid), offerMapping="All", state="Latest",
                firstMarketGroupOnly="false").get("fixture", {})


def _txt(x):
    return (x or {}).get("value", "") if isinstance(x, dict) else (x or "")


def filas_de_fixture(fx, ts, momento):
    """Convierte un fixture-view en filas planas (una por selección)."""
    filas = []
    comp = fx.get("competition") or {}
    for g in fx.get("games") or []:
        res = [r for r in (g.get("results") or []) if r.get("odds")]
        n = len(res)
        # overround solo tiene sentido si el mercado está completo (≥2 selecciones)
        ovr = round(sum(1 / r["odds"] for r in res), 4) if n >= 2 else ""
        for r in res:
            filas.append({
                "ts_utc": ts, "momento": momento,
                "competicion_id": comp.get("id", ""), "competicion": _txt(comp.get("name")),
                "fixture_id": fx.get("id", ""), "fixture": _txt(fx.get("name")),
                "inicio_utc": fx.get("startDate", ""),
                "mercado_id": g.get("id", ""), "mercado": _txt(g.get("name")),
                "template_id": g.get("templateId", ""), "categoria": g.get("category", ""),
                "seleccion_id": r.get("id", ""), "seleccion": _txt(r.get("name")),
                "cuota": r["odds"], "prob_implicita": round(1 / r["odds"], 4),
                "overround_mercado": ovr, "n_selecciones": n,
                "visible": 1 if r.get("visibility", "Visible") == "Visible" and g.get("visibility", "Visible") == "Visible" else 0,
            })
    return filas


def resumen(fx, filas):
    ovr = sorted({(f["mercado_id"], f["overround_mercado"]) for f in filas if f["overround_mercado"] != ""}, key=lambda x: x[1])
    vals = [o for _, o in ovr]
    med = f"{statistics.median(vals)*100:.0f}%" if vals else "-"
    return (f"  {fx.get('id')} | {_txt(fx.get('name'))} | inicio {fx.get('startDate')} | "
            f"mercados {len({f['mercado_id'] for f in filas})} | selecciones {len(filas)} | overround mediano {med}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="solo conecta y resume, no escribe")
    ap.add_argument("--momento", default="manual", help="etiqueta: pre_fp, post_fp, post_q, pre_carrera, manual...")
    a = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        fixtures = listar_fixtures()
    except Exception as e:
        print(f"ERROR conexión bwin: {e}")
        return 2
    abiertos = [f for f in fixtures if f.get("isOpenForBetting", True)]
    print(f"{ts} | fixtures F1: {len(fixtures)} (abiertos {len(abiertos)})")
    if not abiertos:
        print("Sin eventos abiertos. Nada que capturar.")
        return 0

    todas, crudos = [], []
    for f in abiertos:
        time.sleep(PAUSA)
        try:
            fx = vista_fixture(f["id"])
        except Exception as e:
            print(f"  {f.get('id')}: ERROR {e}")
            continue
        filas = filas_de_fixture(fx, ts, a.momento)
        print(resumen(fx, filas))
        todas += filas
        crudos.append(fx)

    if a.test:
        print(f"--test: {len(todas)} filas leídas, no se escribe nada.")
        return 0 if todas else 1

    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    base = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M") + f"_{a.momento}"
    ruta = os.path.join(CSV_DIR, base + ".csv")
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(todas)
    with gzip.open(os.path.join(RAW_DIR, base + ".json.gz"), "wt", encoding="utf-8") as fh:
        json.dump(crudos, fh, ensure_ascii=False)
    print(f"Guardado {ruta} ({len(todas)} filas)")
    return 0 if todas else 1


if __name__ == "__main__":
    sys.exit(main())
