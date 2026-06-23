# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors
#
# Actualizacion automatica de fuentes (re-ingesta + re-procesado).
# NO corre solo: se activa con  docker compose --profile refresh up -d
# y se controla 100% desde .env (NO hace falta tocar este archivo):
#
#   REFRESH=off|daily|weekly   apagado / cada dia / cada domingo   (default: off)
#   REFRESH_HOUR=3             hora del contenedor 0-23, sin cero a la izquierda
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

if [ "$MODE" = "off" ]; then
  echo "refresh: REFRESH=off — desactivado. Pon REFRESH=daily o weekly en .env para activar."
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
