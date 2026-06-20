/**
 * Cliente HTTP del portal de datos abiertos.
 *
 * Expone un único objeto `api` con los endpoints agrupados por recurso.
 * Toda petición pasa por `request`, que centraliza cabeceras, tiempo de
 * espera, cancelación y normalización de errores en `ApiError`.
 */

const API_BASE = "/api";
const DEFAULT_TIMEOUT_MS = 15_000;

// ── Tipos del dominio ────────────────────────────────────────────────────────

export type Health = {
  status: string;
  version: string;
  environment: string;
};

export type SourceKind =
  | "municipal_portal"
  | "state_transparency_portal"
  | "national_transparency_platform"
  | "gazette"
  | "other";

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

export type ProcessingStatus =
  | "pending"
  | "extracted"
  | "chunked"
  | "indexed"
  | "failed"
  | "needs_ocr";

export type Source = {
  id: string;
  slug: string;
  name: string;
  kind: SourceKind;
  municipality: string;
  official_url: string;
  description: string | null;
  is_active: boolean;
};

export type Document = {
  id: string;
  source_id: string;
  sha256: string;
  title: string | null;
  inferred_title?: string | null;
  document_type: DocumentType;
  municipality: string;
  year: number | null;
  jurisdiction: "municipal" | "state" | "federal" | "unknown";
  official_url: string;
  captured_url: string | null;
  captured_at: string;
  mime_type: string;
  storage_path: string;
  file_size: number;
  processing_status: ProcessingStatus;
  needs_ocr: boolean;
  version: number;
  is_current: boolean;
  superseded_by: string | null;
};

export type Chunk = {
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
};

export type SearchHit = {
  score: number;
  rerank_score?: number | null;
  chunk: Chunk;
  document: Document;
};

export type SearchResponse = {
  query: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimension: number;
  reranker: string | null;
  hits: SearchHit[];
};

export type ManifestSummary = {
  filename: string;
  source_slug: string;
  municipality: string | null;
  generated_at: string | null;
  document_count: number | null;
  pipeline_version: string | null;
};

export type StatsResponse = {
  documents_total: number;
  documents_by_status: { status: ProcessingStatus | string; count: number }[];
  chunks_total: number;
  unique_documents_by_sha256: number;
  sources_total: number;
  documents_by_source: { slug: string; count: number }[];
};

export type AskSource = {
  inferred_title?: string | null;
  title: string | null;
  url: string;
  page_start: number | null;
  page_end: number | null;
  jurisdiction: string; // municipal | state | federal | unknown
  excerpt?: string | null;
};

export type AskMode = "ciudadano" | "investigador";

/** Prior turn replayed to the agent for follow-up context (not persisted server-side). */
export type AskHistoryTurn = { question: string; answer: string };

export type AskResponse = {
  answer: string;
  mode: AskMode;
  model: string;
  iterations: number;
  sources: AskSource[];
};

export type DocumentFilters = {
  source_id?: string;
  municipality?: string;
  document_type?: DocumentType | "";
  year?: string;
  current_only?: boolean;
  limit?: number;
  offset?: number;
};

export type SearchParams = {
  q: string;
  limit?: number;
  municipality?: string;
  year?: number | null;
  document_type?: DocumentType | "";
  source_id?: string;
  local_only?: boolean;
};

/** Opciones por petición: cancelación y tiempo de espera. */
export type RequestOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
};

// ── Errores ──────────────────────────────────────────────────────────────────

/**
 * Error de API. A diferencia de un objeto plano, es un `Error` real: conserva
 * la traza y responde a `instanceof`. `status === 0` indica un fallo de
 * transporte (sin respuesta del servidor: red caída, timeout o cancelación).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors?: string[];

  constructor(status: number, message: string, fieldErrors?: string[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

const normalizeError = async (response: Response): Promise<ApiError> => {
  try {
    const body = await response.json();
    if (Array.isArray(body.detail)) {
      return new ApiError(
        response.status,
        "La API rechazó algunos parámetros.",
        body.detail.map((item: { msg?: string }) => item.msg ?? "Error de validación"),
      );
    }

    return new ApiError(response.status, String(body.detail ?? response.statusText));
  } catch {
    return new ApiError(
      response.status,
      response.statusText || "No se pudo leer la respuesta de la API.",
    );
  }
};

// ── Núcleo de transporte ─────────────────────────────────────────────────────

/**
 * Realiza una petición a `API_BASE + path` y devuelve el cuerpo tipado.
 * Aborta tras `timeoutMs` y respeta un `signal` externo. Cualquier respuesta
 * no exitosa o fallo de red se propaga como `ApiError`.
 */
const request = async <T>(path: string, init: RequestInit & { timeoutMs?: number } = {}): Promise<T> => {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, headers, ...rest } = init;

  const controller = new AbortController();
  const linkAbort = () => controller.abort();
  const timeoutId = setTimeout(linkAbort, timeoutMs);
  if (callerSignal) {
    if (callerSignal.aborted) controller.abort();
    else callerSignal.addEventListener("abort", linkAbort, { once: true });
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...rest,
      headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) {
      throw new ApiError(
        0,
        callerSignal?.aborted ? "Solicitud cancelada." : "La API tardó demasiado en responder.",
      );
    }
    throw new ApiError(0, "No se pudo conectar con la API.");
  } finally {
    clearTimeout(timeoutId);
    callerSignal?.removeEventListener("abort", linkAbort);
  }

  // ponytail: el timeout cubre la respuesta, no el streaming del cuerpo; basta para este uso.
  if (!response.ok) {
    throw await normalizeError(response);
  }

  if (response.headers.get("content-type")?.includes("application/json")) {
    return response.json() as Promise<T>;
  }

  return (await response.text()) as T;
};

const withQuery = (path: string, params: Record<string, string | number | boolean | undefined>) => {
  const urlParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      urlParams.set(key, String(value));
    }
  });

  const query = urlParams.toString();
  return query ? `${path}?${query}` : path;
};

// ── API pública ──────────────────────────────────────────────────────────────

export const api = {
  /** Estado del servicio: versión y entorno. */
  health: (options?: RequestOptions) => request<Health>("/health", options),

  /** Métricas agregadas del corpus (documentos, chunks, fuentes). */
  stats: (options?: RequestOptions) => request<StatsResponse>("/stats", options),

  sources: {
    /** Catálogo de fuentes oficiales. */
    list: (options?: RequestOptions) => request<Source[]>("/sources", options),
  },

  documents: {
    /** Lista documentos aplicando filtros (paginado, solo vigentes por defecto). */
    list: (filters: DocumentFilters = {}, options?: RequestOptions) =>
      request<Document[]>(
        withQuery("/documents", {
          ...filters,
          year: filters.year?.trim() || undefined,
          current_only: filters.current_only ?? true,
          limit: filters.limit ?? 10,
          offset: filters.offset ?? 0,
        }),
        options,
      ),

    /** Búsqueda semántica sobre los chunks indexados. */
    search: (body: SearchParams, options?: RequestOptions) =>
      request<SearchResponse>("/search", {
        ...options,
        method: "POST",
        body: JSON.stringify({
          ...body,
          document_type: body.document_type || undefined,
          year: body.year ?? undefined,
          local_only: body.local_only ?? true,
        }),
      }),
  },

  manifests: {
    /** Manifiestos de ingesta, opcionalmente filtrados por fuente. */
    list: (sourceSlug?: string, options?: RequestOptions) =>
      request<ManifestSummary[]>(withQuery("/manifests", { source_slug: sourceSlug }), options),
  },

  agent: {
    /**
     * Agente conversacional: pregunta en lenguaje natural → respuesta redactada
     * con citas. Latencia alta (varias búsquedas + LLM): timeout por defecto de
     * 180s, mayor al del backend. Devuelve 503 si el agente no está configurado.
     */
    ask: (
      question: string,
      mode: AskMode = "ciudadano",
      history: AskHistoryTurn[] = [],
      options?: RequestOptions,
    ) =>
      request<AskResponse>("/ask", {
        timeoutMs: 180_000,
        ...options,
        method: "POST",
        body: JSON.stringify({ question, mode, history }),
      }),
  },
};
