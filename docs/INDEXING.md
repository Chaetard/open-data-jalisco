# Indexar una página en tu instancia self-hosted

Cómo agregar una fuente nueva (un portal, una página o un conjunto de documentos)
y dejarla **buscable** en tu propia instancia levantada con `docker compose`.

> Esta guía asume el despliegue Docker del [README](../README.md#despliegue-docker--todo-en-uno).
> Si trabajas en local con `uv run`, los comandos son idénticos: quita el prefijo
> `docker compose exec -T api`.

---

## Modelo mental

Indexar una página son tres pasos, siempre en este orden:

```
1. Definir la fuente   →  datasets/sources/<slug>.yaml   (qué descargar)
2. Ingestar            →  ingest / discovered ingest     (descarga + preserva con hash)
3. Procesar            →  process                        (extrae texto + chunkea + embebe)
                                                          └─ recién aquí queda buscable
```

Un documento ingestado pero **no procesado** existe en la base con su hash y su
`official_url`, pero no aparece en `/search` hasta que `process` le genera chunks y
embeddings.

### Dos requisitos previos

1. **Las fuentes viven en `datasets/`, que está bind-mounted** (`./datasets:/app/datasets`
   en `docker-compose.yml`). Editas el YAML en el host y el contenedor lo ve al
   instante — **no hace falta reconstruir la imagen** para agregar o cambiar una fuente.

2. **Para búsqueda semántica real necesitas `EMBEDDING_PROVIDER=local_st`** en tu `.env`
   (con `API_EXTRAS=local-embed`). Con el default `dummy` la ingesta y el procesado
   funcionan, pero los embeddings son ruido determinístico: `/search` no encuentra nada
   útil. Ver [README → Demo local con embedder real](../README.md#demo-local-con-embedder-real).

---

## Elegir el tipo de scraper

| Tu fuente es… | Usa `scraper.type` | Cómo se indexa |
|---|---|---|
| Un puñado de URLs de documentos que ya conoces, o una página índice con enlaces `<a href>` directos a PDFs/XLSX | `generic_http` | Caso A |
| Un portal **SAPUMU** (Laravel/Vue con `<level-content :content="...">`, p. ej. `*.sapumu.com`) | `sapumu_content` | Caso B |
| Otra estructura (SPA que renderiza enlaces por JS, paginación compleja, API propia) | — | Requiere un scraper dedicado; ver [Limitaciones](#limitaciones) |

---

## Caso A — `generic_http` (URLs directas + descubrimiento superficial)

### 1. Crea el YAML de la fuente

Copia la plantilla y rellénala:

```bash
cp configs/sources/example.yaml datasets/sources/mi-municipio.yaml
```

```yaml
slug: mi-municipio              # único; es el identificador en todos los comandos
name: "Mi Municipio (transparencia)"
kind: municipal_portal          # municipal_portal | state_transparency_portal |
                                # national_transparency_platform | gazette | other
municipality: "Mi Municipio"
official_url: "https://mimunicipio.gob.mx/transparencia"
is_active: true

metadata:
  state: "Jalisco"
  country: "MX"

scraper:
  type: generic_http

  # Lista blanca de dominios. Cualquier URL fuera de aquí se descarta.
  allowed_domains:
    - mimunicipio.gob.mx

  # Extensiones aceptadas (sin punto).
  document_extensions:
    - pdf
    - xlsx
    - docx

  # (A) URLs explícitas que verificaste a mano:
  direct_documents:
    - url: "https://mimunicipio.gob.mx/docs/contrato-001.pdf"
      title: "Contrato de obra 001/2025"
      document_type: contract     # contract | bidding | award | regulation |
                                  # minutes | budget | financial_report | other | unknown
      year: 2025
      metadata:
        external_id: "OBRA-001"

  # (B) Páginas índice HTML. Se descargan UNA vez y se extraen sus <a href>.
  #     OJO: descubrimiento superficial, NO recursivo. Si la página renderiza
  #     los enlaces por JavaScript, el HTML estático no los trae y no se
  #     descubre nada (verás reason=seed_no_anchors_found en el dry-run).
  seed_urls:
    - "https://mimunicipio.gob.mx/transparencia/contratos"
```

Puedes usar `direct_documents`, `seed_urls`, o ambos. Si solo tienes URLs sueltas,
omite `seed_urls`.

### 2. Ingesta (primero en seco)

```bash
# Dry-run: muestra qué descargaría y qué descarta (y por qué), sin tocar red ni DB.
docker compose exec -T api uv run open-data-jalisco ingest mi-municipio --limit 20 --dry-run

# Ingesta real (descarga + guarda con hash SHA-256, versionado por URL).
docker compose exec -T api uv run open-data-jalisco ingest mi-municipio --limit 20
```

El `--dry-run` reporta `direct`, `discovered` y `skipped_urls` con su `reason`
(`domain_not_allowed`, `extension_not_allowed`, `duplicate`, `seed_no_anchors_found`…).
Úsalo para afinar `allowed_domains`/`document_extensions` antes de descargar nada.

Sigue en [Paso común: procesar](#paso-común--procesar).

---

## Caso B — `sapumu_content` (portales SAPUMU)

Los portales SAPUMU exponen documentos en páginas `/contenido/{id}` con un JSON
embebido. No conoces los IDs de antemano: los **descubres** con `sapumu scan-content`.

### 1. Crea el YAML

Usa [`datasets/sources/tala.yaml`](../datasets/sources/tala.yaml) como referencia. Lo esencial:

```yaml
slug: mi-sapumu
name: "Mi Municipio (SAPUMU)"
kind: municipal_portal
municipality: "Mi Municipio"
official_url: "https://mimunicipio.sapumu.com/municipio/transparencia/articulo-8"
is_active: true

scraper:
  type: sapumu_content
  allowed_domains:
    - mimunicipio.sapumu.com
    - app-sapumu.sfo2.digitaloceanspaces.com     # bucket donde viven los archivos
  document_extensions: [pdf, xlsx, xls, csv, docx]

  # Páginas que `ingest` parsea. Aquí pones los IDs que descubras en el paso 2.
  content_pages:
    - "https://mimunicipio.sapumu.com/municipio/transparencia/articulo-8/contenido/63"

  # Plantilla que usa `sapumu scan-content` para probar rangos de IDs.
  content_page_template: "https://mimunicipio.sapumu.com/municipio/transparencia/articulo-8/contenido/{id}"

  # Plantillas por sección, para `sapumu scan <slug> --section <key>`.
  section_templates:
    articulo_8:  "https://mimunicipio.sapumu.com/municipio/transparencia/articulo-8/contenido/{id}"
    articulo_15: "https://mimunicipio.sapumu.com/municipio/transparencia/articulo-15/contenido/{id}"
```

### 2. Descubrir páginas con documentos (sin descargar nada)

`sapumu scan` recorre un rango de IDs y guarda los candidatos a un archivo. No escribe
en la DB ni descarga PDFs:

```bash
docker compose exec -T api uv run open-data-jalisco sapumu scan mi-sapumu \
    --section articulo_8 --from-id 1 --to-id 200 \
    --output datasets/discovered/mi-sapumu/articulo_8_candidates.json
```

### 3. Inspeccionar los candidatos (offline)

```bash
docker compose exec -T api uv run open-data-jalisco discovered inspect \
    datasets/discovered/mi-sapumu/articulo_8_candidates.json \
    --year 2025 --extension pdf
```

### 4. Ingestar desde los candidatos

```bash
# En seco primero:
docker compose exec -T api uv run open-data-jalisco discovered ingest \
    datasets/discovered/mi-sapumu/articulo_8_candidates.json \
    --source mi-sapumu --year 2025 --extension pdf --limit 20 --dry-run

# Real:
docker compose exec -T api uv run open-data-jalisco discovered ingest \
    datasets/discovered/mi-sapumu/articulo_8_candidates.json \
    --source mi-sapumu --year 2025 --extension pdf --limit 20
```

> Las categorías sensibles (p. ej. declaraciones patrimoniales) se bloquean
> automáticamente en la ingesta. Ver el manifiesto §6 sobre minimización de datos.

---

## Paso común — procesar

Ingestar solo descarga y preserva. Para que el documento sea **buscable** hay que
extraer texto, chunkear y embeber:

```bash
docker compose exec -T api uv run open-data-jalisco process --limit 50
```

`process` toma los documentos en estado `pending`, los procesa y los deja en:

- `indexed` — texto extraído y embebido; ya es buscable.
- `needs_ocr` — PDF escaneado sin capa de texto (OCR aún no implementado).
- `no_text` — sin texto extraíble.
- `failed` — error; revisa los logs.

La primera corrida con `local_st` descarga el modelo (~500 MB a la caché HF) y tarda;
las siguientes son rápidas.

### Títulos legibles (opcional, requiere `LLM_API_KEY`)

Muchos PDFs tienen nombres de archivo inútiles. Para mostrar títulos humanos en el portal:

```bash
docker compose exec -T api uv run open-data-jalisco infer-titles --limit 100
```

---

## Verificar que quedó indexado

```bash
# Estadísticas del corpus (documentos por estado, fuente, etc.)
docker compose exec -T api uv run open-data-jalisco db stats

# Búsqueda directa desde el CLI
docker compose exec -T api uv run open-data-jalisco search "contrato de obra 2025"
```

O contra la API: `GET /api/stats` y `POST /api/search`. También aparece en el portal web.

---

## Refresco automático (opcional)

Para re-ingestar y re-procesar tus fuentes en un horario, levanta el perfil `refresh`
(usa la misma imagen y lee las mismas fuentes de `datasets/`):

```bash
docker compose --profile refresh up -d
```

Se configura por variables `REFRESH*` en `.env`. Ver el README, sección de despliegue.

---

## Limitaciones

- **Descubrimiento superficial.** `generic_http` lee cada `seed_url` una sola vez; no
  sigue enlaces recursivamente. Si la página es una SPA que pinta los enlaces por JS,
  el HTML estático no los trae y no se descubre nada. Para crawls reales se necesita un
  `Scraper` dedicado registrado en `ingestion/scraper_factory`.
- **Guardia de placeholders.** Si una URL conserva fragmentos de plantilla
  (`example.invalid`, `REEMPLAZAR`, `<replace>`), la ingesta aborta con
  `PlaceholderUrlError` antes de tocar la red. Reemplaza todos los placeholders.
- **Deduplicación por hash.** Un documento idéntico (mismo SHA-256) no se duplica. Si la
  fuente oficial cambia el archivo, se guarda una versión nueva con hash nuevo; la
  anterior nunca se sobrescribe.
- **`dummy` no busca.** Si procesaste con `EMBEDDING_PROVIDER=dummy` y luego cambiaste a
  `local_st`, los chunks viejos tienen embeddings inservibles. Bórralos y reprocesa:
  `db reset-chunks` y luego `process` de nuevo.
