# Changelog

Todos los cambios relevantes de este proyecto se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y el
proyecto se adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [No publicado]

### Añadido
- **Router de intención** del agente (`LLM_ROUTER_MODEL`): un modelo barato
  (p.ej. Gemini Flash) clasifica la pregunta (búsqueda / saludo / fuera de
  alcance) antes del loop caro; los saludos se responden en una sola llamada
  sin tocar la búsqueda. Ante cualquier error del router, cae a búsqueda.
- **Multi-proveedor** vía `LLM_PROVIDER` (`google` | `openai` | `groq` |
  `openrouter` | `custom`): el endpoint se deduce del proveedor y un
  `LLM_API_BASE` explícito lo sobreescribe (para servidores locales).
- **Panorama del corpus** en el prompt del agente: municipios, años y tipos de
  documento disponibles, consultados en vivo (cacheados), para acotar búsquedas
  sin asumir cobertura.
- **Memoria de conversación por sesión**: el cliente reenvía los últimos pares
  pregunta→respuesta (`history` en `POST /ask`) y el portal persiste la
  conversación en `sessionStorage` (sobrevive recargas), con botón "Nueva
  conversación". No se almacenan chats en base de datos.
- **Filtros de municipio/año** en la herramienta `search_documents` del agente
  y **score de relevancia** en sus resultados.
- Recomendación de la **Plataforma Nacional de Transparencia (PNT)** y de la
  **guía paso a paso** del panel cuando un documento no está en el corpus.

### Cambiado
- Las stopwords de citación de municipios se derivan dinámicamente del corpus
  (ya no se codifican Tala/Tequila a mano).
- Cobertura territorial ampliada a **Tala y Tequila**.

### Corregido
- HMR del portal en carpetas sincronizadas con OneDrive (`server.watch.usePolling`
  en Vite), donde el watcher perdía eventos de archivo.

## [0.1.0] — MVP inicial

### Añadido
- Ingesta de documentos públicos vía scrapers configurables (`generic_http`,
  `sapumu_content`) y flujo de descubrimiento SAPUMU (`sapumu scan`,
  `discovered inspect`, `discovered ingest`).
- Preservación con hash SHA-256 y versionado por URL (sin sobrescritura).
- Procesamiento: extracción de texto + chunking + embeddings (`dummy` por
  defecto; `local_st` para semántica real).
- Búsqueda híbrida (vectorial + lexical) con filtro `local_only` y reranking
  opcional con cross-encoder.
- Títulos legibles inferidos desde contenido (`infer-titles`).
- Asistente conversacional con citas (`POST /ask`) tipo ReAct acotado.
- Manifests de integridad reproducibles.
- API HTTP (FastAPI), portal web (React + Vite + Caddy) y CLI (Typer).
- Divulgación de código fuente AGPLv3 §13 (`GET /source`).

[No publicado]: https://github.com/Chaetard/open-data-jalisco/commits/main
[0.1.0]: https://github.com/Chaetard/open-data-jalisco/releases/tag/v0.1.0
