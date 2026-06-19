# API pública — open-data-jalisco

Referencia completa de la API HTTP. Documenta **exactamente** los endpoints que
expone `open_data_jalisco.api.app:app` (FastAPI). Si un endpoint no está aquí, no
existe.

- **Versión del documento**: generado para la API `0.1.x`.
- **Licencia**: AGPL-3.0-or-later. Ver [`/source`](#get-source).
- **Repositorio**: <https://github.com/Chaetard/open-data-jalisco>

---

## Tabla de contenidos

1. [Conceptos básicos](#conceptos-básicos)
2. [Autenticación](#autenticación)
3. [CORS](#cors)
4. [Convenciones](#convenciones)
5. [Manejo de errores](#manejo-de-errores)
6. [Enumeraciones](#enumeraciones)
7. [Endpoints](#endpoints)
   - [GET /health](#get-health)
   - [GET /stats](#get-stats)
   - [GET /source](#get-source)
   - [GET /sources](#get-sources)
   - [GET /sources/{slug}](#get-sourcesslug)
   - [GET /documents](#get-documents)
   - [GET /documents/{document_id}](#get-documentsdocument_id)
   - [GET /documents/{document_id}/chunks](#get-documentsdocument_idchunks)
   - [POST /search](#post-search)
   - [GET /search](#get-search)
   - [POST /semantic-search](#post-semantic-search)
   - [GET /manifests](#get-manifests)
8. [Esquemas](#esquemas)
9. [OpenAPI / Swagger](#openapi--swagger)
10. [Recetas](#recetas)

---

## Conceptos básicos

- **Protocolo**: HTTP/1.1, JSON sobre `application/json`.
- **Base URL (dev)**: `http://localhost:8000`
- **Base URL (prod)**: el dominio donde despliegues (ej. `https://api.odj.example.com`).
- **Estado**: la API es **solo lectura**. No hay endpoints de escritura, borrado ni
  mutación. La ingesta y el procesamiento se hacen offline vía la CLI `odj`, no por HTTP.
- **Sin versionado en la ruta**: los endpoints no llevan prefijo `/v1`. La versión real
  se reporta en `GET /health` y `GET /source`.

### Modelo de datos en una frase

Una **fuente** (`source`, ej. el portal de transparencia de Tala) tiene muchos
**documentos** (`document`, un PDF). Cada documento se parte en **chunks** (fragmentos de
texto con embedding). La búsqueda semántica corre sobre los chunks y devuelve el chunk +
su documento padre.

```
source ──< document ──< chunk
```

---

## Autenticación

**Ninguna.** Todos los endpoints son públicos y anónimos. No hay API keys, tokens ni
cookies. Es información pública por diseño (transparencia gubernamental).

> Si en el futuro se agregan endpoints sensibles o de escritura, llevarán autenticación
> propia; los de lectura actuales seguirán abiertos.

---

## CORS

El navegador bloquea peticiones cross-origin salvo que el origin esté en la whitelist.
La lista se controla con la variable de entorno `CORS_ORIGINS` (separada por comas):

```bash
CORS_ORIGINS="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
```

- Métodos permitidos: `GET`, `POST`, `OPTIONS`.
- Headers permitidos: `Content-Type`, `Accept`.
- `allow_credentials: true`.
- En producción, fija `CORS_ORIGINS` al dominio exacto del frontend. **No uses `*`.**

Si `CORS_ORIGINS` queda vacío, el middleware CORS no se monta (peticiones desde un
navegador en otro origin fallarán; `curl` y server-to-server no se ven afectados).

---

## Convenciones

| Tema | Convención |
|---|---|
| Identificadores | `UUID` v4 en formato string (`"3f2a…"`). |
| Fechas | ISO-8601 UTC (`"2026-06-18T14:03:21.123456Z"`). |
| Paginación | `limit` + `offset` (sin cursores). Los límites máximos varían por endpoint. |
| Campos opcionales | Se devuelven como `null`, no se omiten. |
| `document_type` / `processing_status` / `kind` | strings de [enumeraciones](#enumeraciones) fijas. |
| Hashing | `sha256` hex de 64 chars; identifica el contenido binario del documento. |

---

## Manejo de errores

Errores de aplicación (`HTTPException`) devuelven el formato estándar de FastAPI:

```json
{ "detail": "Document not found: 3f2a1b8c-..." }
```

Errores de validación de parámetros (422) devuelven el formato detallado de FastAPI:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["query", "q"],
      "msg": "String should have at least 2 characters",
      "input": "a"
    }
  ]
}
```

| Código | Cuándo |
|---|---|
| `200` | OK. |
| `404` | Recurso no encontrado (documento/fuente inexistente). |
| `422` | Parámetro inválido (faltante, fuera de rango, tipo incorrecto). |
| `500` | Error interno (DB caída, embedder no inicializa, etc.). |

---

## Enumeraciones

### `DocumentType` (`document_type`)

`contract`, `bidding`, `award`, `regulation`, `minutes`, `budget`,
`financial_report`, `other`, `unknown`

### `ProcessingStatus` (`processing_status`)

`pending`, `extracted`, `chunked`, `indexed`, `failed`, `needs_ocr`

> Solo los documentos en `indexed` aparecen en resultados de búsqueda (son los que
> tienen embeddings).

### `SourceKind` (`kind`)

`municipal_portal`, `state_transparency_portal`,
`national_transparency_platform`, `gazette`, `other`

---

## Endpoints

### `GET /health`

Liveness check. No toca la base de datos.

**Respuesta `200`**

```json
{ "status": "ok", "version": "0.1.0", "environment": "local" }
```

```bash
curl -s http://localhost:8000/health
```

---

### `GET /stats`

Métricas agregadas para tarjetas de dashboard. Una query por métrica — usa esto en lugar
de paginar `/documents` para contar. Los números coinciden con `odj db stats`.

**Respuesta `200`** — [`StatsResponse`](#statsresponse)

```json
{
  "documents_total": 2433,
  "documents_by_status": [
    { "status": "failed",  "count": 12 },
    { "status": "indexed", "count": 1513 },
    { "status": "pending", "count": 908 }
  ],
  "chunks_total": 92451,
  "unique_documents_by_sha256": 740,
  "sources_total": 1,
  "documents_by_source": [
    { "slug": "tala", "count": 2433 }
  ]
}
```

> `documents_total` cuenta solo `is_current = true`. `unique_documents_by_sha256` cuenta
> sha256 distintos entre chunks — útil para saber cuántos documentos *de contenido único*
> hay (el portal republica PDFs idénticos en varias URLs).

```bash
curl -s http://localhost:8000/stats | jq
```

---

### `GET /source`

Divulgación de código fuente requerida por AGPLv3 §13. Si despliegas una versión
modificada, este endpoint **debe** apuntar a tu fork público.

**Respuesta `200`**

```json
{
  "repository": "https://github.com/Chaetard/open-data-jalisco",
  "license": "AGPL-3.0-or-later",
  "version": "0.1.0",
  "commit": null
}
```

`commit` se rellena en deploy con la variable de entorno `SOURCE_COMMIT` (ej. el SHA del
build). Si no se setea, es `null`.

---

### `GET /sources`

Lista las fuentes de datos.

**Query params**

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `include_inactive` | bool | `false` | Si `true`, incluye fuentes con `is_active = false`. |

**Respuesta `200`** — `list[`[`SourceOut`](#sourceout)`]`

```bash
curl -s "http://localhost:8000/sources" | jq
curl -s "http://localhost:8000/sources?include_inactive=true" | jq
```

---

### `GET /sources/{slug}`

Una fuente por su `slug` (ej. `tala`).

**Respuesta `200`** — [`SourceOut`](#sourceout)
**Respuesta `404`** — `{ "detail": "Source not found: <slug>" }`

```bash
curl -s http://localhost:8000/sources/tala | jq
```

---

### `GET /documents`

Lista documentos con filtros. Paginado.

**Query params**

| Param | Tipo | Default | Rango | Descripción |
|---|---|---|---|---|
| `source_id` | UUID | — | | Filtra por fuente. |
| `municipality` | string | — | | Filtra por municipio (ej. `Tala`). |
| `document_type` | string | — | [enum](#documenttype-document_type) | Filtra por tipo. |
| `year` | int | — | | Filtra por año del documento. |
| `current_only` | bool | `true` | | Solo la versión vigente de cada documento. |
| `limit` | int | `50` | `1`–`200` | Tamaño de página. |
| `offset` | int | `0` | `≥ 0` | Desplazamiento. |

**Respuesta `200`** — `list[`[`DocumentOut`](#documentout)`]`

```bash
# Primeros 200 documentos indexados de Tala
curl -s "http://localhost:8000/documents?municipality=Tala&limit=200" | jq

# Página 2 de reglamentos
curl -s "http://localhost:8000/documents?document_type=regulation&limit=50&offset=50" | jq
```

---

### `GET /documents/{document_id}`

Un documento por su UUID.

**Respuesta `200`** — [`DocumentOut`](#documentout)
**Respuesta `404`** — `{ "detail": "Document not found: <uuid>" }`

```bash
curl -s http://localhost:8000/documents/3f2a1b8c-1234-5678-9abc-def012345678 | jq
```

---

### `GET /documents/{document_id}/chunks`

Todos los chunks de un documento, en orden (`chunk_index`). Útil para reconstruir el texto
o resaltar el fragmento que devolvió la búsqueda.

**Respuesta `200`** — `list[`[`ChunkOut`](#chunkout)`]`
**Respuesta `404`** — `{ "detail": "Document not found: <uuid>" }` (si el documento no existe)

```bash
curl -s http://localhost:8000/documents/3f2a1b8c-.../chunks | jq '.[].text'
```

---

### `POST /search`

**Endpoint principal de búsqueda semántica.** Recibe una query en lenguaje natural, la
convierte a embedding y devuelve los chunks más cercanos por distancia coseno. Los
resultados se deduplican por `sha256` (PDFs idénticos publicados en varias URLs colapsan a
un hit).

**Request body** — [`SearchRequest`](#searchrequest)

| Campo | Tipo | Default | Rango | Descripción |
|---|---|---|---|---|
| `q` | string | — (req.) | `≥ 2` chars | Query libre. |
| `limit` | int | `10` | `1`–`50` | Máximo de hits a devolver. |
| `municipality` | string | `null` | | Filtra por municipio. |
| `document_type` | string | `null` | [enum](#documenttype-document_type) | Filtra por tipo. |
| `source_id` | UUID | `null` | | Filtra por fuente. |
| `local_only` | bool | `true` | | Oculta material de referencia estatal/federal republicado, deja sólo lo municipal (y sin marcar). **Activo por defecto** — pasa `false` para buscar todo el corpus. Ver [calidad de búsqueda](#calidad-de-búsqueda-reranking-y-jurisdicción). |

**Respuesta `200`** — [`SearchResponse`](#searchresponse)

```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"q": "presupuesto municipal", "limit": 5, "local_only": true}' | jq
```

**Ejemplo de respuesta (recortado)**

```json
{
  "query": "requisitos para licencia de construcción",
  "embedding_provider": "local_st",
  "embedding_model": "intfloat/multilingual-e5-small",
  "embedding_dimension": 384,
  "hits": [
    {
      "score": 0.8721,
      "chunk": {
        "id": "…", "document_id": "…", "chunk_index": 4,
        "text": "Requisitos: 1. Solicitud… 2. Identificación oficial…",
        "page_start": 2, "page_end": 2, "section_title": "Requisitos",
        "document_type": "regulation", "municipality": "Tala", "year": 2024
      },
      "document": {
        "id": "…", "title": "Reglamento de construcción municipal",
        "document_type": "regulation", "official_url": "https://…",
        "processing_status": "indexed", "is_current": true
      }
    }
  ]
}
```

#### Cómo interpretar `score`

`score = max(0, 1 − distancia_coseno)`. Rango `[0, 1]`, mayor = más relevante.

| `score` | Lectura práctica |
|---|---|
| `> 0.88` | Match muy fuerte (suele haber solape literal o semántico claro). |
| `0.84–0.88` | Relevante. La mayoría de buenos resultados caen aquí. |
| `< 0.82` | Débil. Probablemente no es lo que buscabas. |

> Cuando los top hits tienen scores casi idénticos (ej. `0.868`–`0.872`), el embedder no
> está discriminando bien — típico al usar lenguaje coloquial ciudadano contra documentos
> en lenguaje legal/administrativo. Es una limitación conocida del retriever, mitigada por
> el reranking (abajo).

#### Calidad de búsqueda: reranking y jurisdicción

Dos mejoras opcionales sobre la búsqueda vectorial base, ambas activables sin migrar la DB:

**1. Reranking (cross-encoder).** El embedder (bi-encoder) puntúa query y pasaje por
separado y apelmaza resultados en un banco plano de scores. Si se activa
`RERANK_PROVIDER=cross_encoder`, una segunda etapa cross-encoder lee `(query, pasaje)`
juntos y reordena el top-N antes de truncar al `limit`. En la práctica separa el banco
plano en un gradiente amplio y sube el documento correcto al `#1`. Cuando corre, cada hit
trae `rerank_score` y la respuesta trae `reranker` con el modelo. Coste: ~470 MB de modelo
y ~1-3 s/query en CPU. Desactivado (`none`) por defecto: sin coste, comportamiento idéntico.

**2. Filtro de jurisdicción (`local_only`).** El portal municipal republica material de
referencia *estatal* y *federal* (el presupuesto del Estado de Jalisco, leyes federales),
todo bajo `municipality="Tala"`. Por eso "presupuesto municipal" devolvía los volúmenes del
*Estado* arriba de los del municipio. Cada documento trae un badge `jurisdiction`
(`municipal`/`state`/`federal`/`unknown`) inferido del título; **`local_only` está activo por
defecto** y oculta `state` y `federal`, dejando lo municipal (y lo no marcado, que nunca se
oculta por error). Pasa `local_only=false` para buscar el corpus completo.

Se combinan: el reranking ordena bien el conjunto, `local_only` garantiza que no se cuele
referencia de otro nivel de gobierno. El badge `jurisdiction` está siempre presente aunque
no se filtre, para que el frontend lo muestre.

---

### `GET /search`

Variante GET, **legacy**. Mismo comportamiento que `POST /search` pero con query params.
Prefiere `POST` para frontends nuevos.

**Query params**

| Param | Tipo | Default | Rango |
|---|---|---|---|
| `q` | string | — (req.) | `≥ 2` chars |
| `limit` | int | `10` | `1`–`50` |
| `municipality` | string | `null` | |
| `document_type` | string | `null` | |
| `source_id` | UUID | `null` | |
| `local_only` | bool | `true` | |

**Respuesta `200`** — [`SearchResponse`](#searchresponse)

```bash
# local_only=true por defecto; pasa false para incluir material estatal/federal
curl -s "http://localhost:8000/search?q=presupuesto%20municipal&limit=5" | jq
```

---

### `POST /semantic-search`

Ruta semántica explícita. **Actualmente equivalente a `POST /search`** (mismo body, misma
respuesta). Existe para dejar espacio a futuras variantes de búsqueda (ej. híbrida
keyword+vector) sin romper `/search`.

**Request body** — [`SearchRequest`](#searchrequest)
**Respuesta `200`** — [`SearchResponse`](#searchresponse)

---

### `GET /manifests`

Lista los manifiestos de integridad escritos bajo `MANIFESTS_DIR`. Cada manifiesto es un
snapshot point-in-time generado por `odj manifest` (no se actualiza solo — si las cifras
se ven viejas, regenera con `make manifest SOURCE=tala`).

**Query params**

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `source_slug` | string | `null` | Filtra por slug de fuente. |

**Respuesta `200`** — `list[`[`ManifestSummary`](#manifestsummary)`]`

```bash
curl -s "http://localhost:8000/manifests?source_slug=tala" | jq
```

---

## Esquemas

### `SourceOut`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | |
| `slug` | string | Identificador estable (ej. `tala`). |
| `name` | string | Nombre legible. |
| `kind` | string | [`SourceKind`](#sourcekind-kind). |
| `municipality` | string | |
| `official_url` | string | URL del portal oficial. |
| `description` | string \| null | |
| `is_active` | bool | |

### `DocumentOut`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | |
| `source_id` | UUID | |
| `sha256` | string (64 hex) | Hash del binario. PDFs idénticos comparten sha256. |
| `title` | string \| null | |
| `document_type` | string | [`DocumentType`](#documenttype-document_type). |
| `municipality` | string | |
| `year` | int \| null | |
| `official_url` | string | URL canónica del documento. |
| `captured_url` | string \| null | URL exacta desde donde se descargó. |
| `captured_at` | datetime | ISO-8601 UTC. |
| `mime_type` | string | Ej. `application/pdf`. |
| `storage_path` | string | Ruta interna del binario crudo. |
| `file_size` | int | Bytes. |
| `processing_status` | string | [`ProcessingStatus`](#processingstatus-processing_status). |
| `needs_ocr` | bool | `true` si el PDF es imagen sin capa de texto. |
| `version` | int | Versión del documento (≥ 1). |
| `is_current` | bool | `false` si fue reemplazado. |
| `superseded_by` | UUID \| null | Documento que lo reemplaza, si aplica. |
| `jurisdiction` | string | Nivel de gobierno inferido del título: `municipal`, `state`, `federal`, `unknown`. Heurística — ver [calidad de búsqueda](#calidad-de-búsqueda-reranking-y-jurisdicción). |

### `ChunkOut`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | |
| `document_id` | UUID | Documento padre. |
| `source_id` | UUID | |
| `sha256` | string | sha256 del documento padre (usado para dedup). |
| `chunk_index` | int | Orden dentro del documento (0-based). |
| `text` | string | Texto del fragmento. |
| `char_count` | int | Longitud en caracteres. |
| `page_start` | int \| null | Primera página del fragmento (1-based). |
| `page_end` | int \| null | Última página del fragmento. |
| `section_title` | string \| null | Encabezado de sección si se detectó. |
| `document_type` | string | Heredado del documento. |
| `municipality` | string | Heredado del documento. |
| `year` | int \| null | Heredado del documento. |

### `SearchRequest`

Ver [`POST /search`](#post-search).

### `SearchHit`

| Campo | Tipo | Notas |
|---|---|---|
| `score` | float | Similitud coseno `[0, 1]`, mayor = más relevante. Ver [interpretación](#cómo-interpretar-score). |
| `rerank_score` | float \| null | Score del cross-encoder; presente sólo si hubo reranking. Logit sin acotar, comparable sólo dentro de una misma respuesta. Cuando está presente, los hits van ordenados por él (no por `score`). |
| `chunk` | [`ChunkOut`](#chunkout) | El fragmento que hizo match. |
| `document` | [`DocumentOut`](#documentout) | El documento padre. |

### `SearchResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `query` | string | La query recibida (echo). |
| `embedding_provider` | string | `dummy` o `local_st`. |
| `embedding_model` | string | Ej. `intfloat/multilingual-e5-small`. |
| `embedding_dimension` | int | Ej. `384`. |
| `reranker` | string \| null | Nombre del modelo de reranking si se aplicó, si no `null`. |
| `hits` | [`SearchHit`](#searchhit)[] | Deduplicados por `sha256`. Ordenados por `rerank_score` si hubo reranking, si no por `score`. |

> Si `embedding_provider` es `dummy`, los resultados **no son semánticamente útiles** (el
> embedder de prueba devuelve vectores deterministas sin significado). En prod debe ser
> `local_st`.

### `StatsResponse`

| Campo | Tipo | Notas |
|---|---|---|
| `documents_total` | int | Solo `is_current = true`. |
| `documents_by_status` | `{ status, count }[]` | Conteo por `processing_status`. |
| `chunks_total` | int | Total de chunks. |
| `unique_documents_by_sha256` | int | sha256 distintos entre chunks. |
| `sources_total` | int | Número de fuentes. |
| `documents_by_source` | `{ slug, count }[]` | Conteo por fuente. |

### `ManifestSummary`

| Campo | Tipo | Notas |
|---|---|---|
| `filename` | string | Nombre del archivo JSON. |
| `source_slug` | string | |
| `municipality` | string \| null | |
| `generated_at` | string \| null | |
| `document_count` | int \| null | Documentos al momento del snapshot. |
| `pipeline_version` | string \| null | |

---

## OpenAPI / Swagger

FastAPI genera documentación interactiva automáticamente:

| Recurso | Ruta |
|---|---|
| Swagger UI | `GET /docs` |
| ReDoc | `GET /redoc` |
| Esquema OpenAPI (JSON) | `GET /openapi.json` |

El `openapi.json` es la fuente de verdad de la máquina — úsalo para generar clientes
tipados (ej. `openapi-typescript`). Este documento es la versión legible para humanos.

---

## Recetas

### Levantar la API en local

```bash
uv run uvicorn open_data_jalisco.api.app:app --reload --port 8000
```

Requiere PostgreSQL con pgvector y la DB poblada. Para resultados semánticos reales,
exporta antes:

```bash
export EMBEDDING_PROVIDER=local_st
export EMBEDDING_MODEL=intfloat/multilingual-e5-small
```

### Flujo típico de un frontend de búsqueda

1. `GET /stats` para las tarjetas (totales, por estado, por fuente).
2. `POST /search` con la query del usuario → renderizar `hits`.
3. Por cada hit, ya tienes `chunk.text`, `chunk.page_start` y `document.official_url`
   para enlazar al PDF y señalar la página.
4. (Opcional) `GET /documents/{id}/chunks` para mostrar el documento completo o resaltar
   el fragmento en contexto.

Ver [`FRONTEND_GUIDE.md`](./FRONTEND_GUIDE.md) para el cliente TypeScript completo, tipos y
hook de React + Vite.

### Generar un cliente TypeScript desde el esquema

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts
```
