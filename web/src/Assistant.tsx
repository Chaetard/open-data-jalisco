import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowUp,
  ArrowUpRight,
  Database,
  FileText,
  Link2,
  PanelRightClose,
  PanelRightOpen,
  PowerOff,
  RotateCcw,
  Sparkles,
  Square,
} from "lucide-react";
import { Marked } from "marked";
import { api, ApiError, AskResponse, AskSource } from "./api";

type Turn = {
  id: number;
  question: string;
  status: "thinking" | "done" | "error";
  answer?: string;
  model?: string;
  iterations?: number;
  sources?: AskSource[];
  error?: string;
};

type ResourceItem = {
  key: string;
  title: string | null;
  url: string;
  jurisdiction: string;
  pages: string[];
  turnNumbers: number[];
  count: number;
};

const suggestions = [
  "¿Qué requisitos piden para una licencia de construcción?",
  "¿Cómo está distribuido el presupuesto de egresos 2025?",
  "¿Qué dice el reglamento sobre el comité de transparencia?",
];

const thinkingMessages = [
  "Buscando en los documentos del municipio…",
  "Leyendo reglamentos y actas…",
  "Cotejando contra las fuentes oficiales…",
  "Redactando una respuesta con citas…",
];

const jurisdictionLabel: Record<string, string> = {
  municipal: "Municipal",
  state: "Estatal",
  federal: "Federal",
  unknown: "—",
};

const htmlEscapeMap: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (char) => htmlEscapeMap[char]);

const safeHref = (href: string) => {
  const trimmed = href.trim();
  if (/^(https?:|mailto:)/i.test(trimmed) || trimmed.startsWith("/") || trimmed.startsWith("#")) {
    return trimmed;
  }
  return "";
};

const assistantMarkdown = new Marked({
  gfm: true,
  breaks: true,
  renderer: {
    html({ text }) {
      return escapeHtml(text);
    },
    link({ href, title, tokens }) {
      const label = this.parser.parseInline(tokens);
      const cleanHref = safeHref(href);
      if (!cleanHref) return label;
      const cleanTitle = title ? ` title="${escapeHtml(title)}"` : "";
      return `<a href="${escapeHtml(cleanHref)}" target="_blank" rel="noreferrer"${cleanTitle}>${label}</a>`;
    },
    image({ text }) {
      return escapeHtml(text);
    },
  },
});

const renderMarkdown = (markdown: string) => {
  try {
    return assistantMarkdown.parse(markdown, { async: false });
  } catch {
    const paragraphs = escapeHtml(markdown)
      .split(/\n{2,}/)
      .map((part) => part.replace(/\n/g, "<br />"));
    return paragraphs.map((part) => `<p>${part}</p>`).join("");
  }
};

const sourcePageLabel = (source: AskSource) => {
  if (source.page_start == null) return null;
  if (source.page_end != null && source.page_end !== source.page_start) {
    return `pp. ${source.page_start}–${source.page_end}`;
  }
  return `pág. ${source.page_start}`;
};

const sourceKey = (source: AskSource) => source.url.trim().toLowerCase() || `${source.title ?? "sin-titulo"}`;

const compactList = (items: string[], visible = 2) => {
  if (items.length <= visible) return items.join(", ");
  return `${items.slice(0, visible).join(", ")} +${items.length - visible}`;
};

const collectResources = (turns: Turn[]) => {
  const resources = new Map<string, ResourceItem>();

  turns.forEach((turn, turnIndex) => {
    if (turn.status !== "done") return;

    turn.sources?.forEach((source) => {
      const key = sourceKey(source);
      const page = sourcePageLabel(source);
      const turnNumber = turnIndex + 1;
      const current = resources.get(key);

      if (!current) {
        resources.set(key, {
          key,
          title: source.title,
          url: source.url,
          jurisdiction: source.jurisdiction,
          pages: page ? [page] : [],
          turnNumbers: [turnNumber],
          count: 1,
        });
        return;
      }

      current.count += 1;
      if (!current.title && source.title) current.title = source.title;
      if (page && !current.pages.includes(page)) current.pages.push(page);
      if (!current.turnNumbers.includes(turnNumber)) current.turnNumbers.push(turnNumber);
    });
  });

  return Array.from(resources.values());
};

const REDUCED =
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const asAskError = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 0) return "La consulta tardó demasiado o se perdió la conexión.";
    return error.fieldErrors?.length ? error.fieldErrors.join(" ") : error.message;
  }
  return "El asistente tuvo un problema. Intenta de nuevo.";
};

const isAssistantMockEnabled = () => {
  if (!import.meta.env.DEV || typeof window === "undefined") return false;
  const search = new URLSearchParams(window.location.search);
  const hashQuery = window.location.hash.includes("?")
    ? new URLSearchParams(window.location.hash.slice(window.location.hash.indexOf("?") + 1))
    : null;
  return search.get("mock") === "1" || hashQuery?.get("mock") === "1";
};

const waitForMock = (signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new ApiError(0, "Solicitud cancelada."));
      return;
    }
    const timeout = window.setTimeout(resolve, 650);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeout);
        reject(new ApiError(0, "Solicitud cancelada."));
      },
      { once: true },
    );
  });

const mockSources: AskSource[] = [
  {
    title: "Reglamento municipal de prueba",
    url: "https://example.com/reglamento-municipal.pdf",
    page_start: 12,
    page_end: 14,
    jurisdiction: "municipal",
  },
  {
    title: "Acta de comision de prueba",
    url: "https://example.com/acta-comision.pdf",
    page_start: 3,
    page_end: null,
    jurisdiction: "municipal",
  },
];

const mockAsk = async (question: string, signal: AbortSignal): Promise<AskResponse> => {
  await waitForMock(signal);
  return {
    model: "mock-dev",
    iterations: 1,
    sources: mockSources,
    answer: `Respuesta mock para probar el render sin gastar agente real.

Pregunta recibida: **${question}**

Esta respuesta incluye texto largo, listas, citas y una tabla ancha para revisar que el layout no se apachurre y que el scroll horizontal funcione bien.

| Nombre de la persona | Cargo | Area u organo | Documento fuente | Pag. | Texto exacto | Reglamento / Articulo | Facultad o atribucion | Tipo de evidencia | Certeza |
|---|---|---|---|---:|---|---|---|---|---|
| Martina Castillo Robles | Presidente / integrante | Comision edilicia de transparencia y archivos | Reglamento municipal de prueba | 2 | "Participa en sesiones ordinarias y extraordinarias con voz y voto." | Articulo 14, fraccion II | Asistencia, deliberacion y seguimiento de acuerdos | Acta y reglamento | Alta |
| Jose Luis Hernandez Mendoza | Secretario tecnico | Unidad de transparencia | Manual de organizacion de prueba | 8 | "Coordina la recepcion, turnado y respuesta de solicitudes." | Articulo 21 | Gestion documental y control de plazos | Manual administrativo | Media |
| Direccion de Padron y Licencias | Organo administrativo | Tesoreria municipal | Programa operativo anual de prueba | 17 | "Integra padrones, permisos y verificaciones en una sola base documental." | Linea de accion 3.2 | Integracion de registros administrativos | Programa operativo | Alta |

1. La tabla debe conservar columnas legibles.
2. Si no cabe en el ancho del mensaje, debe aparecer scroll horizontal.
3. El cuadro de texto debe volver a su altura normal despues de enviar.`,
  };
};

export default function Assistant() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState("");
  const [loading, setLoading] = useState(false);
  const [agentAvailable, setAgentAvailable] = useState(true);
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const resources = useMemo(() => collectResources(turns), [turns]);
  const mockMode = useMemo(() => isAssistantMockEnabled(), []);

  const idRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const resetInputHeight = useCallback(() => {
    window.requestAnimationFrame(() => {
      if (inputRef.current) inputRef.current.style.height = "auto";
    });
  }, []);

  const runAsk = useCallback(async (id: number, question: string) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, status: "thinking", error: undefined } : t)));
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    try {
      const res: AskResponse = mockMode
        ? await mockAsk(question, controller.signal)
        : await api.agent.ask(question, { signal: controller.signal });
      setTurns((prev) =>
        prev.map((t) =>
          t.id === id
            ? {
                ...t,
                status: "done",
                answer: res.answer,
                model: res.model,
                iterations: res.iterations,
                sources: res.sources,
              }
            : t,
        ),
      );
    } catch (error) {
      if (controller.signal.aborted) {
        setTurns((prev) =>
          prev.map((t) => (t.id === id ? { ...t, status: "error", error: "Consulta cancelada." } : t)),
        );
        return;
      }
      if (error instanceof ApiError && error.status === 503) {
        setAgentAvailable(false);
        setTurns((prev) => prev.filter((t) => t.id !== id));
        return;
      }
      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, status: "error", error: asAskError(error) } : t)),
      );
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setLoading(false);
      }
    }
  }, [mockMode]);

  const submit = useCallback(
    (raw: string) => {
      if (loading) return;
      const question = raw.trim();
      if (question.length < 3) {
        setInputError("Escribe una pregunta de al menos 3 caracteres.");
        return;
      }
      setInputError("");
      setInput("");
      resetInputHeight();
      const id = (idRef.current += 1);
      setTurns((prev) => [...prev, { id, question, status: "thinking" }]);
      void runAsk(id, question);
    },
    [loading, resetInputHeight, runAsk],
  );

  const stop = () => controllerRef.current?.abort();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="tech-grid min-h-0 flex-1 overflow-y-auto pb-44">
        <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
          {turns.length === 0 ? (
            <Intro onPick={submit} />
          ) : (
            <div className="space-y-10">
              {turns.map((turn) => (
                <TurnBlock key={turn.id} turn={turn} onRetry={() => runAsk(turn.id, turn.question)} disabled={loading} />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <ResourcesPanel
        resources={resources}
        loading={loading}
        open={resourcesOpen}
        onToggle={() => setResourcesOpen((open) => !open)}
      />

      <div className="assistant-composer-dock pointer-events-none fixed inset-x-0 bottom-0 z-40 pb-4">
        <div className="relative z-10 mx-auto w-full max-w-5xl px-4 sm:px-6">
          {!agentAvailable ? (
            <Unavailable onRetry={() => setAgentAvailable(true)} />
          ) : (
            <>
              <div className="pointer-events-auto flex items-end gap-2 rounded-2xl border border-line-strong bg-surface/95 p-2 shadow-[0_18px_45px_rgba(21,32,26,0.16)] backdrop-blur focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/15">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submit(input);
                    }
                  }}
                  onInput={(event) => {
                    const el = event.currentTarget;
                    el.style.height = "auto";
                    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
                  }}
                  rows={1}
                  placeholder="Pregunta sobre trámites, presupuestos, reglamentos…"
                  className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-5 outline-none placeholder:text-faint"
                />
                {loading ? (
                  <button
                    type="button"
                    onClick={stop}
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-line-strong text-muted transition hover:bg-paper hover:text-ink"
                    aria-label="Detener"
                    title="Detener"
                  >
                    <Square className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => submit(input)}
                    disabled={input.trim().length < 3}
                    className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-strong text-white transition enabled:hover:bg-brand disabled:opacity-40"
                    aria-label="Preguntar"
                    title="Preguntar"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                )}
              </div>
              <div className="pointer-events-auto mt-1.5 flex items-center justify-between px-1">
                <span className="text-xs text-danger-ink">{inputError}</span>
                <span className="font-mono text-[11px] text-faint">
                  {mockMode ? "Modo mock dev · " : ""}Enter envía · Shift+Enter salto de línea
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Intro({ onPick }: { onPick: (question: string) => void }) {
  return (
    <div className="mx-auto max-w-xl py-10 text-center">
      <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand-strong text-white">
        <Sparkles className="h-6 w-6" />
      </span>
      <h1 className="mt-5 font-display text-3xl font-medium tracking-tight sm:text-4xl">
        Pregúntale a los documentos
      </h1>
      <p className="mx-auto mt-3 max-w-md text-[15px] leading-7 text-muted">
        El asistente lee los documentos públicos por ti, redacta una respuesta en español y la
        respalda con las fuentes oficiales que citó.
      </p>
      <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.16em] text-faint">
        agente · recuperación sobre documentos públicos
      </p>

      <div className="mt-8 space-y-2 text-left">
        {suggestions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className="group flex w-full items-center gap-3 rounded-xl border border-line bg-surface px-4 py-3 text-left text-sm transition hover:-translate-y-0.5 hover:border-line-strong"
          >
            <Sparkles className="h-4 w-4 shrink-0 text-brand" />
            <span className="flex-1">{question}</span>
            <ArrowUp className="h-4 w-4 shrink-0 rotate-45 text-faint transition group-hover:text-brand" />
          </button>
        ))}
      </div>
    </div>
  );
}

function TurnBlock({ turn, onRetry, disabled }: { turn: Turn; onRetry: () => void; disabled: boolean }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-line-strong font-mono text-[11px] text-faint">
          Tú
        </span>
        <p className="font-display text-base leading-6">{turn.question}</p>
      </div>

      {turn.status === "thinking" ? (
        <ThinkingIndicator />
      ) : (
        <div className="assistant-answer-float">
          {turn.status === "error" ? (
          <ErrorBlock message={turn.error ?? "Error."} onRetry={onRetry} disabled={disabled} />
        ) : (
          <AnswerBlock turn={turn} />
        )}
        </div>
      )}
    </div>
  );
}

function ThinkingIndicator() {
  const [messageIndex, setMessageIndex] = useState(0);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const message = REDUCED
      ? undefined
      : window.setInterval(() => setMessageIndex((i) => (i + 1) % thinkingMessages.length), 3500);
    const tick = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => {
      if (message) window.clearInterval(message);
      window.clearInterval(tick);
    };
  }, []);

  return (
    <div className="thinking-float">
      <div className="thinking-orb" aria-hidden>
        <Database className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-3 text-sm">
          <span className="truncate font-medium text-ink">{thinkingMessages[messageIndex]}</span>
          <span className="ml-auto shrink-0 font-mono text-xs tabular-nums text-faint">{seconds}s</span>
        </div>
        <div className="thinking-bar mt-3 h-1 rounded-full bg-line" />
      </div>
    </div>
  );
}

function AnswerBlock({ turn }: { turn: Turn }) {
  const { shown, done } = useTypewriter(turn.answer ?? "");
  const sources = turn.sources ?? [];
  const renderedAnswer = useMemo(() => renderMarkdown(shown), [shown]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-faint">
        <Sparkles className="h-3.5 w-3.5 text-brand" />
        <span className="font-mono">Asistente</span>
        {turn.model ? (
          <>
            <Sep />
            <span className="font-mono">{turn.model}</span>
          </>
        ) : null}
        {typeof turn.iterations === "number" ? (
          <>
            <Sep />
            <span className="font-mono">
              {turn.iterations} {turn.iterations === 1 ? "iteración" : "iteraciones"}
            </span>
          </>
        ) : null}
      </div>

      <div className="assistant-md" dangerouslySetInnerHTML={{ __html: renderedAnswer }} />
      {!done ? <span className="caret mt-1" aria-hidden /> : null}

      {done && sources.length ? (
        <div className="mt-5">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
            Fuentes citadas · {sources.length}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {sources.map((source, index) => (
              <SourceCard key={`${source.url}-${index}`} index={index + 1} source={source} />
            ))}
          </div>
        </div>
      ) : null}

      {done && !sources.length ? (
        <p className="mt-4 font-mono text-xs text-faint">Respuesta sin documento citado.</p>
      ) : null}
    </div>
  );
}

function SourceCard({ index, source }: { index: number; source: AskSource }) {
  const page = sourcePageLabel(source);

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noreferrer"
      className="group flex gap-3 rounded-xl border border-line bg-paper p-3.5 transition hover:-translate-y-0.5 hover:border-line-strong hover:bg-surface"
    >
      <span className="mt-0.5 shrink-0 font-mono text-xs text-faint">[{index}]</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold transition group-hover:text-brand">
          {source.title ?? "Documento sin título"}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] uppercase tracking-wider text-faint">
          <span>{jurisdictionLabel[source.jurisdiction] ?? source.jurisdiction}</span>
          {page ? (
            <>
              <Sep />
              <span>{page}</span>
            </>
          ) : null}
        </span>
      </span>
      <ArrowUpRight className="h-4 w-4 shrink-0 text-faint transition group-hover:text-brand" />
    </a>
  );
}

function ResourcesPanel({
  resources,
  loading,
  open,
  onToggle,
}: {
  resources: ResourceItem[];
  loading: boolean;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <aside className={`resources-sidebar ${open ? "is-open" : ""}`} aria-label="Recursos encontrados">
      <button
        type="button"
        onClick={onToggle}
        className="resources-sidebar-toggle"
        aria-label={open ? "Cerrar recursos encontrados" : "Abrir recursos encontrados"}
        title={open ? "Cerrar" : "Abrir recursos encontrados"}
      >
        {open ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
        {!open && resources.length ? <span className="resources-dock-count">{resources.length}</span> : null}
      </button>

      <div className="flex h-full min-h-0 flex-col p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand">
              <FileText className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h2 className="font-display text-base font-semibold leading-6">Recursos encontrados</h2>
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
                {resources.length} {resources.length === 1 ? "fuente" : "fuentes"}
              </p>
            </div>
          </div>
        </div>
        {loading ? <div className="mt-3 h-1 overflow-hidden rounded-full bg-line"><span className="resource-loading-bar" /></div> : null}

        {resources.length ? (
          <div className="mt-4 min-h-0 flex-1 divide-y divide-line overflow-y-auto pr-1">
            {resources.map((resource, index) => (
              <ResourceLink key={resource.key} resource={resource} index={index + 1} />
            ))}
          </div>
        ) : (
          <div className="mt-5 rounded-xl border border-dashed border-line-strong bg-paper/70 px-3 py-4 text-center">
            <Link2 className="mx-auto h-4 w-4 text-faint" />
            <p className="mt-2 text-sm text-muted">Sin recursos todavía.</p>
          </div>
        )}
      </div>
    </aside>
  );
}

function ResourceLink({ resource, index }: { resource: ResourceItem; index: number }) {
  const turns =
    resource.turnNumbers.length === 1
      ? `Respuesta ${resource.turnNumbers[0]}`
      : `Respuestas ${compactList(resource.turnNumbers.map(String), 3)}`;
  const pageSummary = resource.pages.length ? compactList(resource.pages) : "Sin página";

  return (
    <a
      href={resource.url}
      target="_blank"
      rel="noreferrer"
      className="group flex gap-3 py-3 transition hover:text-brand"
      title="Abrir recurso"
    >
      <span className="mt-0.5 shrink-0 font-mono text-xs text-faint">R{index}</span>
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 text-sm font-semibold leading-5 text-ink transition group-hover:text-brand">
          {resource.title ?? "Documento sin título"}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] uppercase tracking-wider text-faint">
          <span>{jurisdictionLabel[resource.jurisdiction] ?? resource.jurisdiction}</span>
          <Sep />
          <span>{pageSummary}</span>
        </span>
        <span className="mt-1 block text-xs text-faint">
          {turns}
          {resource.count > 1 ? ` · ${resource.count} citas` : ""}
        </span>
      </span>
      <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-faint transition group-hover:text-brand" />
    </a>
  );
}

function ErrorBlock({ message, onRetry, disabled }: { message: string; onRetry: () => void; disabled: boolean }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-2 text-sm text-danger-ink">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{message}</span>
      </div>
      <button
        type="button"
        onClick={onRetry}
        disabled={disabled}
        className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-lg border border-line-strong px-3 py-1.5 text-sm font-semibold text-muted transition enabled:hover:bg-paper enabled:hover:text-ink disabled:opacity-40 sm:self-auto"
      >
        <RotateCcw className="h-4 w-4" /> Reintentar
      </button>
    </div>
  );
}

function Unavailable({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="pointer-events-auto flex flex-col items-center gap-2 rounded-2xl border border-line-strong bg-surface/95 px-4 py-3 text-center shadow-[0_18px_45px_rgba(21,32,26,0.16)] backdrop-blur sm:flex-row sm:justify-center sm:gap-3 sm:text-left">
      <PowerOff className="h-4 w-4 shrink-0 text-warn-ink" />
      <span className="text-sm text-muted">
        El asistente no está disponible en esta instancia.{" "}
        <button type="button" onClick={onRetry} className="font-semibold text-brand transition hover:text-ink">
          Reintentar
        </button>
      </span>
    </div>
  );
}

function Sep() {
  return <span className="text-line-strong">·</span>;
}

// Efecto máquina de escribir. ponytail: revela ~220 ticks (≈3.5s máx); instantáneo
// con prefers-reduced-motion. Cosmético — el backend no transmite parcial.
function useTypewriter(text: string) {
  const [count, setCount] = useState(REDUCED ? text.length : 0);

  useEffect(() => {
    if (REDUCED) {
      setCount(text.length);
      return;
    }
    setCount(0);
    const perTick = Math.max(2, Math.ceil(text.length / 220));
    let revealed = 0;
    const id = window.setInterval(() => {
      revealed += perTick;
      setCount(Math.min(text.length, revealed));
      if (revealed >= text.length) window.clearInterval(id);
    }, 16);
    return () => window.clearInterval(id);
  }, [text]);

  return { shown: text.slice(0, count), done: count >= text.length };
}
