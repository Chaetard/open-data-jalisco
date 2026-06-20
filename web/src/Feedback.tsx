import { useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  Bug,
  CheckCircle2,
  Clipboard,
  ExternalLink,
  Mail,
  MessageSquareText,
} from "lucide-react";

type FeedbackType =
  | "bug"
  | "mejora"
  | "dato"
  | "asistente"
  | "documentacion"
  | "seguridad"
  | "otro";

type FeedbackArea =
  | "inicio"
  | "explorador"
  | "asistente"
  | "api"
  | "pnt"
  | "documentacion"
  | "datos"
  | "despliegue"
  | "otro";

type FeedbackPriority = "baja" | "media" | "alta" | "bloqueante";

type FeedbackForm = {
  type: FeedbackType;
  area: FeedbackArea;
  priority: FeedbackPriority;
  title: string;
  description: string;
  expected: string;
  actual: string;
  steps: string;
  url: string;
  documentUrl: string;
  municipality: string;
  browser: string;
  device: string;
  contactName: string;
  contactEmail: string;
  allowContact: boolean;
  includeDiagnostics: boolean;
};

const FEEDBACK_EMAIL = "jesus@n0kemm.dev";

const initialForm: FeedbackForm = {
  type: "mejora",
  area: "explorador",
  priority: "media",
  title: "",
  description: "",
  expected: "",
  actual: "",
  steps: "",
  url: "",
  documentUrl: "",
  municipality: "",
  browser: "",
  device: "",
  contactName: "",
  contactEmail: "",
  allowContact: true,
  includeDiagnostics: true,
};

const typeOptions: Array<{ value: FeedbackType; label: string }> = [
  { value: "bug", label: "Bug" },
  { value: "mejora", label: "Mejora" },
  { value: "dato", label: "Dato o fuente" },
  { value: "asistente", label: "Asistente" },
  { value: "documentacion", label: "Documentación" },
  { value: "seguridad", label: "Seguridad" },
  { value: "otro", label: "Otro" },
];

const areaOptions: Array<{ value: FeedbackArea; label: string }> = [
  { value: "inicio", label: "Inicio" },
  { value: "explorador", label: "Explorador" },
  { value: "asistente", label: "Asistente" },
  { value: "api", label: "API" },
  { value: "pnt", label: "Guía PNT" },
  { value: "documentacion", label: "Documentación" },
  { value: "datos", label: "Datos" },
  { value: "despliegue", label: "Despliegue" },
  { value: "otro", label: "Otro" },
];

const priorityOptions: Array<{ value: FeedbackPriority; label: string }> = [
  { value: "baja", label: "Baja" },
  { value: "media", label: "Media" },
  { value: "alta", label: "Alta" },
  { value: "bloqueante", label: "Bloqueante" },
];

const currentPageUrl = () => {
  if (typeof window === "undefined") return "";
  return window.location.href;
};

const detectedBrowser = () => {
  if (typeof navigator === "undefined") return "";
  return navigator.userAgent;
};

const detectedDevice = () => {
  if (typeof window === "undefined" || typeof navigator === "undefined") return "";
  return `${navigator.platform || "plataforma desconocida"} · ${window.innerWidth}x${window.innerHeight}`;
};

const labelFor = <T extends string>(options: Array<{ value: T; label: string }>, value: T) =>
  options.find((option) => option.value === value)?.label ?? value;

const clean = (value: string) => value.trim() || "No especificado";

const buildBody = (form: FeedbackForm) => {
  const diagnostics: Record<string, string> = form.includeDiagnostics
    ? {
        "Página actual": currentPageUrl() || "No disponible",
        "Navegador detectado": form.browser || detectedBrowser() || "No disponible",
        "Dispositivo/viewport": form.device || detectedDevice() || "No disponible",
      }
    : {
        "Página actual": clean(form.url),
      };

  const sections: Array<[string, Record<string, string>]> = [
    [
      "Resumen",
      {
        Tipo: labelFor(typeOptions, form.type),
        Área: labelFor(areaOptions, form.area),
        Prioridad: labelFor(priorityOptions, form.priority),
        Título: clean(form.title),
        Municipio: clean(form.municipality),
      },
    ],
    [
      "Detalle",
      {
        Descripción: clean(form.description),
        "Qué esperaba": clean(form.expected),
        "Qué ocurrió": clean(form.actual),
        "Pasos para reproducir o contexto": clean(form.steps),
      },
    ],
    [
      "Referencias",
      {
        "URL relacionada": clean(form.url),
        "Documento/fuente relacionada": clean(form.documentUrl),
      },
    ],
    [
      "Contacto",
      {
        Nombre: clean(form.contactName),
        Email: clean(form.contactEmail),
        "Puede responderme": form.allowContact ? "Sí" : "No",
      },
    ],
    ["Diagnóstico", diagnostics],
  ];

  return sections
    .map(([title, values]) => {
      const rows = Object.entries(values)
        .map(([key, value]) => `${key}: ${value}`)
        .join("\n");
      return `## ${title}\n${rows}`;
    })
    .join("\n\n");
};

export default function Feedback() {
  const [form, setForm] = useState<FeedbackForm>(() => ({
    ...initialForm,
    url: currentPageUrl(),
    browser: detectedBrowser(),
    device: detectedDevice(),
  }));
  const [copied, setCopied] = useState(false);

  const body = useMemo(() => buildBody(form), [form]);
  const subject = useMemo(() => {
    const type = labelFor(typeOptions, form.type);
    const area = labelFor(areaOptions, form.area);
    const title = form.title.trim() || "comentario beta";
    return `[ODJ beta] ${type} · ${area} · ${title}`;
  }, [form.area, form.title, form.type]);
  const mailtoHref = useMemo(
    () => `mailto:${FEEDBACK_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`,
    [body, subject],
  );
  const bodyTooLong = mailtoHref.length > 1800;
  const canSend = form.title.trim().length >= 4 && form.description.trim().length >= 10;

  const update = <K extends keyof FeedbackForm>(key: K, value: FeedbackForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const copyBody = async () => {
    try {
      await navigator.clipboard.writeText(`Para: ${FEEDBACK_EMAIL}\nAsunto: ${subject}\n\n${body}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="max-w-3xl">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
          Comentarios beta
        </p>
        <h1 className="mt-4 font-display text-[2.35rem] font-medium leading-tight tracking-tight text-ink sm:text-[3rem]">
          Ayuda a mejorar Open Data Jalisco
        </h1>
        <p className="mt-4 text-[15px] leading-7 text-muted">
          Este formulario no guarda nada en un servidor. Al final abre tu correo con el mensaje
          armado para enviarlo a <span className="font-semibold text-ink">{FEEDBACK_EMAIL}</span>.
        </p>
      </div>

      <form className="mt-9 space-y-6" onSubmit={(event) => event.preventDefault()}>
        <section className="rounded-card border border-line bg-surface p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <MessageSquareText className="h-5 w-5 text-brand" />
            <h2 className="font-display text-xl font-semibold">Clasificación</h2>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <Field label="Tipo">
              <Select
                value={form.type}
                onChange={(value) => update("type", value as FeedbackType)}
                options={typeOptions}
              />
            </Field>
            <Field label="Área">
              <Select
                value={form.area}
                onChange={(value) => update("area", value as FeedbackArea)}
                options={areaOptions}
              />
            </Field>
            <Field label="Prioridad">
              <Select
                value={form.priority}
                onChange={(value) => update("priority", value as FeedbackPriority)}
                options={priorityOptions}
              />
            </Field>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-[1.4fr_0.8fr]">
            <Field label="Título corto" required>
              <Input
                value={form.title}
                maxLength={120}
                placeholder="Ej. El explorador mezcla leyes estatales con resultados municipales"
                onChange={(value) => update("title", value)}
              />
            </Field>
            <Field label="Municipio o alcance">
              <Input
                value={form.municipality}
                maxLength={80}
                placeholder="Tala, Tequila, general…"
                onChange={(value) => update("municipality", value)}
              />
            </Field>
          </div>
        </section>

        <section className="rounded-card border border-line bg-surface p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <Bug className="h-5 w-5 text-brand" />
            <h2 className="font-display text-xl font-semibold">Detalle</h2>
          </div>

          <div className="mt-5 grid gap-4">
            <Field label="Qué pasó o qué propones" required>
              <Textarea
                value={form.description}
                minRows={5}
                maxLength={1800}
                placeholder="Describe el problema, idea, duda, fuente faltante o comportamiento raro."
                onChange={(value) => update("description", value)}
              />
            </Field>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Qué esperabas">
                <Textarea
                  value={form.expected}
                  minRows={4}
                  maxLength={900}
                  placeholder="Resultado esperado, criterio correcto o cómo debería sentirse."
                  onChange={(value) => update("expected", value)}
                />
              </Field>
              <Field label="Qué ocurrió">
                <Textarea
                  value={form.actual}
                  minRows={4}
                  maxLength={900}
                  placeholder="Resultado actual, mensaje de error, respuesta del asistente, etc."
                  onChange={(value) => update("actual", value)}
                />
              </Field>
            </div>

            <Field label="Pasos para reproducir o contexto">
              <Textarea
                value={form.steps}
                minRows={4}
                maxLength={1200}
                placeholder={"1. Abrí…\n2. Busqué…\n3. Vi…"}
                onChange={(value) => update("steps", value)}
              />
            </Field>
          </div>
        </section>

        <section className="rounded-card border border-line bg-surface p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <ExternalLink className="h-5 w-5 text-brand" />
            <h2 className="font-display text-xl font-semibold">Referencias</h2>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Field label="URL relacionada">
              <Input
                value={form.url}
                placeholder="Página donde ocurrió"
                onChange={(value) => update("url", value)}
              />
            </Field>
            <Field label="Documento o fuente relacionada">
              <Input
                value={form.documentUrl}
                placeholder="URL de PDF, portal, fuente oficial o issue"
                onChange={(value) => update("documentUrl", value)}
              />
            </Field>
            <Field label="Navegador">
              <Input value={form.browser} onChange={(value) => update("browser", value)} />
            </Field>
            <Field label="Dispositivo / viewport">
              <Input value={form.device} onChange={(value) => update("device", value)} />
            </Field>
          </div>

          <label className="mt-5 flex items-start gap-3 rounded-lg border border-line bg-paper p-3 text-sm leading-6 text-muted">
            <input
              type="checkbox"
              checked={form.includeDiagnostics}
              onChange={(event) => update("includeDiagnostics", event.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 rounded border-line-strong accent-[#008a4a]"
            />
            Incluir diagnóstico básico en el correo: página actual, user agent y tamaño de ventana.
          </label>
        </section>

        <section className="rounded-card border border-line bg-surface p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-brand" />
            <h2 className="font-display text-xl font-semibold">Contacto</h2>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Field label="Nombre">
              <Input
                value={form.contactName}
                maxLength={100}
                placeholder="Opcional"
                onChange={(value) => update("contactName", value)}
              />
            </Field>
            <Field label="Tu correo">
              <Input
                value={form.contactEmail}
                type="email"
                maxLength={160}
                placeholder="Opcional"
                onChange={(value) => update("contactEmail", value)}
              />
            </Field>
          </div>

          <label className="mt-5 flex items-start gap-3 rounded-lg border border-line bg-paper p-3 text-sm leading-6 text-muted">
            <input
              type="checkbox"
              checked={form.allowContact}
              onChange={(event) => update("allowContact", event.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 rounded border-line-strong accent-[#008a4a]"
            />
            Puedes responderme si necesitas más contexto.
          </label>
        </section>

        <section className="rounded-card border border-line-strong bg-surface p-5 shadow-[0_18px_45px_rgba(21,32,26,0.08)] sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2">
                {bodyTooLong ? (
                  <AlertTriangle className="h-5 w-5 text-warn-ink" />
                ) : (
                  <CheckCircle2 className="h-5 w-5 text-brand" />
                )}
                <h2 className="font-display text-xl font-semibold">Enviar comentarios</h2>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted">
                El botón abrirá tu cliente de correo con destinatario, asunto y cuerpo
                precargados. Si tu app de correo recorta mensajes largos, usa “Copiar resumen”.
              </p>
              {bodyTooLong ? (
                <p className="mt-2 text-xs leading-5 text-warn-ink">
                  El correo quedó largo para algunos clientes. Todavía puede funcionar, pero conviene
                  copiar el resumen como respaldo.
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={copyBody}
                className="inline-flex h-11 items-center gap-2 rounded-xl border border-line-strong bg-paper px-4 text-sm font-semibold text-ink transition hover:bg-surface"
              >
                <Clipboard className="h-4 w-4" />
                {copied ? "Copiado" : "Copiar resumen"}
              </button>
              <a
                href={canSend ? mailtoHref : undefined}
                aria-disabled={!canSend}
                className={`inline-flex h-11 items-center gap-2 rounded-xl px-5 text-sm font-semibold text-white transition ${
                  canSend
                    ? "bg-brand-strong hover:bg-brand"
                    : "pointer-events-none bg-faint opacity-60"
                }`}
              >
                <Mail className="h-4 w-4" />
                Enviar comentarios
              </a>
            </div>
          </div>
        </section>
      </form>
    </section>
  );
}

function Field({
  label,
  required = false,
  children,
}: {
  label: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.12em] text-faint">
        {label}
        {required ? <span className="text-danger-ink"> *</span> : null}
      </span>
      {children}
    </label>
  );
}

function Input({
  value,
  onChange,
  type = "text",
  placeholder,
  maxLength,
}: {
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  maxLength?: number;
}) {
  return (
    <input
      type={type}
      value={value}
      maxLength={maxLength}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      className="h-11 w-full rounded-lg border border-line-strong bg-paper px-3 text-sm text-ink outline-none transition placeholder:text-faint focus:border-brand focus:ring-2 focus:ring-brand/15"
    />
  );
}

function Textarea({
  value,
  onChange,
  placeholder,
  minRows = 3,
  maxLength,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  minRows?: number;
  maxLength?: number;
}) {
  return (
    <textarea
      value={value}
      rows={minRows}
      maxLength={maxLength}
      placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)}
      className="w-full resize-y rounded-lg border border-line-strong bg-paper px-3 py-2.5 text-sm leading-6 text-ink outline-none transition placeholder:text-faint focus:border-brand focus:ring-2 focus:ring-brand/15"
    />
  );
}

function Select<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (value: string) => void;
  options: Array<{ value: T; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-11 w-full rounded-lg border border-line-strong bg-paper px-3 text-sm font-medium text-ink outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/15"
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
