"""Utilidades comunes para otras casas (Betfair Exchange ES, OddsPapi).

Credenciales en un fichero aparte, fuera de git: /opt/data/futbol/.env.casas (ruta cambiable con ENV_CASAS).
Lo crea Elito a mano: chmod 600 y propietario hermes:hermes (el usuario con el que corre Jarl dentro del Docker;
si queda como root:root, los scripts dan PermissionError). Jarl nunca lo lee ni lo imprime; los scripts solo lo cargan.
  BETFAIR_APP_KEY=...        # clave de aplicación (vale la «delayed», gratuita)
  BETFAIR_USER=...
  BETFAIR_PASS=...
  ODDSPAPI_KEY=...
Si falta una clave, el script correspondiente sale con código 3 y la línea 'SIN CREDENCIALES' (el planificador lo ignora).
"""
import json, os, urllib.error, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
ENV_CASAS = os.environ.get("ENV_CASAS", os.path.join(BASE, ".env.casas"))
SIN_CRED = 3


def credenciales(*claves):
    """Devuelve {clave: valor} desde el entorno o .env.casas; None si falta alguna. Nunca imprime valores."""
    vals = {}
    if os.path.exists(ENV_CASAS):
        for l in open(ENV_CASAS, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#") and "=" in l:
                k, v = l.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    out = {k: os.environ.get(k) or vals.get(k) for k in claves}
    return out if all(out.values()) else None


def http_json(url, datos=None, cabeceras=None, form=False, timeout=40):
    """GET (datos=None) o POST (JSON, o formulario si form=True). Devuelve el JSON decodificado."""
    cab = {"Accept": "application/json", "User-Agent": "jarl-futbol/1.0"}
    cab.update(cabeceras or {})
    cuerpo = None
    if datos is not None:
        if form:
            cuerpo = urllib.parse.urlencode(datos).encode()
            cab["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            cuerpo = json.dumps(datos).encode()
            cab["Content-Type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab), timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:  # el cuerpo suele decir el motivo (parámetro inválido, etc.)
        detalle = e.read().decode(errors="replace")[:300] if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {detalle}") from None


def sin_secretos(texto, *secretos):
    """Quita claves y contraseñas de un mensaje de error antes de imprimirlo."""
    texto = str(texto)
    for s in secretos:
        if s and len(s) >= 4:
            texto = texto.replace(s, "***")
    return texto
