# Guía de implementación frontend — open-data-jalisco API

Guía agnóstica de framework para conectar un frontend (React, Vue, Svelte, Next, Astro, Angular, vanilla, lo que sea) al backend FastAPI de `open-data-jalisco`. El objetivo es probar cada endpoint y armar pantallas básicas de validación, no producir un cliente final.

No incluye código de implementación: incluye contratos, ejemplos de request/response, comportamiento esperado y los detalles que el frontend necesita conocer (paginación, filtros, errores, semántica de campos).

---

## 1. Información del servicio

| Dato              | Valor                                                                                                                                                                                                                                                                                                                   |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Base URL local    | `http://localhost:8000`                                                                                                                                                                                                                                                                                                 |
| Levantar API      | `make api` (alias de `uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir .`)                                                                                                                                                                                                                |
| Docs interactivas | `GET /docs` (Swagger UI) y `GET /redoc`                                                                                                                                                                                                                                                                                 |
| OpenAPI JSON      | `GET /openapi.json` — útil para autogenerar tipos/clientes                                                                                                                                                                                                                                                              |
| Content-Type      | `application/json; charset=utf-8` (request y response salvo `/health`)                                                                                                                                                                                                                                                  |
| Autenticación     | Ninguna actualmente (no hay tokens, no hay cookies)                                                                                                                                                                                                                                                                     |
| CORS              | **Configurado y env-driven**. Por default acepta `http://localhost:5173` (Vite), `http://localhost:3000` (CRA/Next) y `http://127.0.0.1:5173`. Para prod o un puerto distinto, override `CORS_ORIGINS` en `.env` con una lista separada por comas (ej. `CORS_ORIGINS="https://odj.example.com,http://localhost:5173"`). |
| Errores           | FastAPI devuelve `{ "detail": "<mensaje>" }` con códigos HTTP estándar (404, 422, 500). 422 viene con un array de errores de validación.                                                                                                                                                                                |

---

## 2. Mapa de endpoints

| Método | Ruta                              | Propósito                                                                                                                                                       |
| ------ | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/health`                         | Liveness check, versión, environment.                                                                                                                           |
| GET    | `/sources`                        | Lista de fuentes (municipios/portales) registradas.                                                                                                             |
| GET    | `/sources/{slug}`                 | Detalle de una fuente por slug.                                                                                                                                 |
| GET    | `/documents`                      | Lista paginada de documentos con filtros.                                                                                                                       |
| GET    | `/documents/{document_id}`        | Detalle de un documento por UUID.                                                                                                                               |
| GET    | `/documents/{document_id}/chunks` | Chunks de texto extraídos del documento.                                                                                                                        |
| GET    | `/search`                         | Búsqueda semántica via query string (legacy).                                                                                                                   |
| POST   | `/search`                         | Búsqueda semántica con body JSON (preferido).                                                                                                                   |
| POST   | `/semantic-search`                | Alias explícito de `POST /search`.                                                                                                                              |
| GET    | `/manifests`                      | Lista de manifests de integridad generados.                                                                                                                     |
| POST   | `/ask`                            | **Agente**: pregunta en lenguaje natural → respuesta redactada con citas. Requiere `LLM_API_KEY` en el backend; si no está configurado responde `503`. Ver §11. |

Todos los endpoints son `GET` excepto los `POST` de búsqueda y `/ask`. No hay endpoints de mutación expuestos al frontend — ingesta/procesamiento ocurren vía CLI (`odj ingest`, `odj process`).

---

## 3. Convenciones globales

### 3.1 Identificadores

- `id` de fuentes y documentos: **UUID v4** (string, formato `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).
- `slug` de fuentes: string corto, sin espacios, ej. `"tala"`.
- `sha256`: string hex de 64 caracteres. Es la huella de contenido — dos documentos con la misma URL y distinto sha256 son versiones distintas.

### 3.2 Fechas

- `captured_at` viene como **ISO-8601 UTC** (ej. `"2026-05-31T14:22:03.812345+00:00"`). Parsea con `Date` nativo / `Temporal` / la librería que uses.

### 3.3 Paginación

`GET /documents` paginará con `limit` (1–200, default 50) y `offset` (≥0, default 0). El backend NO devuelve un `total` ni un `next_cursor`: la única manera de saber si hay más es comparar `response.length` con el `limit` enviado.

Estrategia frontend simple para "ver más":

- Pide `limit=50, offset=0`.
- Si la respuesta trae 50 items, hay potencialmente más → siguiente página con `offset=50`.
- Si trae <50, llegaste al final.

### 3.4 Enums

El backend serializa los enums como strings minúsculas:

- `SourceKind`: `municipal_portal`, `state_transparency_portal`, `national_transparency_platform`, `gazette`, `other`.
- `DocumentType`: `contract`, `bidding`, `award`, `regulation`, `minutes`, `budget`, `financial_report`, `other`, `unknown`.
- `ProcessingStatus`: `pending`, `extracted`, `chunked`, `indexed`, `failed`, `needs_ocr`.

El frontend puede declarar tipos union de string para estos campos y nunca recibirá un valor fuera de esa lista.

### 3.5 Manejo de errores

Todas las respuestas no-2xx tienen este shape:

```json
{ "detail": "Source not found: foo" }
```

Excepto `422 Unprocessable Entity` (validación de FastAPI), que devuelve:

```json
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["query", "limit"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "abc"
    }
  ]
}
```

Recomendación: el cliente HTTP debería normalizar ambos a un objeto `{ status, message, fieldErrors? }` para mostrar feedback uniforme.

---

## 4. Endpoints en detalle

### 4.1 `GET /health`

Liveness probe. Sin parámetros, sin auth.

**Request**

```
GET /health
```

**Response 200**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "local"
}
```

**Uso en frontend**

- Mostrar un indicador "API conectada / desconectada" en la barra de estado de la app de prueba.
- Llamarlo al arrancar la app y, si quieres, cada 30s con `setInterval`.

---

### 4.2 `GET /sources`

Lista las fuentes registradas (cada municipio/portal es una fuente).

**Query params**

| Param              | Tipo    | Default | Notas                                             |
| ------------------ | ------- | ------- | ------------------------------------------------- |
| `include_inactive` | boolean | `false` | Si `true`, incluye fuentes con `is_active=false`. |

**Request**

```
GET /sources
GET /sources?include_inactive=true
```

**Response 200** — array de objetos `SourceOut`:

```json
[
  {
    "id": "8f1a3b4c-7d2e-4a9f-9b1c-2d3e4f5a6b7c",
    "slug": "tala",
    "name": "Tala (SAPUMU portal)",
    "kind": "municipal_portal",
    "municipality": "Tala",
    "official_url": "https://tala.sapumu.com/municipio/transparencia/articulo-8",
    "description": "Municipal source served from the SAPUMU portal...",
    "is_active": true
  }
]
```

**Uso en frontend**

- Llenar un `<select>` o lista lateral con las fuentes disponibles.
- El `id` (UUID) se usa para filtrar documentos por `source_id` en `/documents` y `/search`.
- El `slug` se usa para llamar `GET /sources/{slug}` o filtrar `/manifests?source_slug=...`.

---

### 4.3 `GET /sources/{slug}`

Detalle de una fuente.

**Path param**

| Param  | Tipo   | Notas         |
| ------ | ------ | ------------- |
| `slug` | string | Ej. `"tala"`. |

**Request**

```
GET /sources/tala
```

**Response 200**

```json
{
  "id": "8f1a3b4c-7d2e-4a9f-9b1c-2d3e4f5a6b7c",
  "slug": "tala",
  "name": "Tala (SAPUMU portal)",
  "kind": "municipal_portal",
  "municipality": "Tala",
  "official_url": "https://tala.sapumu.com/municipio/transparencia/articulo-8",
  "description": "Municipal source served from the SAPUMU portal...",
  "is_active": true
}
```

**Response 404**

```json
{ "detail": "Source not found: foo" }
```

**Uso en frontend**

- Página "Detalle de fuente" donde muestras nombre, municipio y un link al `official_url`.
- Botón "Ver documentos de esta fuente" → `GET /documents?source_id={id}`.

---

### 4.4 `GET /documents`

Lista paginada con filtros opcionales.

**Query params**

| Param           | Tipo    | Default | Validación                                |
| --------------- | ------- | ------- | ----------------------------------------- |
| `source_id`     | UUID    | —       | Filtra documentos de una fuente.          |
| `municipality`  | string  | —       | Match exacto (ej. `"Tala"`).              |
| `document_type` | string  | —       | Uno de los valores de `DocumentType`.     |
| `year`          | int     | —       | Ej. `2025`.                               |
| `current_only`  | boolean | `true`  | Si `false`, incluye versiones históricas. |
| `limit`         | int     | `50`    | 1–200.                                    |
| `offset`        | int     | `0`     | ≥0.                                       |

**Request**

```
GET /documents?source_id=8f1a3b4c-7d2e-4a9f-9b1c-2d3e4f5a6b7c&year=2025&limit=20&offset=0
```

**Response 200** — array de `DocumentOut`:

```json
[
  {
    "id": "11111111-2222-3333-4444-555555555555",
    "source_id": "8f1a3b4c-7d2e-4a9f-9b1c-2d3e4f5a6b7c",
    "sha256": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
    "title": "Documento SAPUMU Tala 2025-11 2743",
    "document_type": "other",
    "municipality": "Tala",
    "year": 2025,
    "official_url": "https://app-sapumu.sfo2.digitaloceanspaces.com/tala/content/2025/11/2743/VYx464GjY1.pdf",
    "captured_url": "https://app-sapumu.sfo2.digitaloceanspaces.com/tala/content/2025/11/2743/VYx464GjY1.pdf",
    "captured_at": "2026-05-31T14:22:03.812345+00:00",
    "mime_type": "application/pdf",
    "storage_path": "tala/9a8b7c6d.../document.pdf",
    "file_size": 1580901,
    "processing_status": "indexed",
    "needs_ocr": false,
    "version": 1,
    "is_current": true,
    "superseded_by": null
  }
]
```

**Notas sobre el modelo**

- `version` y `is_current` permiten mostrar el historial. Si `is_current=false`, hay una versión más nueva; `superseded_by` apunta al UUID que la reemplazó (si está disponible).
- `processing_status` te dice si el texto ya fue extraído (`extracted`, `chunked`, `indexed`) o falló (`failed`, `needs_ocr`). Solo `indexed` (o `chunked`) garantiza que `GET /documents/{id}/chunks` devuelva resultados.
- `storage_path` es relativo al storage del backend — el frontend NO puede usarlo para descargar. Para descarga usa `official_url`.

**Uso en frontend**

- Tabla principal con paginación.
- Filtros side-bar con los query params.
- Click en una fila → ruta `/documents/{id}` para el detalle.

---

### 4.5 `GET /documents/{document_id}`

Detalle de un documento.

**Path param**

| Param         | Tipo | Notas    |
| ------------- | ---- | -------- |
| `document_id` | UUID | UUID v4. |

**Request**

```
GET /documents/11111111-2222-3333-4444-555555555555
```

**Response 200** — un único objeto `DocumentOut` (mismo schema que el array de `/documents`).

**Response 404**

```json
{ "detail": "Document not found: 11111111-2222-3333-4444-555555555555" }
```

**Uso en frontend**

- Pantalla de detalle del documento.
- Botón "Descargar original" → `target="_blank"` apuntando a `official_url`.
- Botón "Ver chunks" → `GET /documents/{id}/chunks`.

---

### 4.6 `GET /documents/{document_id}/chunks`

Chunks de texto del documento. Útiles para mostrar el cuerpo del documento ya procesado, o para construir el snippet de resultados de búsqueda.

**Request**

```
GET /documents/11111111-2222-3333-4444-555555555555/chunks
```

**Response 200** — array de `ChunkOut` ordenado por `chunk_index`:

```json
[
  {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "document_id": "11111111-2222-3333-4444-555555555555",
    "source_id": "8f1a3b4c-7d2e-4a9f-9b1c-2d3e4f5a6b7c",
    "sha256": "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
    "chunk_index": 0,
    "text": "REGLAMENTO DE GOBIERNO DEL MUNICIPIO DE TALA\nTÍTULO I\nDisposiciones Generales\nArtículo 1...",
    "char_count": 1782,
    "page_start": 1,
    "page_end": 1,
    "section_title": "Título I",
    "document_type": "regulation",
    "municipality": "Tala",
    "year": 2025
  }
]
```

**Response 404**

```json
{ "detail": "Document not found: 11111111-2222-3333-4444-555555555555" }
```

**Notas**

- Si el documento existe pero aún no fue procesado (`processing_status = "pending"` o `"failed"`), devuelve `200` con array vacío `[]`, no `404`.
- `page_start`/`page_end` son `null` para extracciones que no tienen paginación (ej. CSV/XLSX).
- `section_title` puede ser `null` si el extractor no detectó secciones.

**Uso en frontend**

- Vista "Leer documento": render lineal de `chunks[].text` separados por `chunk_index`.
- Para anclas: `section_title` puede usarse como heading.

---

### 4.7 Búsqueda semántica — `POST /search` (preferido)

Búsqueda semántica sobre el texto extraído. Internamente: la query se embeddea y se busca por distancia coseno contra los embeddings de los chunks.

**Request body** — `SearchRequest`:

```json
{
  "q": "presupuesto de egresos 2025",
  "limit": 10,
  "municipality": "Tala",
  "document_type": "budget",
  "source_id": "8f1a3b4c-7d2e-4a9f-9b1c-2d3e4f5a6b7c"
}
```

| Campo           | Tipo   | Requerido | Default | Notas                    |
| --------------- | ------ | --------- | ------- | ------------------------ |
| `q`             | string | sí        | —       | Mínimo 2 caracteres.     |
| `limit`         | int    | no        | `10`    | 1–50.                    |
| `municipality`  | string | no        | —       | Filtro exacto.           |
| `document_type` | string | no        | —       | Valor de `DocumentType`. |
| `source_id`     | UUID   | no        | —       | Filtra a una fuente.     |

**Response 200** — `SearchResponse`:

```json
{
  "query": "presupuesto de egresos 2025",
  "embedding_provider": "dummy",
  "embedding_model": "dummy-v1",
  "embedding_dimension": 384,
  "hits": [
    {
      "score": 0.8742,
      "chunk": {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "document_id": "11111111-2222-3333-4444-555555555555",
        "source_id": "8f1a3b4c-7d2e-4a9f-9b1c-2d3e4f5a6b7c",
        "sha256": "9a8b7c6d5e4f...",
        "chunk_index": 3,
        "text": "El presupuesto de egresos del ejercicio 2025...",
        "char_count": 1640,
        "page_start": 4,
        "page_end": 4,
        "section_title": "Capítulo II",
        "document_type": "budget",
        "municipality": "Tala",
        "year": 2025
      },
      "document": {
        "id": "11111111-2222-3333-4444-555555555555",
        "title": "Presupuesto de Egresos 2025",
        "official_url": "https://app-sapumu.../presupuesto-2025.pdf",
        "sha256": "9a8b7c6d5e4f...",
        "municipality": "Tala",
        "year": 2025,
        "document_type": "budget",
        "processing_status": "indexed"
      }
    }
  ]
}
```

(El objeto `document` dentro de cada hit es el mismo `DocumentOut` completo del endpoint `/documents/{id}`; abreviado arriba por legibilidad.)

**Semántica del `score`**

- Rango: `[0, 1]`. Mayor = más relevante.
- Calculado como `max(0, 1 - distance_cosine)`. Un 0.0 significa que el match es marginal o que ya saturó el límite.
- No es un porcentaje de relevancia "humano" — sirve para ordenar, no para mostrar "87% match" en UI a menos que aclares qué significa.

**Comportamiento esperado**

- Si no hay resultados, `hits` es array vacío `[]` (no 404).
- Si el `embedding_provider` actual es `"dummy"` (default en local), los resultados serán determinísticos pero no semánticamente útiles — útil sólo para validar la integración.
- 422 si `q` tiene menos de 2 caracteres.

**Uso en frontend**

- Componente search-bar con debounce (≥300ms) que dispara el `POST`.
- Lista de resultados: por cada hit muestra `document.title`, snippet de `chunk.text` (primeros 240 chars + `…`), `score` y un link al detalle del documento.
- Filtros opcionales: select de municipio, tipo de documento, source.

---

### 4.8 `GET /search` (legacy, equivalente)

Mismo comportamiento que `POST /search` pero con query string. Útil para enlaces compartibles ("URL como estado").

**Request**

```
GET /search?q=presupuesto%20de%20egresos%202025&limit=10&municipality=Tala
```

Mismos parámetros que el body del `POST`, mismo response. Preferí `POST` para queries largas o con muchos filtros.

---

### 4.9 `POST /semantic-search`

Alias explícito de `POST /search`. Mismo body, mismo response. Usar este cuando quieras dejar claro en el código del frontend que la intención es semántica (vs. otros tipos de búsqueda futuros como BM25).

---

### 4.10 `GET /manifests`

Lista los manifests de integridad generados por `odj manifest`. Son resúmenes con el conteo de documentos y la versión del pipeline en el momento de generación. Útiles para una pantalla de "auditoría".

**Query params**

| Param         | Tipo   | Default | Notas                           |
| ------------- | ------ | ------- | ------------------------------- |
| `source_slug` | string | —       | Filtra manifests de una fuente. |

**Request**

```
GET /manifests
GET /manifests?source_slug=tala
```

**Response 200** — array de `ManifestSummary`:

```json
[
  {
    "filename": "tala_2026-05-31T14-22-03.json",
    "source_slug": "tala",
    "municipality": "Tala",
    "generated_at": "2026-05-31T14:22:03.812345+00:00",
    "document_count": 42,
    "pipeline_version": "0.1.0"
  }
]
```

**Notas**

- `filename` es el nombre del JSON en disco bajo `datasets/manifests/`. El frontend NO puede descargarlo directamente vía API (no hay endpoint que sirva el blob). Si lo necesitas, agregar un router `GET /manifests/{filename}` al backend es trivial.
- Si `MANIFESTS_DIR` está vacío, devuelve `[]`.

**Uso en frontend**

- Tabla "Auditoría / Manifests" con columnas `generated_at`, `source_slug`, `document_count`, `pipeline_version`.
- Útil como prueba de existencia: si la cuenta crece, sabes que la ingesta corrió.

---

## 5. Flujos de prueba sugeridos

Estos son los flujos mínimos para validar que la integración frontend funciona. Hazlos en orden.

### Flujo 1 — Liveness

1. `GET /health` → confirma `status: "ok"`.

### Flujo 2 — Catálogo de fuentes

1. `GET /sources` → guarda el `id` y `slug` de la primera fuente.
2. `GET /sources/{slug}` → confirma que el detalle coincide.
3. `GET /sources/no-existe` → confirma `404` y muestra mensaje de error en UI.

### Flujo 3 — Listado de documentos

1. `GET /documents?limit=5` → confirma array con ≤5 items.
2. `GET /documents?source_id={id}` (usando el id del flujo 2) → confirma que todos los items tienen ese `source_id`.
3. `GET /documents?year=2025&document_type=budget` → confirma que el filtro se aplica.
4. Pagina: `GET /documents?limit=5&offset=5` → confirma que los items son distintos a la primera página.

### Flujo 4 — Detalle de documento + chunks

1. Toma un `document_id` del flujo 3.
2. `GET /documents/{id}` → confirma campos del modelo.
3. `GET /documents/{id}/chunks` → si `processing_status = "indexed"`, esperabas chunks; si `"pending"`, esperabas `[]`.

### Flujo 5 — Búsqueda

1. `POST /search` con `{ "q": "ab" }` (mínimo 2 chars) → confirma 200 (o `[]` en hits si no hay nada indexado).
2. `POST /search` con `{ "q": "a" }` → confirma 422 y muestra error de validación en UI.
3. `POST /search` con filtros (`municipality`, `document_type`, `source_id`) → confirma que `hits[].document` cumple los filtros.
4. `GET /search?q=test` → confirma que el equivalente GET responde igual.

### Flujo 6 — Manifests

1. `GET /manifests` → confirma array (puede estar vacío en local recién montado).
2. Si no hay manifests, generar uno desde el backend: `odj manifest <slug>` y volver a llamar.

---

## 6. Recomendaciones para el cliente HTTP del frontend

Sin asumir lenguaje, los puntos que debes cubrir en cualquier cliente:

1. **Capa única de fetch**. Un módulo `apiClient` que reciba `{ method, path, query, body }` y centralice base URL, headers y manejo de errores. No esparzas `fetch`/`axios` por la UI.
2. **Tipos / contratos**. Genera tipos desde `GET /openapi.json` (hay generadores para casi todo: `openapi-typescript`, `openapi-generator`, `quicktype`). Mantén un único `types.ts`/`api.d.ts`/equivalente.
3. **Cancelación**. Implementa `AbortController` (o equivalente) en `/search` — un usuario tipeando dispara múltiples requests y la última gana.
4. **Errores**. Normaliza `detail: string` y `detail: array` a una forma única: `{ message, fieldErrors }`. Las validaciones de FastAPI (422) deben mapearse a errores por campo.
5. **Loading / empty / error**. Cada vista debe tener los 4 estados: loading, error, empty (`[]`) y populated. La búsqueda semántica con `dummy` provider devolverá frecuentemente `hits: []` — no es un bug.
6. **Cache opcional**. `/sources` y `/manifests` son baratas y cambian raro — pueden cachearse en memoria por unos minutos. `/documents` y `/search` cambian más rápido — no cachees agresivamente.
7. **Paginación**. Recuerda: no hay `total`. Implementa "Cargar más" en vez de paginador numérico, o calcula manualmente con un round-trip extra.
8. **URLs canónicas**. Considera que cada vista tenga estado URL-shareable: `/search?q=...&municipality=...` y `/documents?year=2025&offset=20` — esto te da deep-links gratis para probar.

---

## 7. Pantallas mínimas sugeridas para validar todo

Para un frontend de pruebas no necesitas diseño — sólo necesitas estas 6 pantallas con las llamadas correctas:

| Pantalla             | Endpoints que dispara                                 |
| -------------------- | ----------------------------------------------------- |
| Home / status        | `GET /health`, `GET /sources`                         |
| Lista de fuentes     | `GET /sources?include_inactive=...`                   |
| Detalle de fuente    | `GET /sources/{slug}`, `GET /documents?source_id=...` |
| Lista de documentos  | `GET /documents` con filtros y paginación             |
| Detalle de documento | `GET /documents/{id}`, `GET /documents/{id}/chunks`   |
| Búsqueda             | `POST /search` (o `GET /search` con URL state)        |
| Manifests            | `GET /manifests` (opcional con `source_slug`)         |

Con esas 6 pantallas tocas el 100% de los endpoints expuestos hoy y puedes detectar regresiones de contrato apenas el backend cambie un campo.

---

## 8. Qué NO está expuesto al frontend (importante)

Estos casos requieren backend (CLI) o trabajo adicional — el frontend no debería intentar hacerlos:

- **Ingestar documentos** (`odj ingest`, `odj discovered ingest`). No hay endpoint HTTP; corre por CLI desde un operador.
- **Descargar el blob original** desde el storage interno. El frontend debe usar `official_url` (que apunta al portal público de la fuente). No hay `GET /documents/{id}/raw` ni equivalente.
- **Procesar / re-procesar** documentos (`odj process`). Sin endpoint.
- **Descubrir candidatos** (`odj sapumu scan`, `odj discovered inspect`). Sin endpoint — son herramientas de operador.
- **Generar manifests** (`odj manifest`). Sin endpoint — se generan por CLI y el frontend sólo los lista.

Si en algún punto necesitas alguna de estas operaciones desde la UI, se agregan como rutas nuevas en `api/routers/` — pero hoy no existen y el frontend no debe asumirlas.

---

## 9. Cambios futuros previsibles (heads-up al equipo de frontend)

Para que el cliente HTTP no te sorprenda:

- **Paginación con total**: el backend no devuelve `total` hoy. Si lo necesitas para mostrar "página 3 de 17", solicita agregar `X-Total-Count` o un wrapper `{ items, total, limit, offset }`.
- **Autenticación**: no existe. Si se agrega, será probablemente `Authorization: Bearer <jwt>` — diseña tu cliente con un slot para inyectar ese header desde el inicio.
- **Embedding provider**: el campo `embedding_provider` en `/search` te dice si estás en `"dummy"` (local), `"local_st"` (sentence-transformers) o algo real. El frontend puede mostrar un banner "Búsqueda en modo demo" cuando sea `"dummy"`.

---

## 10. Receta concreta para React + Vite

Esta sección NO reemplaza las anteriores — es el "kit de arranque" para el caso que más usamos en dev.

### 10.1 Arrancar todo en orden

En dos terminales separadas:

```bash
# Terminal 1 — API (puerto 8000). El --reload se reinicia solo al guardar.
make api
# equivalente literal:
# uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir .

# Terminal 2 — frontend Vite (puerto 5173 por default)
cd <tu-carpeta-de-front>
npm run dev
```

Verificá que la API responde antes de pelearte con el front:

```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0","environment":"local"}
```

### 10.2 Variable de entorno en Vite

En la raíz del front, `.env.development`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Para producción, `.env.production`:

```bash
VITE_API_BASE_URL=https://api.odj.example.com
```

Vite expone `import.meta.env.VITE_API_BASE_URL` (sólo las que empiezan con `VITE_`).

### 10.3 Tipos TypeScript del API

Pegá esto en `src/api/types.ts` — son los Pydantic schemas reales del backend (`api/schemas.py`):

```ts
export type ProcessingStatus =
  | "pending"
  | "extracted"
  | "chunked"
  | "indexed"
  | "failed"
  | "needs_ocr";

export type DocumentType =
  | "contract"
  | "bidding"
  | "award"
  | "regulation"
  | "minutes"
  | "budget"
  | "financial_report"
  | "other"
  | "unknown";

export interface SourceOut {
  id: string;
  slug: string;
  name: string;
  kind: string;
  municipality: string;
  official_url: string;
  description: string | null;
  is_active: boolean;
}

export interface DocumentOut {
  id: string;
  source_id: string;
  sha256: string;
  title: string | null;
  document_type: DocumentType;
  municipality: string;
  year: number | null;
  official_url: string;
  captured_url: string | null;
  captured_at: string; // ISO-8601 UTC
  mime_type: string;
  storage_path: string;
  file_size: number;
  processing_status: ProcessingStatus;
  needs_ocr: boolean;
  version: number;
  is_current: boolean;
  superseded_by: string | null;
}

export interface ChunkOut {
  id: string;
  document_id: string;
  source_id: string;
  sha256: string;
  chunk_index: number;
  text: string;
  char_count: number;
  page_start: number | null;
  page_end: number | null;
  section_title: string | null;
  document_type: DocumentType;
  municipality: string;
  year: number | null;
}

export interface SearchHit {
  score: number; // 0–1, mayor = mejor
  chunk: ChunkOut;
  document: DocumentOut;
}

export interface SearchResponse {
  query: string;
  embedding_provider: string; // "dummy" | "local_st" | ...
  embedding_model: string;
  embedding_dimension: number;
  hits: SearchHit[];
}

export interface SearchRequest {
  q: string;
  limit?: number; // 1–50, default 10
  municipality?: string | null;
  document_type?: DocumentType | null;
  source_id?: string | null; // UUID
}

export interface ApiError {
  status: number;
  message: string;
  fieldErrors?: Array<{ loc: string[]; msg: string }>;
}
```

### 10.4 Cliente HTTP mínimo (sin dependencias extras)

`src/api/client.ts`:

```ts
import type {
  ApiError,
  DocumentOut,
  SearchRequest,
  SearchResponse,
  SourceOut,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const err: ApiError = {
      status: res.status,
      message:
        typeof body.detail === "string" ? body.detail : "Validation error",
      fieldErrors: Array.isArray(body.detail) ? body.detail : undefined,
    };
    throw err;
  }
  return res.json();
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  listSources: (includeInactive = false) =>
    request<SourceOut[]>(
      `/sources${includeInactive ? "?include_inactive=true" : ""}`,
    ),

  listDocuments: (
    params: {
      limit?: number;
      offset?: number;
      municipality?: string;
      year?: number;
    } = {},
  ) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) q.set(k, String(v));
    }
    return request<DocumentOut[]>(`/documents?${q.toString()}`);
  },

  search: (body: SearchRequest) =>
    request<SearchResponse>("/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
```

### 10.5 Hook de búsqueda con cancelación

`src/hooks/useSearch.ts`:

```ts
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ApiError, SearchResponse } from "../api/types";

export function useSearch(query: string, limit = 10) {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const t = setTimeout(() => {
      api
        .search({ q, limit })
        .then((r) => {
          if (!cancelled) setData(r);
        })
        .catch((e) => {
          if (!cancelled) setError(e);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 300); // debounce 300ms
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [query, limit]);

  return { data, error, loading };
}
```

### 10.6 Componente de resultados

`src/components/SearchResults.tsx`:

```tsx
import type { SearchHit } from "../api/types";

export function SearchResults({ hits }: { hits: SearchHit[] }) {
  if (hits.length === 0) {
    return <p>Sin resultados. Probá otra consulta.</p>;
  }
  return (
    <ul className="search-results">
      {hits.map((hit) => (
        <li key={hit.chunk.id}>
          <header>
            <strong>{hit.document.title ?? "(sin título)"}</strong>
            <span> · score {hit.score.toFixed(3)}</span>
            {hit.chunk.page_start != null && (
              <span>
                {" "}
                · pág. {hit.chunk.page_start}
                {hit.chunk.page_end !== hit.chunk.page_start &&
                  `–${hit.chunk.page_end}`}
              </span>
            )}
          </header>
          <p>
            {hit.chunk.text.slice(0, 280)}
            {hit.chunk.text.length > 280 ? "…" : ""}
          </p>
          <a
            href={hit.document.official_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir PDF original ↗
          </a>
        </li>
      ))}
    </ul>
  );
}
```

### 10.7 Si tu front sigue rompiendo con CORS

Si después de levantar la API con CORS configurado seguís viendo error en el browser, chequeá en orden:

1. **El origin del front es el que el backend espera.** Abrí DevTools → Network → la request bloqueada → mirá el header `Origin` que envía el browser. Tiene que estar en `CORS_ORIGINS` del backend. Vite a veces arranca en `:5174` si `:5173` está ocupado.
2. **El backend NO se reinició** después de cambiar `.env`. `--reload` sólo escucha cambios en `.py`, no en `.env`. Mata el proceso y volvé a correr `make api`.
3. **Estás haciendo `fetch` a `0.0.0.0:8000`** (no, el browser no acepta eso). Usá `localhost:8000` o `127.0.0.1:8000`.
4. **Alternativa sin tocar nada**: el proxy de Vite. En `vite.config.ts`:
   ```ts
   server: {
     proxy: {
       "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
     },
   },
   ```
   Y tu front llama a `/api/search` sin cross-origin. Útil si tenés un proxy en prod y querés mismo shape en dev.

### 10.8 Debug del lado del backend

Si la API parece "responder vacío" pero hay docs en la DB:

```bash
# 1) Verificar que SÍ hay indexed
uv run open-data-jalisco db stats

# 2) Probar el endpoint directo (sin browser, sin CORS)
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"q":"comité de transparencia tala","limit":3}' | jq .

# 3) Si la API responde con hits pero el front muestra vacío, es bug del front.
#    Si la API también devuelve `hits: []`, mirá embedding_provider — si dice
#    "dummy" tu .env apunta al provider tonto y por eso no encuentra nada.
```

---

## 11. Agente conversacional (`POST /ask`)

Guía sin código de implementación: contrato, comportamiento, estados de UI y los detalles que el frontend necesita conocer para integrar el agente.

### 11.1 Qué es y cuándo usarlo (vs `/search`)

Son dos cosas distintas y conviene ofrecer ambas:

|                      | `POST /search`                           | `POST /ask`                                               |
| -------------------- | ---------------------------------------- | --------------------------------------------------------- |
| Devuelve             | Lista de **fragmentos crudos** rankeados | Una **respuesta redactada** + fuentes citadas             |
| Quién lee/interpreta | El usuario                               | El agente lee por el usuario y resume                     |
| Latencia             | ~0.5–3 s                                 | **~5–30 s o más** (varias búsquedas + llamadas al modelo) |
| Buen caso de uso     | "Quiero ver los documentos sobre X"      | "¿Cuánto cuesta el trámite Y?", "¿Qué necesito para Z?"   |
| Requiere             | Nada                                     | `LLM_API_KEY` en el backend                               |

Recomendación de UX: una sola caja de búsqueda con dos modos/botones — **"Ver documentos"** (`/search`) y **"Preguntar"** (`/ask`) — o una pestaña "Asistente" separada. No reemplaces la búsqueda por el agente: la búsqueda es rápida y siempre disponible; el agente es más lento y opcional.

### 11.2 Contrato

**Request** (`application/json`):

| Campo      | Tipo   | Requerido | Notas                                                             |
| ---------- | ------ | --------- | ----------------------------------------------------------------- |
| `question` | string | sí        | Pregunta en lenguaje natural. Mínimo 3 caracteres (si no, `422`). |

**Response `200`** (`AskResponse`):

| Campo        | Tipo   | Significado                                                                                                  |
| ------------ | ------ | ------------------------------------------------------------------------------------------------------------ |
| `answer`     | string | Respuesta redactada en español, citando documentos por su título.                                            |
| `model`      | string | Modelo LLM que respondió (ej. `gemini-2.5-pro`). Útil para mostrar "Generado por…".                          |
| `iterations` | int    | Cuántas vueltas de búsqueda/razonamiento tomó (1 = respondió a la primera). Informativo.                     |
| `sources`    | array  | Documentos que el agente consultó. Ver tabla siguiente. Puede venir vacío si respondió sin necesitar buscar. |

Cada objeto en `sources` (`AskSource`):

| Campo          | Tipo           | Uso en UI                                                           |
| -------------- | -------------- | ------------------------------------------------------------------- |
| `title`        | string \| null | Título del documento. Si es `null`, mostrar "Documento sin título". |
| `url`          | string         | URL oficial del PDF. Hacer la card **clickable** a este enlace.     |
| `page_start`   | int \| null    | Página del fragmento citado. Mostrar "pág. 12" si no es `null`.     |
| `page_end`     | int \| null    | Última página del fragmento.                                        |
| `jurisdiction` | string         | `municipal` / `state` / `federal` / `unknown`. Badge opcional.      |

Ejemplo de respuesta (contrato, no código de front):

```json
{
  "answer": "Para una licencia de construcción necesitas presentar… (según el Reglamento de construcción municipal).",
  "model": "gemini-2.5-pro",
  "iterations": 2,
  "sources": [
    {
      "title": "Reglamento de construcción municipal",
      "url": "https://…",
      "page_start": 12,
      "page_end": 12,
      "jurisdiction": "municipal"
    }
  ]
}
```

Llamada de referencia para probar el endpoint:

```bash
curl -s -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question":"¿Qué requisitos piden para una licencia de construcción?"}' | jq .
```

### 11.3 Estados de UI que SÍ o SÍ hay que manejar

1. **Latencia alta (lo más importante).** El agente hace varias búsquedas y una o más llamadas a un modelo remoto. Espera **5–30 s, a veces más**. No es como `/search`.
   - Muestra un indicador de progreso con texto tranquilizador ("Buscando en los documentos del municipio…"), idealmente rotando el mensaje cada pocos segundos para que no parezca colgado.
   - Pon un **timeout de cliente generoso**: igual o mayor a `LLM_TIMEOUT_SECONDS` del backend (por defecto 120 s). Un timeout corto (5–10 s) cortará respuestas válidas.
   - No bloquees toda la UI: deja al usuario cancelar o seguir navegando.

2. **Agente apagado → `503`.** Si el backend no tiene `LLM_API_KEY`, `/ask` responde `503` con `{ "detail": "Agent not configured. Set LLM_API_KEY…" }`.
   - El frontend debe **degradar con elegancia**: ocultar o deshabilitar la función "Preguntar" y, si acaso, mostrar "El asistente no está disponible en esta instancia". La búsqueda (`/search`) sigue funcionando normal.
   - No hay endpoint de "capabilities": la forma de saberlo es recibir un `503` (ver §11.4).

3. **Respuesta "no encontré evidencia".** El agente está instruido para decir que no hay información en vez de inventar. Eso llega como un `200` normal con un `answer` que lo explica y `sources` posiblemente vacío. **No lo trates como error** — muéstralo tal cual.

4. **Error del modelo / timeout / cuota → `500` o error de red.** El proveedor LLM remoto puede fallar o agotar cuota. Muestra un mensaje amable ("El asistente tuvo un problema, intenta de nuevo") y permite **reintentar**. No muestres el stack ni el detalle técnico crudo al ciudadano.

5. **Sin streaming (por ahora).** La respuesta llega **completa de una sola vez**, no token por token. Si quieres efecto "máquina de escribir" es puramente cosmético del front; el backend no transmite parcial todavía (ver §11.6).

### 11.4 Detectar si el agente está disponible

No hay flag de capacidades. Opciones, de menos a más limpia:

- **Reactiva (suficiente):** muestra el botón "Preguntar"; si la primera llamada devuelve `503`, ocúltalo y recuerda esa sesión que está apagado.
- **Proactiva (opcional):** al cargar la app, una petición ligera a `/ask` con una pregunta trivial te dirá `200` (encendido) o `503` (apagado) — pero gasta una llamada al modelo, así que no abuses.

Heads-up al equipo: si esto molesta, se puede exponer un flag (`agent_enabled`) en `/health` o `/stats` en el futuro. Hoy: `503` = apagado.

### 11.5 Mostrar la respuesta y las fuentes (trazabilidad = confianza)

El valor cívico del agente está en que **se puede verificar**. Reglas de presentación:

- Muestra el `answer` como texto redactado, legible.
- Debajo, lista **siempre** las `sources` como tarjetas/clickables que abren el `url` (el PDF oficial) en pestaña nueva. Incluye `title`, la página ("pág. 12") y, si quieres, el badge de `jurisdiction`.
- Si `sources` está vacío pero hay `answer`, deja claro que es una respuesta sin documento citado (poco común; trátalo con cautela visual).
- Opcional: muestra `model` en letra chica ("Respuesta generada por gemini-2.5-pro a partir de documentos públicos") — transparencia sobre que es IA, alineado con el principio del proyecto de IA como interfaz, no autoridad.

### 11.6 Conversación de un solo turno (sin memoria)

Cada `POST /ask` es **independiente**: el backend no recuerda preguntas anteriores. En la UI puedes mostrar un historial visual, pero cada pregunta se envía sola, sin contexto previo. Si el usuario hace una repregunta ("¿y para el otro trámite?"), debes reformularla completa antes de enviarla, o el agente no entenderá el "otro".

Heads-up: el multi-turno (memoria de conversación) sería un cambio de backend (aceptar un historial de mensajes). No lo asumas disponible.

### 11.7 Seguridad — la API key NUNCA toca el frontend

La `LLM_API_KEY` vive **solo** en el backend (`.env`, gitignored). El frontend jamás la ve, ni la manda, ni la necesita: el front solo llama a **tu** `/ask`, y el backend hace la llamada al modelo con su key. No pongas claves de LLM en variables `VITE_*` ni en el bundle del cliente — quedarían expuestas a cualquiera.

### 11.8 Pantalla mínima sugerida para validar

Una vista "Asistente": caja de texto para la pregunta + botón "Preguntar" → estado de carga con mensaje → respuesta redactada + lista de fuentes clickables. Con eso validas el flujo completo end-to-end. Si `/ask` da `503`, esa vista debe ocultarse o mostrar el aviso de "no disponible".
