# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors
#
# Actualizacion automatica de fuentes (re-ingesta + re-procesado).
# NO corre solo: se activa con  docker compose --profile refresh up -d
# y se controla 100% desde .env (NO hace falta tocar este archivo):
#
#   REFRESH=off|daily|weekly|every   apagado / cada dia / cada domingo / cada N horas (default: off)
#   REFRESH_HOUR=3             solo daily/weekly: hora del contenedor 0-23
#   REFRESH_EVERY_HOURS=8      solo modo "every": cada cuantas horas correr
#   REFRESH_SOURCES=all        "all" = todas las fuentes, o "tala,zapopan"
#   REFRESH_LIMIT=50           docs maximos a fetchear por fuente y corrida
#   TZ=America/Mexico_City     opcional: usar hora local (por defecto UTC)
#
# Es seguro re-correrlo seguido: 'ingest' salta lo que no cambio (compara
# SHA-256) y 'process' solo toca documentos nuevos. Un doc actualizado entra
# como version nueva y la busqueda solo muestra la vigente.
set -u

MODE="${REFRESH:-off}"
SOURCES="${REFRESH_SOURCES:-all}"
LIMIT="${REFRESH_LIMIT:-50}"
# Normaliza la hora: quita ceros a la izquierda ("03" -> "3") para comparar como numero.
HOUR=$(echo "${REFRESH_HOUR:-3}" | sed 's/^0*//'); HOUR=${HOUR:-0}
EVERY_HOURS=$(echo "${REFRESH_EVERY_HOURS:-8}" | sed 's/^0*//'); EVERY_HOURS=${EVERY_HOURS:-8}

if [ "$MODE" = "off" ]; then
  echo "refresh: REFRESH=off — desactivado. Pon REFRESH=daily, weekly o every en .env para activar."
  # Quedarse vivo sin trabajar evita que el contenedor entre en restart-loop.
  while true; do sleep 86400; done
fi

run_once() {
  echo "refresh: START sources=$SOURCES limit=$LIMIT $(date -u +%FT%TZ)"
  if [ "$SOURCES" = "all" ]; then
    slugs=$(uv run python -c "from open_data_jalisco.ingestion import iter_source_configs; [print(c.slug) for c in iter_source_configs()]")
  else
    slugs=$(echo "$SOURCES" | tr ',' ' ')
  fi
  for slug in $slugs; do
    [ -n "$slug" ] || continue
    echo "refresh: ingest $slug"
    uv run odj ingest "$slug" --limit "$LIMIT" || echo "refresh: ingest $slug FALLO (continuo con el resto)"
  done
  echo "refresh: process"
  uv run odj process || echo "refresh: process FALLO"
  echo "refresh: DONE $(date -u +%FT%TZ)"
}

# Modo intervalo: corre al arrancar y luego cada N horas. Simple y predecible;
# no depende del reloj de pared ni de zona horaria.
if [ "$MODE" = "every" ]; then
  echo "refresh: activo MODE=every cada ${EVERY_HOURS}h SOURCES=$SOURCES"
  while true; do
    run_once
    sleep "$((EVERY_HOURS * 3600))"
  done
fi

echo "refresh: activo MODE=$MODE HOUR=$HOUR SOURCES=$SOURCES (revisa cada 30 min)"
# ponytail: poll cada 30 min y dispara cuando la hora coincide (1 vez/dia via
# last_run). Simple y a prueba de drift de reloj; si hiciera falta precision al
# minuto o varios horarios, cambiar a un cron real (p.ej. supercronic) sin tocar
# compose ni este contrato de variables.
last_run=""
while true; do
  now_h=$(date +%-H)     # hora actual sin cero a la izquierda (GNU date)
  now_dow=$(date +%u)    # 1=lunes .. 7=domingo
  today=$(date +%F)
  due=0
  if [ "$now_h" -eq "$HOUR" ] 2>/dev/null; then
    [ "$MODE" = "daily" ] && due=1
    [ "$MODE" = "weekly" ] && [ "$now_dow" = "7" ] && due=1   # domingo
  fi
  if [ "$due" = "1" ] && [ "$today" != "$last_run" ]; then
    run_once
    last_run="$today"
  fi
  sleep 1800
done
