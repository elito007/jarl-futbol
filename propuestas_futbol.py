#!/usr/bin/env python3
"""Propuestas diarias de fútbol (tras la captura de la mañana) → Telegram. SOLO PAPEL por ahora.

Reglas fijas (PLAN.md, 29-sep-2026):
- Solo mercados de córners y tarjetas del modelo (goles no: el mercado nos gana).
- EV ≥ 10 %, prob ≥ 25 %, cuota ≤ 5; una selección por mercado (la de más EV); máx. 2 por partido y 12 al día.
- Solo partidos que empiezan en las próximas 24 h (la captura de mañana cubre el resto).
- Confianza: «media» en los mercados que el backtest fuera de muestra validó (más córners, ambos equipos
  N+ tarjetas); «baja» en el resto.
- Importe sugerido: banca viva (banca.py: real declarada o teórica; inicial 200 €), ¼ Kelly, tope 1 %/apuesta y 5 %/día; ×0,5 si la confianza es baja.
Se registran en papel/apuestas.csv y se liquidan con liquidar_futbol.py.
Uso: python3 propuestas_futbol.py --captura datos/cuotas/X.csv.gz [--no-registrar]
"""
import argparse, csv, gzip, os, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import banca as bk
import liquidar_futbol as lq
import modelo_futbol as mf

BASE = os.path.dirname(os.path.abspath(__file__))
PAPEL = os.path.join(BASE, "papel", "apuestas.csv")
EV_MIN, P_MIN, CUOTA_MAX, POR_PARTIDO, POR_DIA = 0.10, 0.25, 5.0, 2, 12
BANCA, KELLY, TOPE_AP, TOPE_DIA = 200.0, 0.25, 0.01, 0.05
CAMPOS = ["fecha", "liga", "fixture_id", "partido", "inicio_utc", "mercado", "seleccion", "cuota_tomada", "momento_cuota",
          "prob_modelo", "confianza", "importe_eur", "resultado", "cuota_cierre", "beneficio_u", "beneficio_eur", "fraccion"]
LIGA = {"SP1": "LaLiga", "SP2": "LaLiga 2", "E0": "Premier", "E1": "Championship", "I1": "Serie A", "D1": "Bundesliga", "F1": "Ligue 1"}


def hora_local(iso):
    try:
        from zoneinfo import ZoneInfo
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("Atlantic/Canary"))
        return f"{['lun','mar','mié','jue','vie','sáb','dom'][d.weekday()]} {d:%H:%M}"
    except Exception:
        return iso


def confianza(mercado):
    m = lq.norm(mercado)
    return "media" if m in ("mas corners",) or (m.startswith("ambos equipos") and "tarjetas" in m) else "baja"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captura", required=True); ap.add_argument("--no-registrar", action="store_true")
    ap.add_argument("--ahora")
    ap.add_argument("--reimprimir", action="store_true",
                    help="vuelve a mostrar las propuestas con la banca actual; no añade nuevas, actualiza el importe de las pendientes")
    a = ap.parse_args()
    ahora = datetime.fromisoformat(a.ahora.replace("Z", "+00:00")) if a.ahora else datetime.now(timezone.utc)
    rows = list(csv.DictReader(gzip.open(a.captura, "rt", encoding="utf-8")))
    modelo = mf.Modelo()
    mercados = defaultdict(list)
    for r in rows:
        ini = datetime.fromisoformat(r["inicio_utc"].replace("Z", "+00:00"))
        if ahora < ini <= ahora + timedelta(hours=24):
            mercados[(r["fixture_id"], r["mercado_id"])].append(r)
    cand = []
    for (fid, _), rs in mercados.items():
        mejor = None
        for r in rs:
            c = float(r["cuota"])
            if c > CUOTA_MAX:
                continue
            p = modelo.prob(r["liga"], r["local"], r["visitante"], r["mercado"], r["seleccion"])
            if p is None or p < P_MIN:
                continue
            ev = p * c - 1
            if ev >= EV_MIN and (mejor is None or ev > mejor[1]):
                mejor = (r, ev, p)
        if mejor:
            cand.append(mejor)
    # apuestas equivalentes (mismo suceso en mercados distintos de bwin) → UNA sola apuesta, a la mejor cuota,
    # con Kelly una vez (no dos veces sobre el mismo resultado) y anotando las alternativas para el mensaje
    grupos = defaultdict(list)
    for r, ev, p in cand:
        grupos[(r["fixture_id"], mf.Modelo.evento(r["local"], r["visitante"], r["mercado"], r["seleccion"]))].append((r, ev, p))
    cand, alternativas = [], {}
    for g in grupos.values():
        g.sort(key=lambda x: (-float(x[0]["cuota"]), len(x[0]["mercado"])))
        cand.append(g[0])
        alternativas[id(g[0][0])] = [f"{x[0]['mercado']} «{x[0]['seleccion']}» @ {x[0]['cuota']}" for x in g[1:]]
    cand.sort(key=lambda x: -x[1])
    por_partido, elegidas = defaultdict(int), []
    for r, ev, p in cand:
        if por_partido[r["fixture_id"]] < POR_PARTIDO and len(elegidas) < POR_DIA:
            por_partido[r["fixture_id"]] += 1; elegidas.append((r, ev, p))
    # importes
    props = []
    for r, ev, p in elegidas:
        c = float(r["cuota"]); conf = confianza(r["mercado"])
        f = min(KELLY * (p * c - 1) / (c - 1), TOPE_AP) * (1.0 if conf == "media" else 0.5)
        props.append({"r": r, "ev": ev, "p": p, "conf": conf, "f": f, "alt": alternativas.get(id(r), [])})
    props.sort(key=lambda x: x["r"]["inicio_utc"])  # mismo orden en que se muestran (y se apuestan)
    t = sum(x["f"] for x in props)
    banca, etiqueta = bk.para_importes()
    real, teor = bk.bases()
    for x, f in zip(props, bk.secuencial([x["f"] * (TOPE_DIA / t if t > TOPE_DIA else 1) for x in props])):
        x["f"] = f
        x["eur"] = round(banca * f, 1)
        x["eur_t"] = round(teor * f, 1) if real is not None else None
    # registrar
    if props and a.reimprimir and os.path.exists(PAPEL):
        prev = list(csv.DictReader(open(PAPEL, encoding="utf-8")))
        imp = {(x["r"]["fixture_id"], x["r"]["mercado"], x["r"]["seleccion"]): x["eur"] for x in props}
        for e in prev:
            k = (e["fixture_id"], e["mercado"], e["seleccion"])
            if k in imp and not e.get("resultado"):
                e["importe_eur"] = imp[k]
        with open(PAPEL, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=CAMPOS, restval="", extrasaction="ignore"); w.writeheader(); w.writerows(prev)
    elif props and not a.no_registrar:
        os.makedirs(os.path.dirname(PAPEL), exist_ok=True)
        prev = list(csv.DictReader(open(PAPEL, encoding="utf-8"))) if os.path.exists(PAPEL) else []
        ya = {(e["fixture_id"], e["mercado"], e["seleccion"]) for e in prev}
        for x in props:
            r = x["r"]
            if (r["fixture_id"], r["mercado"], r["seleccion"]) in ya:
                continue
            prev.append({"fecha": r["ts_utc"][:10], "liga": r["liga"], "fixture_id": r["fixture_id"],
                         "partido": f"{r['local']} - {r['visitante']}", "inicio_utc": r["inicio_utc"], "mercado": r["mercado"],
                         "seleccion": r["seleccion"], "cuota_tomada": r["cuota"], "momento_cuota": r["momento"],
                         "prob_modelo": round(x["p"], 3), "confianza": x["conf"], "importe_eur": x["eur"],
                         "fraccion": round(x["f"], 5)})
        with open(PAPEL, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=CAMPOS, restval=""); w.writeheader(); w.writerows(prev)
    # texto
    if not props:
        print("⚽ Propuestas de hoy: ninguna supera el umbral. 📝 SOLO PAPEL"); return 0
    lin = [("🔁 RECALCULADAS · " if a.reimprimir else "") + f"⚽ Propuestas de hoy — 📝 SOLO PAPEL ({len(props)}, total sugerido {sum(x['eur'] for x in props):.1f} € sobre banca {etiqueta})"]
    partido_ant = None
    for x in props:  # ya ordenadas por hora (mismo orden que los importes)
        r = x["r"]; pb = float(r["prob_implicita"]) / (float(r["overround_mercado"]) if r["overround_mercado"] else 1)
        partido = (r["fixture_id"], r["inicio_utc"])
        if partido != partido_ant:
            lin.append(f"\n🕒 {hora_local(r['inicio_utc'])} · {LIGA.get(r['liga'], r['liga'])} · {r['local']} - {r['visitante']}")
            partido_ant = partido
        teo = f" (teór. {x['eur_t']:.1f} €)" if x.get("eur_t") is not None else ""
        lin.append(f"🎯 {r['mercado']}")
        lin.append(f"   ➜ «{r['seleccion']}» @ {r['cuota']} · {x['eur']:.1f} €{teo}")
        lin.append(f"   nuestra {x['p']*100:.0f} % vs bwin {pb*100:.0f} % · confianza {x['conf']}")
        for alt in x.get("alt", []):
            lin.append(f"   ≡ misma apuesta en: {alt}")
    print("\n".join(lin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
