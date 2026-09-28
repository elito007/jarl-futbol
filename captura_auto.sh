#!/usr/bin/env bash
# Cron horario (sin LLM). Telegram recibe cualquier salida no vacía: propuestas diarias, informe semanal y fallos.
set -uo pipefail
cd /opt/data/futbol || exit 2

# git pull con reintentos: un fallo puntual de red no merece aviso
ok=0
for i in 1 2 3; do
  if git pull -q --no-edit 2>/tmp/futbol_pull.err; then ok=1; break; fi
  sleep 30
done
if [ $ok -ne 1 ]; then
  echo "aviso: git pull falló 3 veces ($(tail -1 /tmp/futbol_pull.err)). Sigo con la versión local."
fi

.venv/bin/python captura_auto.py
rc=$?

# todo lo que generan los scripts (capturas, liquidaciones, informe, papel)
git add datos/ analisis/ papel/ >/dev/null 2>&1
if ! git diff --cached --quiet; then
  git commit -q -m "auto: capturas/liquidación $(date -u +%Y-%m-%d_%H%M)" && git push -q || { echo "FALLO git push"; rc=1; }
fi
exit $rc
