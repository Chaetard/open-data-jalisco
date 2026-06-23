import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpRight,
  Check,
  Database,
  FileText,
  Link2,
  MapPin,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  PowerOff,
  RotateCcw,
  Search,
  Settings,
  Sparkles,
  Square,
  type LucideIcon,
} from "lucide-react";
import { Marked } from "marked";
import { Link } from "react-router-dom";
import { api, ApiError, AskMode, AskResponse, AskSource, AskStep, Source } from "./api";

type Turn = {
  id: number;
  question: string;
  mode: AskMode;
  status: "thinking" | "done" | "error";
  answer?: string;
  model?: string;
  iterations?: number;
  sources?: AskSource[];
  error?: string;
  // Actividad real del agente recibida por streaming mientras piensa.
  activity?: AskStep[];
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

const suggestedQuestions = [
  "¿Qué requisitos piden para una licencia de construcción?",
  "¿Qué documentos hablan de obras públicas recientes?",
  "¿Qué reglas aplican para transparencia y acceso a información?",
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

const modeLabel: Record<AskMode, string> = {
  ciudadano: "Ciudadano",
  investigador: "Técnico",
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

const pntMentionPattern =
  /\bPNT\b|Plataforma Nacional de Transparencia|Panel Nacional de Transparencia/i;

const notifyPntMention = (text: string) => {
  if (typeof window === "undefined" || !pntMentionPattern.test(text)) return;
  window.dispatchEvent(new Event("odj:pnt-mentioned"));
};

const sourcePageLabel = (source: AskSource) => {
  if (source.page_start == null) return null;
  if (source.page_end != null && source.page_end !== source.page_start) {
    return `pp. ${source.page_start}–${source.page_end}`;
  }
  return `pág. ${source.page_start}`;
};

const sourceTitle = (source: AskSource) => source.inferred_title || source.title || "Documento sin título";

const sourceKey = (source: AskSource) => source.url.trim().toLowerCase() || sourceTitle(source);

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
          title: sourceTitle(source),
          url: source.url,
          jurisdiction: source.jurisdiction,
          pages: page ? [page] : [],
          turnNumbers: [turnNumber],
          count: 1,
        });
        return;
      }

      current.count += 1;
      if (!current.title) current.title = sourceTitle(source);
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
    if (error.status === 502) return "El modelo tuvo un problema. Intenta de nuevo.";
    if (error.status === 503) return "Asistente no disponible.";
    return error.fieldErrors?.length ? error.fieldErrors.join(" ") : error.message;
  }
  return "El asistente tuvo un problema. Intenta de nuevo.";
};

const isAssistantMockEnabled = () => {
  if (typeof window === "undefined") return false;
  const localHost = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
  if (!import.meta.env.DEV && !localHost) return false;
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
    inferred_title: "Reglamento municipal de prueba",
    title: "Reglamento municipal de prueba",
    url: "https://example.com/reglamento-municipal.pdf",
    page_start: 12,
    page_end: 14,
    jurisdiction: "municipal",
    excerpt: "Participa en sesiones ordinarias y extraordinarias con voz y voto.",
  },
  {
    inferred_title: "Acta de comisión de prueba",
    title: "Acta de comision de prueba",
    url: "https://example.com/acta-comision.pdf",
    page_start: 3,
    page_end: null,
    jurisdiction: "municipal",
    excerpt: "Coordina la recepción, turnado y respuesta de solicitudes.",
  },
];

const mockMunicipalSources: Source[] = [
  {
    id: "mock-tala",
    slug: "tala",
    name: "Portal municipal de Tala",
    kind: "municipal_portal",
    municipality: "Tala",
    official_url: "https://example.com/tala",
    description: null,
    is_active: true,
  },
  {
    id: "mock-tequila",
    slug: "tequila",
    name: "Portal municipal de Tequila",
    kind: "municipal_portal",
    municipality: "Tequila",
    official_url: "https://example.com/tequila",
    description: null,
    is_active: true,
  },
  {
    id: "mock-zapopan",
    slug: "zapopan",
    name: "Portal municipal de Zapopan",
    kind: "municipal_portal",
    municipality: "Zapopan",
    official_url: "https://example.com/zapopan",
    description: null,
    is_active: true,
  },
  {
    id: "mock-guadalajara",
    slug: "guadalajara",
    name: "Portal municipal de Guadalajara",
    kind: "municipal_portal",
    municipality: "Guadalajara",
    official_url: "https://example.com/guadalajara",
    description: null,
    is_active: true,
  },
  {
    id: "mock-tonala",
    slug: "tonala",
    name: "Portal municipal de Tonala",
    kind: "municipal_portal",
    municipality: "Tonala",
    official_url: "https://example.com/tonala",
    description: null,
    is_active: true,
  },
  {
    id: "mock-tlajomulco",
    slug: "tlajomulco",
    name: "Portal municipal de Tlajomulco",
    kind: "municipal_portal",
    municipality: "Tlajomulco",
    official_url: "https://example.com/tlajomulco",
    description: null,
    is_active: true,
  },
];

const mockAsk = async (question: string, mode: AskMode, signal: AbortSignal): Promise<AskResponse> => {
  await waitForMock(signal);
  return {
    model: "mock-dev",
    iterations: 1,
    mode,
    sources: mockSources,
    answer: `Respuesta mock para probar el render sin gastar agente real.

Pregunta recibida: **${question}**

**Prueba PNT:** si el documento no aparece en ODJ, recomienda abrir la Plataforma Nacional de Transparencia (PNT) con una solicitud clara y acotada. Esta frase existe para probar el brillo del botón PNT sin gastar tokens del agente real.

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

// Emula el streaming real emitiendo unos pasos antes de la respuesta mock, para
// poder afinar la UI de actividad sin gastar el agente.
const mockAskStream = async (
  question: string,
  mode: AskMode,
  signal: AbortSignal,
  onStep: (step: AskStep) => void,
): Promise<AskResponse> => {
  const searchLabel = `Buscando «${question.slice(0, 40)}»`;
  onStep({ type: "step", status: "run", tool: "search_documents", label: searchLabel });
  await waitForMock(signal);
  onStep({ type: "step", status: "done", tool: "search_documents", label: searchLabel, count: 8 });
  const readLabel = "Leyendo reglamento-municipal.pdf";
  onStep({ type: "step", status: "run", tool: "read_document", label: readLabel });
  await waitForMock(signal);
  onStep({ type: "step", status: "done", tool: "read_document", label: readLabel, count: null });
  return mockAsk(question, mode, signal);
};

// Persistencia por sesión (sobrevive recargas, se borra al cerrar la pestaña —
// que es justo el alcance de "sesión"). No hay backend: el contexto que ve el
// agente se deriva de estos `turns` al enviar el historial.
const CHAT_STORAGE_KEY = "odj.chat";
// El agente sólo usa los últimos turnos; recortar acota el tamaño en storage.
const MAX_PERSISTED_TURNS = 30;

const loadTurns = (): Turn[] => {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Un turno "thinking" restaurado ya no tiene petición viva detrás (el
    // AbortController murió con la página): márcalo como error para que la UI no
    // se quede con el spinner eterno.
    return (parsed as Turn[]).map((t) =>
      t.status === "thinking"
        ? { ...t, status: "error", error: "Se interrumpió al recargar. Reintenta." }
        : t,
    );
  } catch {
    return [];
  }
};

const saveTurns = (turns: Turn[]) => {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(
      CHAT_STORAGE_KEY,
      JSON.stringify(turns.slice(-MAX_PERSISTED_TURNS)),
    );
  } catch {
    // Cuota o serialización: nunca debe tumbar el chat.
  }
};

export default function Assistant() {
  const [turns, setTurns] = useState<Turn[]>(loadTurns);
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState("");
  const [mode, setMode] = useState<AskMode>("ciudadano");
  const [sources, setSources] = useState<Source[]>([]);
  const [pendingSuggestion, setPendingSuggestion] = useState("");
  const [municipalityFilter, setMunicipalityFilter] = useState("");
  // Pregunta escrita en espera de decidir alcance (todos vs. un municipio).
  const [pendingScopeQuestion, setPendingScopeQuestion] = useState("");
  // Cacheado de sesión: una vez que el usuario eligió alcance, no se vuelve a preguntar.
  const [scopeAsked, setScopeAsked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [agentAvailable, setAgentAvailable] = useState(true);
  const [resourcesOpen, setResourcesOpen] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [showScrollDown, setShowScrollDown] = useState(false);
  const resources = useMemo(() => collectResources(turns), [turns]);
  const mockMode = useMemo(() => isAssistantMockEnabled(), []);
  const municipalities = useMemo(
    () =>
      Array.from(new Set(sources.map((source) => source.municipality.trim()).filter(Boolean))).sort((a, b) =>
        a.localeCompare(b, "es-MX"),
      ),
    [sources],
  );

  // Restored turns carry ids; start the counter past them so new turns don't collide.
  const idRef = useRef(turns.reduce((max, t) => Math.max(max, t.id), 0));
  const controllerRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  // ¿El usuario está pegado al fondo? Gobierna el auto-scroll: si subió a leer
  // historial no lo arrastramos; si está abajo, seguimos la respuesta que se
  // genera. Cuántos turnos había, para detectar cuándo se agrega uno nuevo.
  const nearBottomRef = useRef(true);
  const prevLenRef = useRef(turns.length);
  // Latest turns, readable inside runAsk (a useCallback that must not depend on
  // `turns`). Lets every ask — including retries — replay prior Q→A for context.
  const turnsRef = useRef<Turn[]>(turns);

  useEffect(() => {
    turnsRef.current = turns;
    saveTurns(turns);
    // Solo al ENVIAR un turno nuevo re-enganchamos al fondo y enfocamos el actual.
    // El crecimiento por stream/typewriter lo sigue el ResizeObserver de abajo, así
    // no peleamos con el usuario cuando sube a leer mensajes anteriores.
    if (turns.length > prevLenRef.current) {
      nearBottomRef.current = true;
      bottomRef.current?.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "end" });
    }
    prevLenRef.current = turns.length;
  }, [turns]);

  // Stick-to-bottom estilo chat de IA: cuando el contenido crece (pasos del
  // stream o el texto que se va escribiendo) y el usuario está pegado al fondo,
  // mantenemos la vista en el final para seguir la respuesta en curso.
  useEffect(() => {
    const el = scrollRef.current;
    const content = contentRef.current;
    if (!el || !content || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (nearBottomRef.current) el.scrollTop = el.scrollHeight;
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, []);

  const clearChat = useCallback(() => {
    controllerRef.current?.abort();
    setTurns([]);
    idRef.current = 0;
    setLoading(false);
    setInputError("");
    setClearConfirmOpen(false);
    setResourcesOpen(false);
    setPendingScopeQuestion("");
    setScopeAsked(false);
    try {
      window.sessionStorage.removeItem(CHAT_STORAGE_KEY);
    } catch {
      // ignore: clearing UI state is what matters
    }
  }, []);

  const requestClearChat = useCallback(() => {
    setClearConfirmOpen(true);
  }, []);

  useEffect(() => {
    if (!clearConfirmOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setClearConfirmOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [clearConfirmOpen]);

  useEffect(() => {
    if (mockMode) {
      setSources(mockMunicipalSources);
      return;
    }

    const controller = new AbortController();
    api.sources
      .list({ signal: controller.signal })
      .then(setSources)
      .catch(() => {
        if (!controller.signal.aborted) setSources([]);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (mode !== "ciudadano") {
      setPendingSuggestion("");
      setMunicipalityFilter("");
      setPendingScopeQuestion("");
    }
  }, [mode]);

  const resetInputHeight = useCallback(() => {
    window.requestAnimationFrame(() => {
      if (inputRef.current) inputRef.current.style.height = "auto";
    });
  }, []);

  const runAsk = useCallback(async (id: number, question: string, askMode: AskMode) => {
    setTurns((prev) =>
      prev.map((t) =>
        t.id === id ? { ...t, mode: askMode, status: "thinking", error: undefined, activity: [] } : t,
      ),
    );
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    // Cada evento del agente se funde en la actividad del turno: "run" agrega una
    // fila; "done" marca como completada la última fila con la misma etiqueta.
    const onStep = (step: AskStep) => {
      setTurns((prev) =>
        prev.map((t) => {
          if (t.id !== id) return t;
          const activity = [...(t.activity ?? [])];
          if (step.status === "run") {
            activity.push(step);
          } else {
            for (let k = activity.length - 1; k >= 0; k--) {
              if (activity[k].label === step.label && activity[k].status === "run") {
                activity[k] = step;
                break;
              }
            }
          }
          return { ...t, activity };
        }),
      );
    };
    try {
      const history = turnsRef.current
        .filter((t) => t.id !== id && t.status === "done" && t.answer)
        .slice(-3)
        .map((t) => ({ question: t.question, answer: t.answer as string }));
      const res: AskResponse = mockMode
        ? await mockAskStream(question, askMode, controller.signal, onStep)
        : await api.agent.askStream(question, askMode, history, onStep, { signal: controller.signal });
      notifyPntMention(res.answer);
      setTurns((prev) =>
        prev.map((t) =>
          t.id === id
            ? {
                ...t,
                status: "done",
                answer: res.answer,
                mode: res.mode ?? askMode,
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
    (raw: string, askMode: AskMode = mode) => {
      if (loading) return;
      const question = raw.trim();
      if (question.length < 3) {
        setInputError("Escribe una pregunta de al menos 3 caracteres.");
        return;
      }
      setInputError("");
      setInput("");
      resetInputHeight();
      const scopedQuestion =
        askMode === "ciudadano" && municipalityFilter
          ? `Para ${municipalityFilter}: ${question}`
          : question;
      const id = (idRef.current += 1);
      setTurns((prev) => [...prev, { id, question: scopedQuestion, mode: askMode, status: "thinking" }]);
      void runAsk(id, scopedQuestion, askMode);
    },
    [loading, mode, municipalityFilter, resetInputHeight, runAsk],
  );

  const submitSuggestion = useCallback(
    (question: string, municipality?: string) => {
      const scopedQuestion = municipality ? `Para ${municipality}: ${question}` : question;
      setPendingSuggestion("");
      submit(scopedQuestion, "ciudadano");
    },
    [submit],
  );

  // Pide al agente redactar una solicitud PNT lista para enviar, a partir de la
  // pregunta original. El prompt detallado es también lo que se muestra como turno.
  const draftPntRequest = useCallback(
    (question: string) => {
      if (loading) return;
      const prompt =
        `Redacta una solicitud de información lista para enviar por la Plataforma ` +
        `Nacional de Transparencia (PNT) sobre: «${question}». Estructúrala con: ` +
        `sujeto obligado probable, los documentos concretos a solicitar, el periodo ` +
        `y el formato digital abierto, y al final cómo dar seguimiento (guardar el ` +
        `folio y, si aplica, recurso de revisión). Lenguaje claro y respetuoso.`;
      const id = (idRef.current += 1);
      setTurns((prev) => [...prev, { id, question: prompt, mode, status: "thinking" }]);
      void runAsk(id, prompt, mode);
    },
    [loading, mode, runAsk],
  );

  // Punto único de envío desde el composer: si es modo ciudadano y aún no se ha
  // fijado un alcance (ni municipio elegido ni decisión cacheada), primero
  // pregunta «¿todos o un municipio?» en vez de mandar a ciegas.
  const handleSend = useCallback(
    (raw: string) => {
      if (loading) return;
      const question = raw.trim();
      if (question.length < 3) {
        setInputError("Escribe una pregunta de al menos 3 caracteres.");
        return;
      }
      if (mode === "ciudadano" && !municipalityFilter && !scopeAsked) {
        setInputError("");
        setPendingScopeQuestion(question);
        return;
      }
      submit(raw);
    },
    [loading, mode, municipalityFilter, scopeAsked, submit],
  );

  const resolveScope = useCallback(
    (question: string, municipality?: string) => {
      if (municipality) setMunicipalityFilter(municipality);
      else setScopeAsked(true);
      setPendingScopeQuestion("");
      submitSuggestion(question, municipality);
    },
    [submitSuggestion],
  );

  const stop = () => controllerRef.current?.abort();

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    nearBottomRef.current = distance < 120;
    setShowScrollDown(distance > 280);
  }, []);

  const scrollToBottom = () =>
    bottomRef.current?.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "end" });

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} onScroll={handleScroll} className="tech-grid no-scrollbar min-h-0 flex-1 overflow-y-auto pb-64">
        <div ref={contentRef} className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6">
          {turns.length === 0 ? (
            <Intro
              mode={mode}
              municipalities={municipalities}
              pendingSuggestion={pendingSuggestion}
              onPickSuggestion={setPendingSuggestion}
              onCancelSuggestion={() => setPendingSuggestion("")}
              onSubmitSuggestion={submitSuggestion}
              disabled={loading}
            />
          ) : (
            <div className="space-y-6">
              <div className="space-y-10">
                {turns.map((turn) => (
                  <TurnBlock
                    key={turn.id}
                    turn={turn}
                    onRetry={() => runAsk(turn.id, turn.question, turn.mode)}
                    onDraftRequest={() => draftPntRequest(turn.question)}
                    disabled={loading}
                  />
                ))}
              </div>
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
        onClearChat={requestClearChat}
        canClearChat={turns.length > 0 || loading}
      />

      <ClearChatDialog
        open={clearConfirmOpen}
        loading={loading}
        onCancel={() => setClearConfirmOpen(false)}
        onConfirm={clearChat}
      />

      {showScrollDown ? (
        <button
          type="button"
          onClick={scrollToBottom}
          className="turn-rise fixed bottom-28 left-1/2 z-40 grid h-10 w-10 -translate-x-1/2 place-items-center rounded-full border border-line-strong bg-surface/95 text-muted shadow-[0_10px_30px_rgba(21,32,26,0.18)] backdrop-blur transition hover:text-ink"
          aria-label="Bajar al final"
          title="Bajar al final"
        >
          <ArrowDown className="h-4 w-4" />
        </button>
      ) : null}

      <div className="assistant-composer-dock pointer-events-none fixed inset-x-0 bottom-0 z-40 pb-4">
        <div className="relative z-10 mx-auto w-full max-w-5xl px-4 sm:px-6">
          {!agentAvailable ? (
            <Unavailable onRetry={() => setAgentAvailable(true)} />
          ) : (
            <>
              {pendingScopeQuestion ? (
                <div className="pointer-events-auto mb-2">
                  <MunicipalityMenu
                    question={pendingScopeQuestion}
                    municipalities={municipalities}
                    onSubmit={resolveScope}
                    onCancel={() => setPendingScopeQuestion("")}
                  />
                </div>
              ) : null}
              <div className="pointer-events-auto flex items-center gap-2 rounded-2xl border border-line-strong bg-surface/95 p-2 shadow-[0_18px_45px_rgba(21,32,26,0.16)] backdrop-blur focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/15">
                <ComposerSettings
                  mode={mode}
                  onModeChange={setMode}
                  municipality={municipalityFilter}
                  municipalities={municipalities}
                  onMunicipalityChange={setMunicipalityFilter}
                  disabled={loading}
                />
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      handleSend(input);
                    }
                  }}
                  onInput={(event) => {
                    const el = event.currentTarget;
                    el.style.height = "auto";
                    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
                  }}
                  rows={1}
                  placeholder="Pregunta sobre trámites, presupuestos, reglamentos…"
                  className="max-h-40 min-w-0 flex-1 resize-none bg-transparent px-1 py-2 text-[15px] leading-6 outline-none placeholder:text-faint"
                />
                {loading ? (
                  <button
                    type="button"
                    onClick={stop}
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-line-strong text-muted transition hover:bg-paper hover:text-ink"
                    aria-label="Detener"
                    title="Detener"
                  >
                    <Square className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleSend(input)}
                    disabled={input.trim().length < 3}
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand to-brand-strong text-white shadow-[0_6px_16px_rgba(0,138,74,0.26)] transition enabled:hover:opacity-90 disabled:opacity-40 disabled:shadow-none"
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

function Intro({
  mode,
  municipalities,
  pendingSuggestion,
  onPickSuggestion,
  onCancelSuggestion,
  onSubmitSuggestion,
  disabled,
}: {
  mode: AskMode;
  municipalities: string[];
  pendingSuggestion: string;
  onPickSuggestion: (question: string) => void;
  onCancelSuggestion: () => void;
  onSubmitSuggestion: (question: string, municipality?: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center justify-start pt-4 text-center sm:pt-8">
      <span className="intro-orb turn-rise" aria-hidden>
        <Sparkles className="h-5 w-5" />
      </span>
      <h1 className="intro-gradient mt-4 font-display text-4xl font-medium leading-tight tracking-tight sm:text-5xl">
        Pregúntale a los documentos
      </h1>
      <p className="mx-auto mt-4 max-w-xl text-base leading-8 text-muted sm:text-[17px]">
        Consulta trámites, reglamentos, presupuestos, actas y contratos en lenguaje natural. El
        asistente busca en documentos públicos, resume lo relevante y muestra las fuentes oficiales
        que respaldan la respuesta.
      </p>

      {mode === "ciudadano" ? (
        <div className="mt-9 w-full max-w-3xl text-left">
          {pendingSuggestion ? (
            <MunicipalityMenu
              question={pendingSuggestion}
              municipalities={municipalities}
              onSubmit={onSubmitSuggestion}
              onCancel={onCancelSuggestion}
            />
          ) : (
            <div className="grid gap-2.5 sm:grid-cols-3">
                {suggestedQuestions.map((question, index) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => onPickSuggestion(question)}
                    disabled={disabled}
                    className="group flex h-full flex-col gap-3 rounded-2xl border border-line bg-surface/80 p-4 text-left text-sm leading-5 text-muted transition hover:-translate-y-0.5 hover:border-brand/40 hover:bg-surface hover:text-ink hover:shadow-[0_12px_30px_rgba(21,32,26,0.1)] disabled:opacity-50"
                  >
                    <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-soft font-mono text-[11px] font-semibold text-brand transition group-hover:bg-brand group-hover:text-white">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="flex-1">{question}</span>
                    <ArrowUp className="h-4 w-4 rotate-45 text-faint transition group-hover:text-brand" />
                  </button>
                ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function MunicipalityMenu({
  question,
  municipalities,
  onSubmit,
  onCancel,
}: {
  question: string;
  municipalities: string[];
  onSubmit: (question: string, municipality?: string) => void;
  onCancel: () => void;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [query, setQuery] = useState("");
  const filteredMunicipalities = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("es-MX");
    if (!normalized) return municipalities;
    return municipalities.filter((municipality) =>
      municipality.toLocaleLowerCase("es-MX").includes(normalized),
    );
  }, [municipalities, query]);

  useEffect(() => {
    window.requestAnimationFrame(() => {
      panelRef.current?.scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "center" });
    });
  }, []);

  return (
    <div
      ref={panelRef}
      data-assistant-municipality-panel
      className="overflow-hidden rounded-xl border border-line-strong bg-surface text-left shadow-[0_18px_42px_rgba(21,32,26,0.12)]"
    >
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-faint">
          <MapPin className="h-3.5 w-3.5 text-brand" />
          Municipio
        </div>
        <p className="mt-2 text-sm leading-6 text-ink">{question}</p>
      </div>
      <div className="border-b border-line p-2">
        <label className="relative block">
          <span className="sr-only">Buscar municipio</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-10 w-full rounded-lg border border-line bg-paper pl-9 pr-3 text-sm outline-none transition placeholder:text-faint focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/15"
            placeholder="Buscar municipio"
          />
        </label>
      </div>
      <div className="max-h-[8.75rem] overflow-y-auto p-2">
        <button
          type="button"
          onClick={() => onSubmit(question)}
          className="block w-full rounded-lg px-3 py-2.5 text-left text-sm font-semibold text-ink transition hover:bg-paper"
        >
          Todos los municipios
        </button>
        <div className="mt-1 grid gap-1 sm:grid-cols-2">
          {filteredMunicipalities.map((municipality) => (
            <button
              key={municipality}
              type="button"
              onClick={() => onSubmit(question, municipality)}
              className="block w-full rounded-lg px-3 py-2 text-left text-sm text-muted transition hover:bg-paper hover:text-ink"
            >
              {municipality}
            </button>
          ))}
        </div>
        {!municipalities.length ? (
          <p className="px-3 py-2 text-xs leading-5 text-faint">
            No pude cargar el catálogo de municipios. Puedes preguntar en todos por ahora.
          </p>
        ) : null}
        {municipalities.length && !filteredMunicipalities.length ? (
          <p className="px-3 py-2 text-xs leading-5 text-faint">Sin municipios con ese texto.</p>
        ) : null}
      </div>
      <div className="border-t border-line px-1.5 py-1.5">
        <button
          type="button"
          onClick={onCancel}
          className="block w-full rounded-lg px-3 py-2 text-left text-xs font-semibold text-faint transition hover:bg-paper hover:text-ink"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

// Engranaje del composer: condensa modo de respuesta + municipio en un popover,
// para dejar la barra de entrada limpia. Un punto en el engranaje señala que hay
// alguna configuración activa (modo técnico o municipio fijado).
function ComposerSettings({
  mode,
  onModeChange,
  municipality,
  municipalities,
  onMunicipalityChange,
  disabled,
}: {
  mode: AskMode;
  onModeChange: (mode: AskMode) => void;
  municipality: string;
  municipalities: string[];
  onMunicipalityChange: (value: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const customized = mode !== "ciudadano" || !!municipality;

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onEscape);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        disabled={disabled}
        aria-label="Configuración de la consulta"
        aria-expanded={open}
        title="Configuración"
        className={`relative grid h-10 w-10 place-items-center rounded-xl border transition disabled:opacity-50 ${
          open
            ? "border-brand bg-brand-soft text-brand"
            : "border-line-strong text-muted hover:bg-paper hover:text-ink"
        }`}
      >
        <Settings className={`h-4 w-4 transition-transform ${open ? "rotate-45" : ""}`} />
        {customized && !open ? (
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-brand" />
        ) : null}
      </button>

      {open ? (
        <div className="absolute bottom-full left-0 z-50 mb-2 w-72 rounded-xl border border-line-strong bg-surface p-3 shadow-[0_14px_35px_rgba(21,32,26,0.18)]">
          <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
            Modo de respuesta
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            {(["ciudadano", "investigador"] as AskMode[]).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => onModeChange(option)}
                className={`rounded-lg border px-2.5 py-2 text-left transition ${
                  mode === option
                    ? "border-brand bg-brand-soft text-ink"
                    : "border-line bg-paper text-muted hover:text-ink"
                }`}
              >
                <span className="block text-xs font-semibold">{modeLabel[option]}</span>
                <span className="mt-0.5 block text-[11px] leading-4 text-faint">
                  {option === "ciudadano" ? "Breve y simple" : "Detalle y trazabilidad"}
                </span>
              </button>
            ))}
          </div>

          {mode === "ciudadano" ? (
            <div className="mt-3">
              <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.14em] text-faint">
                Municipio
              </p>
              <label className="relative block">
                <span className="sr-only">Municipio para consultar</span>
                <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
                <select
                  value={municipality}
                  onChange={(event) => onMunicipalityChange(event.target.value)}
                  disabled={disabled}
                  className="h-10 w-full appearance-none rounded-lg border border-line bg-paper pl-9 pr-8 text-sm text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/15 disabled:opacity-50"
                >
                  <option value="">Todos los municipios</option>
                  {municipalities.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-faint">
                  ⌄
                </span>
              </label>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
function TurnBlock({
  turn,
  onRetry,
  onDraftRequest,
  disabled,
}: {
  turn: Turn;
  onRetry: () => void;
  onDraftRequest: () => void;
  disabled: boolean;
}) {
  return (
    <div className="turn-rise space-y-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-line-strong font-mono text-[11px] text-faint">
          Tú
        </span>
        <p className="user-bubble flex-1 px-4 py-2.5 font-display text-base leading-6 text-ink">
          {turn.question}
        </p>
      </div>

      {turn.status === "thinking" ? (
        <ThinkingIndicator steps={turn.activity ?? []} />
      ) : (
        <div className="assistant-answer-float">
          {turn.status === "error" ? (
          <ErrorBlock message={turn.error ?? "Error."} onRetry={onRetry} disabled={disabled} />
        ) : (
          <AnswerBlock turn={turn} onDraftRequest={onDraftRequest} disabled={disabled} />
        )}
        </div>
      )}
    </div>
  );
}

const STEP_ICONS: Record<string, LucideIcon> = {
  search_documents: Search,
  read_document: FileText,
  document_coverage: Database,
  list_documents: FileText,
};

function stepCountLabel(count: number) {
  return `${count} ${count === 1 ? "resultado" : "resultados"}`;
}

// Una fila del timeline: punto de estado, ícono de la herramienta, etiqueta y
// (si aplica) conteo. Compartida por el indicador en vivo y el pie de testigos.
function TimelineItem({ step }: { step: AskStep }) {
  const Icon = STEP_ICONS[step.tool] ?? Sparkles;
  const done = step.status === "done";
  return (
    <li className={`thinking-tl-item ${done ? "is-done" : "is-run"}`}>
      <span className="thinking-tl-dot">{done ? <Check className="h-2.5 w-2.5" /> : null}</span>
      <Icon className="h-3.5 w-3.5 shrink-0 text-faint" />
      {step.url ? (
        <a
          href={step.url}
          target="_blank"
          rel="noreferrer"
          className="min-w-0 truncate font-medium text-brand underline decoration-brand/30 underline-offset-2 transition hover:decoration-brand"
          title={step.url}
        >
          {step.label}
        </a>
      ) : (
        <span className={`min-w-0 truncate ${done ? "text-muted" : "font-medium text-ink"}`}>
          {step.label}
        </span>
      )}
      {typeof step.count === "number" ? (
        <span className="ml-auto shrink-0 font-mono text-[11px] text-faint">
          {stepCountLabel(step.count)}
        </span>
      ) : null}
    </li>
  );
}

function ThinkingIndicator({ steps }: { steps: AskStep[] }) {
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

  // Mientras no llega ningún paso real (router/primer turno del LLM), se cicla un
  // mensaje genérico; en cuanto el agente actúa, el titular y el ícono del orb
  // reflejan su último paso real.
  const last = steps[steps.length - 1];
  const headline = last ? last.label : thinkingMessages[messageIndex];
  const HeadIcon = last ? STEP_ICONS[last.tool] ?? Sparkles : Database;

  return (
    <div className="thinking-float">
      <div className="thinking-orb" aria-hidden>
        <HeadIcon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-3 text-sm">
          <span className="truncate font-medium text-ink">{headline}</span>
          <span className="ml-auto shrink-0 font-mono text-xs tabular-nums text-faint">{seconds}s</span>
        </div>
        {steps.length ? (
          <ol className="thinking-timeline mt-3.5">
            {steps.map((step, index) => (
              <TimelineItem key={`${step.label}-${index}`} step={step} />
            ))}
          </ol>
        ) : (
          <div className="thinking-bar mt-3 h-1.5 rounded-full" />
        )}
      </div>
    </div>
  );
}

// Pie de "testigos": los pasos que el agente ejecutó, dejados al final de la
// respuesta. Colapsado por defecto para no estorbar; el resumen anuncia cuántos
// pasos hubo y cuántos documentos abrió.
function AgentTrace({ steps }: { steps: AskStep[] }) {
  const done = steps.filter((s) => s.status === "done");
  if (!done.length) return null;
  const readCount = done.filter((s) => s.tool === "read_document").length;
  const summary = [
    `${done.length} ${done.length === 1 ? "paso" : "pasos"}`,
    readCount ? `${readCount} ${readCount === 1 ? "documento leído" : "documentos leídos"}` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <details className="mt-5 rounded-xl border border-line bg-paper/60 px-4 py-3">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-semibold text-muted transition hover:text-ink">
        <Activity className="h-3.5 w-3.5 text-brand" />
        Cómo llegué a esto
        <span className="font-mono text-[11px] font-normal text-faint">· {summary}</span>
      </summary>
      <ol className="thinking-timeline mt-3">
        {done.map((step, index) => (
          <TimelineItem key={`${step.label}-${index}`} step={step} />
        ))}
      </ol>
    </details>
  );
}

function AnswerBlock({
  turn,
  onDraftRequest,
  disabled,
}: {
  turn: Turn;
  onDraftRequest: () => void;
  disabled: boolean;
}) {
  const { shown, done } = useTypewriter(turn.answer ?? "");
  const sources = turn.sources ?? [];
  const renderedAnswer = useMemo(() => renderMarkdown(shown), [shown]);
  const mentionsPnt = pntMentionPattern.test(turn.answer ?? "");

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-faint">
        <span className="assistant-orb" aria-hidden>
          <Sparkles className="h-3.5 w-3.5" />
        </span>
        <span className="font-mono">Asistente</span>
        <Sep />
        <span className="rounded-full border border-line px-2 py-0.5 font-mono">
          {modeLabel[turn.mode] ?? turn.mode}
        </span>
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

      {/* Testigos del stream, arriba: qué hizo el agente para llegar a esto. */}
      <AgentTrace steps={turn.activity ?? []} />

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

      {done && mentionsPnt ? (
        <div className="mt-5 rounded-xl border border-brand/30 bg-brand-soft p-4">
          <div className="flex items-start gap-2.5">
            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink">¿No está en el corpus? Pídelo por la PNT</p>
              <p className="mt-1 text-xs leading-5 text-muted">
                Te redacto una solicitud lista para enviar, o sigue la guía paso a paso.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onDraftRequest}
                  disabled={disabled}
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-strong px-3 text-sm font-semibold text-white transition enabled:hover:bg-brand disabled:opacity-40"
                >
                  <Sparkles className="h-4 w-4" /> Redactar solicitud
                </button>
                <Link
                  to="/pnt"
                  className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line-strong bg-paper px-3 text-sm font-semibold text-ink transition hover:bg-surface"
                >
                  Ver guía PNT <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </div>
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
      className="group flex gap-2.5 rounded-lg border border-line bg-paper p-2.5 transition hover:border-line-strong hover:bg-surface"
    >
      <span className="mt-px shrink-0 font-mono text-[11px] text-faint">[{index}]</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold leading-5 transition group-hover:text-brand">
          {sourceTitle(source)}
        </span>
        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 font-mono text-[10px] uppercase tracking-wider text-faint">
          <span>{jurisdictionLabel[source.jurisdiction] ?? source.jurisdiction}</span>
          {page ? (
            <>
              <Sep />
              <span>{page}</span>
            </>
          ) : null}
        </span>
        {source.excerpt ? (
          <span className="mt-1.5 line-clamp-2 block border-l-2 border-line-strong pl-2.5 text-[11px] leading-4 text-muted">
            “{source.excerpt}”
          </span>
        ) : null}
      </span>
      <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-faint transition group-hover:text-brand" />
    </a>
  );
}

function ResourcesPanel({
  resources,
  loading,
  open,
  onToggle,
  onClearChat,
  canClearChat,
}: {
  resources: ResourceItem[];
  loading: boolean;
  open: boolean;
  onToggle: () => void;
  onClearChat: () => void;
  canClearChat: boolean;
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
        {canClearChat ? (
          <div className="mt-auto border-t border-line pt-3">
            <button
              type="button"
              onClick={onClearChat}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-line-strong bg-paper px-3 text-sm font-semibold text-muted transition hover:border-brand/35 hover:bg-surface hover:text-ink"
              title="Empezar una conversación nueva"
            >
              <Plus className="h-4 w-4" /> Nueva conversación
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function ClearChatDialog({
  open,
  loading,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  loading: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-[#101814]/38 px-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <section
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="clear-chat-title"
        aria-describedby="clear-chat-description"
        className="w-full max-w-md rounded-card border border-line-strong bg-surface p-5 shadow-[0_24px_70px_rgba(21,32,26,0.24)]"
      >
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-warn-soft text-warn-ink">
            <AlertTriangle className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h2 id="clear-chat-title" className="font-display text-xl font-semibold leading-6">
              Crear una nueva conversación
            </h2>
            <p id="clear-chat-description" className="mt-3 text-sm leading-6 text-muted">
              Se perderá el chat anterior en esta pestaña, incluyendo preguntas, respuestas,
              fuentes encontradas y contexto usado para repreguntas.
              {loading ? " La consulta en curso también se cancelará." : ""}
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-10 items-center justify-center rounded-lg border border-line-strong bg-paper px-4 text-sm font-semibold text-muted transition hover:bg-surface hover:text-ink"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="inline-flex h-10 items-center justify-center rounded-lg bg-danger-ink px-4 text-sm font-semibold text-white transition hover:bg-[#7c281f]"
          >
            Sí, borrar chat
          </button>
        </div>
      </section>
    </div>
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
