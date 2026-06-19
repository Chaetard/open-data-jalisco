import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import gsap from "gsap";
import { ArrowUpRight, Database, FileSearch, Loader2, RefreshCw, Search, XCircle } from "lucide-react";
import {
  api,
  ApiError,
  Document,
  DocumentType,
  ManifestSummary,
  SearchHit,
  Source,
  StatsResponse,
} from "./api";

const documentTypes: Array<{ value: DocumentType | ""; label: string }> = [
  { value: "", label: "Todos" },
  { value: "contract", label: "Contratos" },
  { value: "bidding", label: "Licitaciones" },
  { value: "award", label: "Adjudicaciones" },
  { value: "regulation", label: "Reglamentos" },
  { value: "minutes", label: "Actas" },
  { value: "budget", label: "Presupuesto" },
  { value: "financial_report", label: "Financieros" },
  { value: "other", label: "Otros" },
  { value: "unknown", label: "Sin clasificar" },
];

const typeLabel = (value: string) =>
  documentTypes.find((type) => type.value === value)?.label ?? value;

const statusLabels: Record<string, string> = {
  pending: "Pendiente",
  extracted: "Extraído",
  chunked: "Fragmentado",
  indexed: "Indexado",
  failed: "Fallido",
  needs_ocr: "Requiere OCR",
};

const statusColor: Record<string, string> = {
  indexed: "#1f5b43",
  extracted: "#5f7d92",
  chunked: "#7d6fa6",
  needs_ocr: "#7c581a",
  failed: "#9a3328",
  pending: "#aab2a8",
};

const formatDate = (value?: string | null) => {
  if (!value) return "Sin fecha";
  return new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" }).format(new Date(value));
};

const humanFileSize = (size?: number | null) => {
  if (!size) return "Sin peso";
  const units = ["B", "KB", "MB", "GB"];
  let current = size;
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

const asApiMessage = (error: unknown) => {
  if (error instanceof ApiError) {
    return error.fieldErrors?.length
      ? `${error.message} ${error.fieldErrors.join(" ")}`
      : error.message;
  }
  return "Ocurrió un error inesperado.";
};

export default function Explorer() {
  const [sources, setSources] = useState<Source[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [manifests, setManifests] = useState<ManifestSummary[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [query, setQuery] = useState("");
  const [searchHits, setSearchHits] = useState<SearchHit[]>([]);
  const [sourceFilter, setSourceFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<DocumentType | "">("");
  const [yearFilter, setYearFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [error, setError] = useState("");
  const pageRef = useRef<HTMLDivElement | null>(null);
  const resultsRef = useRef<HTMLDivElement | null>(null);

  const selectedSource = useMemo(
    () => sources.find((source) => source.id === sourceFilter),
    [sourceFilter, sources],
  );

  const indexedDocuments =
    stats?.documents_by_status.find((status) => status.status === "indexed")?.count ?? 0;

  const hasQuery = query.trim().length >= 2;

  const runSearch = useCallback(
    async (signal?: AbortSignal) => {
      if (query.trim().length < 2) {
        setSearchHits([]);
        return;
      }

      setSearching(true);
      setError("");
      try {
        const response = await api.documents.search(
          {
            q: query.trim(),
            limit: 8,
            source_id: sourceFilter || undefined,
            municipality: selectedSource?.municipality,
            document_type: typeFilter,
          },
          { signal },
        );
        setSearchHits(response.hits);
      } catch (requestError) {
        if (signal?.aborted) return; // búsqueda obsoleta cancelada: ignorar
        setSearchHits([]);
        setError(asApiMessage(requestError));
      } finally {
        if (!signal?.aborted) setSearching(false);
      }
    },
    [query, selectedSource?.municipality, sourceFilter, typeFilter],
  );

  const refreshDocuments = useCallback(async () => {
    setLoadingDocuments(true);
    setError("");
    try {
      const nextDocuments = await api.documents.list({
        source_id: sourceFilter || undefined,
        municipality: selectedSource?.municipality,
        document_type: typeFilter,
        year: yearFilter,
        limit: 20,
      });
      setDocuments(nextDocuments);
    } catch (requestError) {
      setError(asApiMessage(requestError));
      setDocuments([]);
    } finally {
      setLoadingDocuments(false);
    }
  }, [selectedSource?.municipality, sourceFilter, typeFilter, yearFilter]);

  useEffect(() => {
    const controller = new AbortController();

    const loadInitialData = async () => {
      setLoading(true);
      setError("");
      try {
        const [nextStats, nextSources, nextDocuments, nextManifests] = await Promise.all([
          api.stats({ signal: controller.signal }),
          api.sources.list({ signal: controller.signal }),
          api.documents.list({ limit: 20 }, { signal: controller.signal }),
          api.manifests.list(undefined, { signal: controller.signal }),
        ]);
        setStats(nextStats);
        setSources(nextSources);
        setDocuments(nextDocuments);
        setManifests(nextManifests);
      } catch (requestError) {
        if (controller.signal.aborted) return;
        setError(asApiMessage(requestError));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    void loadInitialData();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!pageRef.current || loading) return;
    // gsap.context + clearProps: evita que un tween interrumpido (re-render /
    // StrictMode) deje elementos en opacity:0 e inservibles.
    const ctx = gsap.context(() => {
      gsap.from("[data-enter]", {
        y: 12,
        opacity: 0,
        duration: 0.45,
        stagger: 0.04,
        ease: "power2.out",
        clearProps: "opacity,transform",
      });
    }, pageRef);
    return () => ctx.revert();
  }, [loading]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setSearchHits([]);
      return;
    }
    const controller = new AbortController();
    const timeout = window.setTimeout(() => void runSearch(controller.signal), 350);
    return () => {
      window.clearTimeout(timeout);
      controller.abort(); // cancela la petición en vuelo al teclear de nuevo
    };
  }, [query, runSearch]);

  useEffect(() => {
    if (!resultsRef.current || !searchHits.length) return;
    const ctx = gsap.context(() => {
      gsap.from("[data-result]", {
        y: 8,
        opacity: 0,
        duration: 0.28,
        stagger: 0.035,
        ease: "power2.out",
        clearProps: "opacity,transform",
      });
    }, resultsRef);
    return () => ctx.revert();
  }, [searchHits]);

  return (
    <div ref={pageRef} className="mx-auto max-w-7xl px-4 py-9 sm:px-6 lg:px-8">
      <section data-enter className="mb-8 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div className="max-w-2xl">
          <p className="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            <span className="h-px w-8 bg-line-strong" aria-hidden />
            Registro público municipal
          </p>
          <h1 className="mt-5 font-display text-[2.5rem] font-medium leading-[1.06] tracking-tight sm:text-[3.25rem]">
            Documentos públicos de Jalisco,
            <br className="hidden sm:block" /> sin solicitarlos por oficio.
          </h1>
          <p className="mt-4 max-w-xl text-[15px] leading-7 text-muted">
            Contratos, licitaciones, actas y presupuestos de los municipios, indexados con su URL
            de origen y su huella SHA-256 para verificar cada documento contra la fuente.
          </p>
        </div>
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-line bg-line sm:grid-cols-4 lg:w-auto">
          <Metric label="Fuentes" value={stats?.sources_total ?? sources.length} loading={loading && !stats} />
          <Metric label="Documentos" value={stats?.documents_total ?? 0} loading={loading && !stats} />
          <Metric label="Indexados" value={indexedDocuments} loading={loading && !stats} />
          <Metric label="Fragmentos" value={stats?.chunks_total ?? 0} loading={loading && !stats} />
        </dl>
      </section>

      <section data-enter className="mb-6 rounded-card border border-line bg-surface p-3 shadow-[0_1px_0_rgba(21,32,26,0.03)]">
        <form
          className="space-y-2.5"
          onSubmit={(event) => {
            event.preventDefault();
            void runSearch();
          }}
        >
          <div className="flex gap-2">
            <label className="relative flex-1">
              <span className="sr-only">Buscar documentos</span>
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-faint" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="h-12 w-full rounded-xl border border-line-strong bg-paper pl-11 pr-3 text-[15px] outline-none transition focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/15"
                placeholder="Ej. licitación de alumbrado en Tala"
              />
            </label>
            <button
              type="submit"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand-strong px-5 text-sm font-semibold text-white transition hover:bg-brand"
            >
              {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSearch className="h-4 w-4" />}
              <span className="hidden sm:inline">Buscar</span>
            </button>
          </div>

          <div className="grid gap-2 sm:grid-cols-[1fr_1fr_7rem_auto]">
            <select
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value)}
              className="h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm text-muted outline-none transition focus:border-brand focus:text-ink"
              aria-label="Filtrar por fuente"
            >
              <option value="">Todas las fuentes</option>
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name}
                </option>
              ))}
            </select>

            <select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as DocumentType | "")}
              className="h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm text-muted outline-none transition focus:border-brand focus:text-ink"
              aria-label="Filtrar por tipo documental"
            >
              {documentTypes.map((type) => (
                <option key={type.value || "all"} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>

            <input
              value={yearFilter}
              onChange={(event) => setYearFilter(event.target.value.replace(/\D/g, "").slice(0, 4))}
              className="h-10 rounded-lg border border-line-strong bg-surface px-3 text-sm outline-none transition focus:border-brand"
              placeholder="Año"
              inputMode="numeric"
              aria-label="Filtrar por año"
            />

            <button
              type="button"
              onClick={refreshDocuments}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-line-strong px-3 text-sm font-semibold text-muted transition hover:bg-paper hover:text-ink"
              aria-label="Actualizar documentos"
            >
              {loadingDocuments ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              <span className="hidden sm:inline">Actualizar</span>
            </button>
          </div>
        </form>
      </section>

      {error ? (
        <div
          data-enter
          role="alert"
          className="mb-6 flex items-start gap-2 rounded-card border border-danger-soft bg-danger-soft px-4 py-3 text-sm text-danger-ink"
        >
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <section data-enter ref={resultsRef} className="overflow-hidden rounded-card border border-line bg-surface">
            <SectionHeader
              title="Coincidencias"
              meta={
                searching
                  ? "Buscando…"
                  : hasQuery
                    ? `${searchHits.length} por afinidad`
                    : "Búsqueda por contenido"
              }
            />
            <div className="divide-y divide-line">
              {searching && !searchHits.length ? (
                <SkeletonResults />
              ) : searchHits.length ? (
                searchHits.map((hit) => (
                  <article data-result key={hit.chunk.id} className="p-5 transition-colors hover:bg-paper/60">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <h2 className="font-display text-[15px] font-semibold leading-6">
                          {hit.document.title}
                        </h2>
                        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted">
                          <span>{hit.document.municipality}</span>
                          <Dot />
                          <span>{hit.document.year ?? "s/a"}</span>
                          <Dot />
                          <span>{typeLabel(hit.document.document_type)}</span>
                        </p>
                      </div>
                      <div
                        className="shrink-0 text-right leading-none"
                        title="Afinidad semántica con tu búsqueda"
                      >
                        <span className="font-display text-xl tabular-nums">
                          {(hit.score * 100).toFixed(0)}
                        </span>
                        <span className="text-xs text-faint">%</span>
                        <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-faint">
                          afinidad
                        </p>
                      </div>
                    </div>
                    <p className="mt-3 line-clamp-3 text-sm leading-6 text-[#46524a]">{hit.chunk.text}</p>
                    <a
                      href={hit.document.official_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-brand transition hover:text-ink"
                    >
                      Abrir fuente oficial <ArrowUpRight className="h-4 w-4" />
                    </a>
                  </article>
                ))
              ) : (
                <EmptyState
                  loading={false}
                  text={
                    hasQuery
                      ? "Ningún documento coincide. Prueba otros términos o quita filtros."
                      : "Escribe dos o más letras para buscar dentro del texto."
                  }
                />
              )}
            </div>
          </section>

          <section data-enter className="overflow-hidden rounded-card border border-line bg-surface">
            <SectionHeader
              title="Documentos"
              meta={loadingDocuments ? "Actualizando…" : `Últimos ${documents.length}`}
            />
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-line text-[11px] font-semibold uppercase tracking-[0.08em] text-faint">
                  <tr>
                    <th className="px-5 py-3">Título</th>
                    <th className="px-5 py-3">Tipo</th>
                    <th className="px-5 py-3">Estado</th>
                    <th className="px-5 py-3 text-right">Año</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {loading || loadingDocuments ? (
                    <SkeletonRows />
                  ) : (
                    documents.map((document) => (
                      <tr key={document.id} className="align-top transition-colors hover:bg-paper/60">
                        <td className="max-w-[24rem] px-5 py-3.5">
                          <a
                            href={document.official_url}
                            target="_blank"
                            rel="noreferrer"
                            className="font-semibold transition hover:text-brand"
                          >
                            {document.title}
                          </a>
                          <p className="mt-1 text-xs text-muted">
                            {document.municipality} · {humanFileSize(document.file_size)}
                          </p>
                        </td>
                        <td className="px-5 py-3.5 text-muted">{typeLabel(document.document_type)}</td>
                        <td className="px-5 py-3.5">
                          <StatusMark status={document.processing_status} />
                        </td>
                        <td className="px-5 py-3.5 text-right tabular-nums text-muted">
                          {document.year ?? "s/a"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              {!loading && !loadingDocuments && !documents.length ? (
                <EmptyState loading={false} text="Sin documentos para estos filtros." />
              ) : null}
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <section data-enter className="overflow-hidden rounded-card border border-line bg-surface">
            <SectionHeader title="Fuentes oficiales" meta={loading ? "" : `${sources.length}`} />
            <div className="divide-y divide-line">
              {loading ? (
                <SkeletonList rows={3} />
              ) : sources.length ? (
                sources.map((source) => (
                  <article key={source.id} className="p-4 transition-colors hover:bg-paper/60">
                    <h2 className="text-sm font-semibold">{source.name}</h2>
                    <p className="mt-1 text-xs text-muted">
                      {source.municipality} · {source.kind.replace(/_/g, " ")}
                    </p>
                    <a
                      href={source.official_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-brand transition hover:text-ink"
                    >
                      Portal <ArrowUpRight className="h-4 w-4" />
                    </a>
                  </article>
                ))
              ) : (
                <EmptyState loading={false} text="Sin fuentes." />
              )}
            </div>
          </section>

          <section data-enter className="overflow-hidden rounded-card border border-line bg-surface">
            <SectionHeader title="El corpus en números" meta="" />
            {loading && !stats ? (
              <div className="p-4">
                <SkeletonList rows={4} bare />
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 border-b border-line p-4">
                  <Metric label="Sin duplicar" value={stats?.unique_documents_by_sha256 ?? 0} inline />
                  <Metric label="Fragmentos" value={stats?.chunks_total ?? 0} inline />
                </div>
                {stats?.documents_by_status.length ? (
                  <div className="divide-y divide-line">
                    {stats.documents_by_status.map((item) => (
                      <StatRow key={item.status} label={statusLabels[item.status] ?? item.status} value={item.count} />
                    ))}
                  </div>
                ) : (
                  <EmptyState loading={false} text="Sin estadísticas." />
                )}
                {stats?.documents_by_source.length ? (
                  <div className="border-t border-line p-4">
                    <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
                      Por fuente
                    </p>
                    <div className="space-y-1">
                      {stats.documents_by_source.map((source) => (
                        <StatRow key={source.slug} label={source.slug} value={source.count} compact />
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            )}
          </section>

          <section data-enter className="overflow-hidden rounded-card border border-line bg-surface">
            <SectionHeader title="Manifiestos de integridad" meta={loading ? "" : `${manifests.length}`} />
            <div className="divide-y divide-line">
              {loading ? (
                <SkeletonList rows={3} />
              ) : manifests.length ? (
                manifests.slice(0, 6).map((manifest) => (
                  <article key={manifest.filename} className="p-4">
                    <h2 className="text-sm font-semibold">{manifest.source_slug}</h2>
                    <p className="mt-1 text-xs text-muted">
                      {manifest.document_count} docs · {manifest.pipeline_version}
                    </p>
                    <p className="mt-2 text-xs text-faint">{formatDate(manifest.generated_at)}</p>
                  </article>
                ))
              ) : (
                <EmptyState loading={false} text="Sin manifiestos." />
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

function Dot() {
  return <span className="text-line-strong">·</span>;
}

function Metric({
  label,
  value,
  loading = false,
  inline = false,
}: {
  label: string;
  value: number;
  loading?: boolean;
  inline?: boolean;
}) {
  if (inline) {
    return (
      <div>
        <p className="font-display text-xl font-semibold tabular-nums">{value.toLocaleString("es-MX")}</p>
        <p className="text-xs text-muted">{label}</p>
      </div>
    );
  }
  return (
    <div className="bg-surface px-4 py-3 text-right sm:min-w-[7rem]">
      {loading ? (
        <div className="ml-auto h-7 w-14 skeleton rounded-md" />
      ) : (
        <p className="font-display text-2xl font-semibold tabular-nums leading-7">
          {value.toLocaleString("es-MX")}
        </p>
      )}
      <p className="mt-1 text-[11px] uppercase tracking-[0.1em] text-faint">{label}</p>
    </div>
  );
}

function SectionHeader({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-3.5">
      <h2 className="font-display text-base font-semibold">{title}</h2>
      {meta ? <span className="text-xs text-muted">{meta}</span> : null}
    </div>
  );
}

function StatusMark({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-sm text-muted">
      <span
        className="h-1.5 w-1.5 shrink-0 rounded-full"
        style={{ background: statusColor[status] ?? "#b8c0b6" }}
        aria-hidden
      />
      {statusLabels[status] ?? status}
    </span>
  );
}

function StatRow({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: number;
  compact?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between gap-4 ${compact ? "py-1" : "px-5 py-2.5"}`}>
      <span className="truncate text-sm text-[#46524a]">{label}</span>
      <span className="shrink-0 text-sm font-semibold tabular-nums">{value.toLocaleString("es-MX")}</span>
    </div>
  );
}

function EmptyState({ loading, text }: { loading: boolean; text: string }) {
  return (
    <div className="flex items-center gap-2 p-5 text-sm text-muted">
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4 text-faint" />}
      {loading ? "Cargando…" : text}
    </div>
  );
}

function SkeletonResults() {
  return (
    <>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="space-y-3 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="h-4 w-2/3 skeleton rounded-md" />
            <div className="h-6 w-10 skeleton rounded-md" />
          </div>
          <div className="h-3 w-1/3 skeleton rounded-md" />
          <div className="space-y-2">
            <div className="h-3 w-full skeleton rounded-md" />
            <div className="h-3 w-11/12 skeleton rounded-md" />
            <div className="h-3 w-4/5 skeleton rounded-md" />
          </div>
        </div>
      ))}
    </>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, index) => (
        <tr key={index}>
          <td className="px-5 py-3.5">
            <div className="h-3.5 w-3/4 skeleton rounded-md" />
            <div className="mt-2 h-3 w-1/3 skeleton rounded-md" />
          </td>
          <td className="px-5 py-3.5">
            <div className="h-3.5 w-16 skeleton rounded-md" />
          </td>
          <td className="px-5 py-3.5">
            <div className="h-6 w-20 skeleton rounded-md" />
          </td>
          <td className="px-5 py-3.5">
            <div className="ml-auto h-3.5 w-10 skeleton rounded-md" />
          </td>
        </tr>
      ))}
    </>
  );
}

function SkeletonList({ rows, bare = false }: { rows: number; bare?: boolean }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className={bare ? "py-2" : "p-4"}>
          <div className="h-3.5 w-1/2 skeleton rounded-md" />
          <div className="mt-2 h-3 w-2/3 skeleton rounded-md" />
        </div>
      ))}
    </>
  );
}
