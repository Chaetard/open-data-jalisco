# Open Data Jalisco

> Información pública, verificable y consultable para una ciudadanía más informada.

🌐 Sitio oficial: <https://odj.n0kemm.dev/> · 💻 Código fuente: <https://github.com/Chaetard/open-data-jalisco>

**Open Data Jalisco** es una iniciativa ciudadana, técnica, apartidista y open source para recopilar, preservar, organizar, consultar y verificar información pública municipal del estado de Jalisco, México.

El primer piloto territorial es **Tala, Jalisco**.

📜 Manifiesto completo del proyecto: [**docs/MANIFEST.md**](docs/MANIFEST.md)

---

## ¿Qué es?

La información pública existe para ser consultada, reutilizada y entendida por la ciudadanía. En la práctica, muchos documentos públicos viven dispersos en portales distintos, formatos difíciles, archivos PDF, hojas de cálculo, páginas poco indexadas, enlaces rotos y estructuras inconsistentes.

Open Data Jalisco nace para reducir esa fricción: construir una capa abierta de consulta documental sobre información pública municipal, manteniendo siempre trazabilidad hacia las fuentes oficiales.

La visión es que una persona pueda preguntar:

> "¿Qué contratos públicos relacionados con obra hubo en Tala durante 2021?"

Y el sistema pueda responder con documentos, fechas, fuentes, enlaces oficiales, fragmentos relevantes y evidencia verificable.

El objetivo **no** es sustituir a las autoridades, ni emitir acusaciones, ni interpretar políticamente la información pública. El objetivo es construir infraestructura abierta para que cualquier persona pueda consultar documentos públicos, entenderlos mejor y participar de forma más informada.

---

## Principios

1. **Neutralidad política.** Apartidista. El sistema no asume corrupción, dolo o mala fe. Cuando detecta inconsistencias documentales las describe; no las convierte en acusaciones.
2. **Trazabilidad documental.** La fuente de verdad no es la IA ni la base vectorial: son los documentos originales, sus URLs oficiales, fechas de captura, hashes y manifests.
3. **Integridad y preservación.** Los documentos capturados no se modifican. Si la fuente oficial cambia un documento, se guarda una nueva versión con nuevo hash — nunca se sobrescribe la anterior.
4. **Transparencia técnica.** Código abierto. Scrapers, pipelines, extractores, manifests y criterios de contribución son públicamente auditables.
5. **Acceso público y gratuito.** Sujeto a límites operativos razonables (rate limits, API keys técnicas) sin convertirse en barrera comercial.
6. **Protección de datos personales.** Que un documento sea público no significa amplificar innecesariamente datos personales. Aplican criterios de minimización, contexto y responsabilidad.

Cada principio está desarrollado en detalle en el [manifiesto §3](docs/MANIFEST.md).

---

## Qué NO es

Open Data Jalisco **no es**:

- una autoridad fiscalizadora, una auditoría oficial, una fiscalía ni un tribunal;
- una herramienta de propaganda o partidista;
- una plataforma para acusar personas;
- una sustitución de solicitudes formales de transparencia ni de las fuentes oficiales;
- una garantía de completitud absoluta;
- un sistema para publicar datos personales fuera de contexto;
- una prueba automática de irregularidades.

> La ausencia de un documento en la base no significa necesariamente que el documento no exista.
> Una inconsistencia detectada por el sistema no significa necesariamente una irregularidad legal.

El sistema puede ayudar a encontrar documentos, comparar información, detectar faltantes y señalar inconsistencias documentales. No debe convertir esas señales en conclusiones jurídicas, penales, administrativas o políticas.

---

## ¿Para quién?

El proyecto está pensado como infraestructura útil para:

- **ciudadanía** interesada en información pública municipal;
- **estudiantes** y proyectos académicos;
- **periodistas e investigadores**;
- **organizaciones civiles**;
- **desarrolladores y contribuidores** open source;
- **servidores públicos y áreas de transparencia** que quieran reutilizar o auditar sus propios datos.

La relación deseada con autoridades no es de confrontación automática, sino de consulta, verificación y mejora del acceso a información pública.

---

## Alcance actual

- **Territorial**: Tala, Jalisco (piloto). Diseñado para crecer hacia otros municipios del estado.
- **Documental**: contratos, licitaciones, adjudicaciones, compras y obra pública, reglamentos, actas, presupuestos, leyes de ingresos y egresos, transparencia activa, directorios institucionales, gacetas y portales oficiales municipales.

Nuevas fuentes se incorporan mediante configuración versionada (YAML), no por modificación del código de producción. Esto mantiene la incorporación auditable y replicable.

---

## Estado del proyecto

Etapa temprana. MVP funcional con:

- ingesta de documentos públicos vía scrapers configurables (`generic_http`, `sapumu_content`);
- descubrimiento conservador de páginas SAPUMU (`sapumu scan`) sin descargar documentos;
- inspección offline de candidatos descubiertos (`discovered inspect`);
- ingesta controlada desde candidatos con filtros y bloqueo de categorías sensibles (`discovered ingest`);
- preservación con hash SHA-256 y versionado por URL;
- extracción de texto + chunking + embeddings (provider `dummy` por defecto, sin API key);
- búsqueda semántica vía pgvector;
- manifests de integridad reproducibles;
- API HTTP + CLI.

Lo que aún no está expuesto al consumidor: descarga de blobs originales desde la API (se usa el `official_url` de la fuente), autenticación, panel de auditoría visual, OCR.

---

## Inteligencia artificial: principio de operación

Cuando exista una interfaz conversacional o asistida por IA, operará bajo un principio estricto:

> El asistente no debe responder afirmaciones sustantivas sin respaldo documental recuperado.

El asistente podrá explicar documentos, resumir contratos, comparar fuentes, señalar inconsistencias documentales e indicar qué evidencia encontró o no encontró. No podrá inventar fuentes, asumir corrupción, acusar personas, inferir delitos, presentar texto generado como documento oficial ni sustituir asesoría legal o auditoría formal.

La IA es **interfaz de consulta asistida, no autoridad factual**. Detalle en [manifiesto §7](docs/MANIFEST.md).

---

## Open source

El software se publica bajo la licencia **GNU Affero General Public License v3.0 o posterior (AGPL-3.0-or-later)**. El texto completo está en el archivo [`LICENSE`](LICENSE) de este repositorio.

La elección de AGPLv3 mantiene el proyecto abierto incluso cuando se ofrezca como servicio web: si una persona u organización modifica el software y lo publica como servicio, deberá publicar también sus modificaciones bajo los mismos términos.

### Aviso de uso en red (AGPLv3 §13)

Cuando este software se opera como servicio accesible por red, la AGPLv3 requiere que las personas usuarias puedan obtener el código fuente correspondiente a la versión en ejecución, incluidas modificaciones. El código fuente oficial está disponible en el repositorio del proyecto: <https://github.com/Chaetard/open-data-jalisco>. Adicionalmente, toda instancia expone el endpoint `GET /source`, que devuelve la URL del repositorio, la versión publicada y, si está configurado, el commit en ejecución. Cualquier operador de una instancia modificada debe ofrecer públicamente el código fuente de su versión bajo los mismos términos de la AGPLv3.

### Documentos oficiales recopilados

Los documentos oficiales recopilados **no son propiedad del proyecto**. Open Data Jalisco no se atribuye autoría sobre documentos gubernamentales, reglamentos, actas, contratos, licitaciones o archivos emitidos por autoridades públicas. El proyecto los **preserva, referencia, procesa e indexa** con fines de consulta, trazabilidad, investigación, participación ciudadana y reutilización técnica.

---

## Contribuir

Se aceptan contribuciones por pull requests, issues, reportes, documentación, mejoras técnicas, nuevos scrapers, validaciones de fuentes y pruebas.

**Contribuciones bienvenidas**:

- nuevas configuraciones de municipios (YAML en `datasets/sources/`);
- mejoras en scrapers, parsers y extractores de texto;
- chunking semántico;
- tests y validaciones de integridad;
- documentación y accesibilidad;
- mejoras de seguridad.

**No aceptables**:

- insertar documentos no verificables como si fueran oficiales;
- modificar hashes históricos o alterar documentos raw;
- eliminar evidencia sin justificación;
- agregar inferencias políticas como metadata factual;
- exponer datos personales fuera de contexto;
- romper la trazabilidad hacia las fuentes oficiales.

Las contribuciones no tienen acceso directo a la base oficial de producción. Detalle completo en [manifiesto §10](docs/MANIFEST.md).

---

## Sostenibilidad

El proyecto podrá aceptar donaciones voluntarias para cubrir costos técnicos (infraestructura, almacenamiento, dominios, procesamiento documental, OCR, bases de datos, monitoreo, mantenimiento, seguridad). Las donaciones, si existen, no comprometerán la neutralidad del proyecto ni convertirán el sistema en una herramienta partidista.

---

## Documentación

| Documento | Contenido |
|---|---|
| 📜 [docs/MANIFEST.md](docs/MANIFEST.md) | Manifiesto completo: propósito, principios, gobernanza, alcance, IA, contribuciones, sostenibilidad. |
| 🔌 [docs/API.md](docs/API.md) | Referencia completa de la API pública: cada endpoint, parámetros, esquemas, errores y ejemplos curl. |
| 🖥️ [docs/FRONTEND_GUIDE.md](docs/FRONTEND_GUIDE.md) | Guía de integración frontend: endpoints, ejemplos JSON, flujos de prueba. |
| 🧪 `--help` en CLI | Cada comando documenta sus opciones: `uv run open-data-jalisco --help`, `... sapumu --help`, `... discovered --help`. |

---

## Frase guía

> Open Data Jalisco no busca reemplazar a las instituciones. Busca que la información pública sea más accesible, más trazable y más útil para la sociedad.

---
---

# Sección técnica

Lo necesario para correr el MVP local. Esta sección está al final intencionalmente: la prioridad del README es el propósito del proyecto.

## Stack

- Python 3.12 + FastAPI + Typer
- SQLAlchemy 2 + psycopg + PostgreSQL con pgvector
- `uv` para gestión de dependencias
- pytest para tests
- Arquitectura hexagonal: `domain/`, `ports/`, `adapters/`, más una capa fina de `api/` y `cli.py`

## Estructura

```
open-data-jalisco/
  apps/api/main.py              # entrypoint para uvicorn
  src/open_data_jalisco/
    domain/                     # dataclasses: Source, Document, Chunk, enums
    ports/                      # protocols (Repository, EmbeddingProvider, ...)
    adapters/                   # implementaciones: postgres, fs local, embedder dummy, scrapers
    api/                        # FastAPI app, routers, schemas, deps
    discovery/                  # sapumu scan + candidates inspect + candidates ingest
    ingestion/                  # loader de YAML, use case de ingesta
    processing/                 # extracción + chunking + embedding
    manifests/                  # generador de manifests de integridad
    shared/                     # config, logging, hashing, time
    cli.py                      # CLI `odj` / `open-data-jalisco`
  configs/                      # plantillas YAML (sin URLs reales)
  datasets/
    sources/                    # configs de fuentes activas (YAML)
    discovered/                 # candidatos descubiertos por sapumu scan
    manifests/                  # manifests generados (JSON)
  docs/                         # manifiesto + guía frontend
  infra/postgres/init.sql       # pgvector + bootstrap del schema
  tests/unit/                   # sin DB, sin red
  tests/integration/            # ejercitan API + DB
  web/                          # SPA del portal (Vite + React)
    Dockerfile                  # build estático + Caddy (sirve SPA y proxy /api)
    Caddyfile
  Dockerfile                    # imagen de la API
  docker-compose.yml            # stack completo: postgres + api + web
```

> Monorepo: el backend vive en la raíz y el frontend en `web/`. El SPA llama al
> backend por la ruta relativa `/api`, que Caddy enruta al contenedor `api` — así
> el front no necesita configurarse: mismo origen, sin CORS, sin URLs hardcodeadas.

## Despliegue (Docker — todo en uno)

La forma más simple de correr la plataforma completa (base de datos, API y portal)
en cualquier máquina. Sólo necesitas Docker; **no** instalas Python, Node ni `uv`,
y **no** tocas nada del frontend: sólo editas variables.

```bash
git clone https://github.com/Chaetard/open-data-jalisco
cd open-data-jalisco
cp .env.example .env        # edita POSTGRES_PASSWORD, SITE_ADDRESS, LLM_API_KEY…
docker compose up -d --build
```

Listo. El portal queda en <http://localhost> y la API detrás de `/api`
(p.ej. <http://localhost/api/health>). En el primer arranque la API crea el
schema automáticamente.

| Variable | Para qué |
|---|---|
| `POSTGRES_PASSWORD` | Contraseña de Postgres (cámbiala en producción). |
| `SITE_ADDRESS` | `http://localhost` (HTTP) o un dominio real → **HTTPS automático** (Let's Encrypt). |
| `HTTP_PORT` / `HTTPS_PORT` | Puertos públicos del portal (default 80 / 443). |
| `LLM_API_KEY` | Activa el agente de respuestas `POST /ask` (opcional; sin ella, el resto funciona igual). |
| `EMBEDDING_PROVIDER` | `dummy` (default, sin descargas) o `local_st` para búsqueda semántica real. |

Comandos equivalentes vía `make up` / `make down` / `make logs`.

> Para servir en un dominio con HTTPS, apunta el DNS a la máquina y pon
> `SITE_ADDRESS=tu-dominio.com`. Caddy emite y renueva el certificado solo.

## Setup (desarrollo)

Para trabajar en el código (hot-reload, tests, CLI) sin contenedores.
El proyecto fija Python **3.12** vía `.python-version`. No uses tu Python del sistema — deja que `uv` provisione el intérprete.

### Linux / macOS

```bash
cp .env.example .env
uv python install 3.12
uv venv --python 3.12
uv sync --extra dev
make db-up                       # Postgres + pgvector
make init-db                     # crear schema (idempotente)
```

### Windows (PowerShell)

```powershell
Copy-Item .env.example .env
uv python install 3.12
uv venv --python 3.12
uv sync --extra dev
# o todo en uno:
.\scripts\bootstrap.ps1

docker compose up -d postgres
uv run open-data-jalisco db init
```

> En Windows usa siempre `uv run ...`. Ejecutar `python -m pytest` directamente toma el Python del sistema (típicamente 3.13) en vez del `.venv` del proyecto (3.12) y rompe imports.

El CLI está registrado bajo dos nombres equivalentes:

```bash
uv run open-data-jalisco --help              # preferido
uv run python -m open_data_jalisco.cli --help # equivalente
uv run odj --help                             # alias corto
```

## API

```bash
make api          # uvicorn apps.api.main:app --reload
```

Endpoints expuestos:

| Método | Ruta | Notas |
|---|---|---|
| GET | `/health` | Liveness + versión |
| GET | `/sources` | Lista de fuentes |
| GET | `/sources/{slug}` | Detalle de una fuente |
| GET | `/documents` | Lista filtrable (source_id, municipality, year) |
| GET | `/documents/{id}` | Detalle de un documento |
| GET | `/documents/{id}/chunks` | Chunks de texto extraídos |
| POST | `/search` | Búsqueda semántica (preferido) |
| GET | `/search?q=...` | Alias GET para deep-links |
| POST | `/semantic-search` | Alias explícito de POST /search |
| GET | `/manifests` | Lista manifests en disco |

Documentación interactiva en `GET /docs` (Swagger) y `GET /redoc`. Referencia completa de cada endpoint (parámetros, esquemas, errores, ejemplos curl): [**docs/API.md**](docs/API.md). Integración frontend: [**docs/FRONTEND_GUIDE.md**](docs/FRONTEND_GUIDE.md).

## CLI — flujos principales

```bash
# Listar fuentes definidas en datasets/sources/*.yaml
uv run open-data-jalisco sources list

# 1) Descubrir páginas SAPUMU (sin descargar nada)
uv run open-data-jalisco sapumu scan tala \
    --section articulo_8 --from-id 1 --to-id 100 \
    --output datasets/discovered/tala/articulo_8_candidates.json

# 2) Inspeccionar candidatos descubiertos (offline)
uv run open-data-jalisco discovered inspect \
    datasets/discovered/tala/articulo_8_candidates.json \
    --year 2025 --extension pdf

# 3) Ingesta controlada desde candidatos
uv run open-data-jalisco discovered ingest \
    datasets/discovered/tala/articulo_8_candidates.json \
    --source tala --content-id 63 --year 2025 --extension pdf \
    --limit 10 --dry-run

# Ingesta clásica de una fuente completa
uv run open-data-jalisco ingest tala --limit 5 --dry-run
uv run open-data-jalisco ingest tala --limit 5

# Procesar documentos pendientes (extraer texto + chunkear + embeber)
uv run open-data-jalisco process --limit 50

# Generar manifest de integridad (datasets/manifests/<slug>_*.json)
uv run open-data-jalisco manifest tala
```

Cada comando documenta sus opciones con `--help`. Conviene leer al menos `sapumu scan --help`, `discovered inspect --help`, `discovered ingest --help` antes de la primera corrida real.

## Tests

```bash
make test                # suite completa
make test-unit           # sin DB, sin red
make test-integration    # requiere Postgres arriba
```

Los tests unitarios usan `dependency_overrides` de FastAPI con repositorios y embedder fake — nunca tocan red ni base de datos.

## Configuración

Toda la configuración runtime es via `.env` (gestionada por `pydantic-settings`). Variables relevantes:

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://odj:odj@localhost:5432/open_data_jalisco` |
| `RAW_STORAGE_PATH` | `./data/raw` |
| `MANIFESTS_DIR` | `./datasets/manifests` |
| `EMBEDDING_PROVIDER` | `dummy` (determinístico, sin API) — alternativa: `local_st` |
| `EMBEDDING_MODEL` | `dummy-v1` — para `local_st`: `intfloat/multilingual-e5-small` |
| `EMBEDDING_DIMENSION` | `384` |
| `EMBEDDING_DEVICE` | `cpu` (sólo aplica a `local_st`; usa `cuda` si hay GPU disponible) |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` |

`EMBEDDING_PROVIDER=dummy` produce vectores determinísticos desde el hash del texto — sin API keys, sin red, **sin semántica real**. Útil para tests, inútil para búsqueda. Para una demo funcional usa `local_st` (siguiente sección).

## Demo local con embedder real

El proveedor `local_st` ejecuta [`sentence-transformers`](https://www.sbert.net/) en CPU (o CUDA) sin red y sin API keys una vez bajado el modelo. El default `intfloat/multilingual-e5-small` es multilingüe, ~470 MB y de 384 dimensiones — coincide con el schema `vector(384)` de pgvector, así que **no hace falta migración**.

```bash
# 1) Instalar el extra (~700 MB con torch). Sólo la primera vez.
uv sync --extra local-embed

# 2) Editar .env
#    EMBEDDING_PROVIDER=local_st
#    EMBEDDING_MODEL=intfloat/multilingual-e5-small
#    EMBEDDING_DIMENSION=384
#    EMBEDDING_DEVICE=cpu

# 3) Si ya habías procesado documentos con `dummy`, sus chunks quedaron con
#    embeddings determinísticos inservibles. Borralos antes de re-indexar:
uv run open-data-jalisco db reset-chunks      # (o: psql … "TRUNCATE chunks;")

# 4) Ingestar 200 documentos de los candidatos ya descubiertos para Tala
#    (el bloqueo de declaraciones patrimoniales cid=92 es automático)
uv run open-data-jalisco discovered ingest \
    datasets/discovered/tala/articulo_8_candidates_1_500.json \
    --source tala --extension pdf --limit 200

# 5) Procesar (extraer + chunkear + embeber). La primera corrida descarga
#    el modelo a ~/.cache/huggingface y tarda más; las siguientes son rápidas.
uv run open-data-jalisco process --limit 200

# 6) Probar la búsqueda
uv run open-data-jalisco search "contrato sapumu"
uv run open-data-jalisco search "adjudicación directa 2025"
uv run open-data-jalisco search "ley datos personales"

# 7) Levantar la API para el frontend
make api    # uvicorn apps.api.main:app --reload
```

El input al embedder antepone el título del documento a cada chunk — así, aunque el cuerpo de un PDF no mencione la entidad buscada (p. ej. "SAPUMU"), si aparece en el título el chunk hace match.

## Notas técnicas adicionales

- **Extractores soportados**: PDF (`pypdf`, los escaneados sin capa de texto van a `needs_ocr`), XLSX/XLSM (`openpyxl` read-only, una página por hoja no vacía), HTML (`trafilatura` + `beautifulsoup4`), plaintext/CSV/Markdown vía stdlib.
- **Inferencia de año/mes**: cuando el YAML no provee `year`, se infiere de URLs con forma `/<...>/YYYY/MM/<...>`. El valor aterriza en `Document.year` y `Document.metadata` (`inferred_month`, `year_inferred_from_url`).
- **Scrapers**: `generic_http` cubre portales con `direct_documents` + descubrimiento superficial sobre `seed_urls`; `sapumu_content` cubre portales SAPUMU parseando el JSON embebido en `<level-content :content="...">`. Ambos comparten allow-lists, deduplicación y semántica de `--limit`.
- **Plantillas en `configs/`**: contienen URLs placeholder. Si una URL conserva fragmentos como `example.invalid`, `REEMPLAZAR` o `<replace>`, la ingesta falla con `PlaceholderUrlError` antes de tocar la red o la DB.
