import { useState, type ReactNode } from "react";
import {
  ArrowRight,
  Building2,
  CalendarDays,
  Check,
  ClipboardCheck,
  Copy,
  ExternalLink,
  FileQuestion,
  FileSearch,
  FileText,
  Search,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

const PNT_URL = "https://www.plataformadetransparencia.org.mx/Inicio";

const processSteps: Array<{
  number: string;
  icon: LucideIcon;
  title: string;
  body: string;
}> = [
  {
    number: "01",
    icon: Search,
    title: "Busca primero",
    body: "Antes de solicitar, revisa si el documento ya existe en ODJ, en el portal municipal o en la Plataforma Nacional de Transparencia. Guarda enlaces, fechas y capturas útiles.",
  },
  {
    number: "02",
    icon: Building2,
    title: "Define el sujeto obligado",
    body: "Para información municipal, normalmente será el ayuntamiento, una dependencia municipal, un organismo público descentralizado o una unidad administrativa relacionada con el tema.",
  },
  {
    number: "03",
    icon: FileText,
    title: "Pide documentos, no explicaciones",
    body: "Funciona mejor pedir copias, versiones públicas, contratos, facturas, actas, padrones, presupuestos, oficios, anexos o bases de datos, en lugar de pedir opiniones o conclusiones.",
  },
  {
    number: "04",
    icon: CalendarDays,
    title: "Acota periodo y formato",
    body: "Incluye fechas, municipio, área, programa, contrato, obra, expediente o periodo. Si puedes, pide entrega en formato digital abierto como CSV, XLSX, PDF buscable o liga de descarga.",
  },
  {
    number: "05",
    icon: ClipboardCheck,
    title: "Da seguimiento",
    body: "Conserva el folio de la solicitud. Si la respuesta es incompleta, no corresponde, niega información sin sustento o declara inexistencia, puedes valorar un recurso de revisión.",
  },
];

const requestTemplates = [
  {
    id: "contrato",
    title: "Contrato u obra pública",
    text: "Solicito copia digital del contrato, anexos, convenio modificatorio, estimaciones, facturas, evidencia de pago y acta de entrega-recepción relacionados con [obra/proyecto], ejecutado por [área o municipio], durante el periodo [fecha inicial] a [fecha final].",
  },
  {
    id: "presupuesto",
    title: "Presupuesto o gasto",
    text: "Solicito el presupuesto aprobado, modificado y ejercido de [programa/área/concepto] correspondiente al ejercicio fiscal [año], incluyendo partidas presupuestales, calendario de gasto y documentos que acrediten pagos realizados.",
  },
  {
    id: "no-localizado",
    title: "Documento no localizado",
    text: "Solicito se informe si el sujeto obligado cuenta con [documento específico]. En caso afirmativo, pido copia digital. En caso de inexistencia, solicito la respuesta fundada del área competente y, si aplica, el acta o constancia del comité correspondiente.",
  },
];

const odjCriteria = [
  "No convertir una ausencia documental en acusación.",
  "Distinguir entre no localizado, inexistente, reservado, confidencial y pendiente de publicación.",
  "Pedir evidencia primaria siempre que sea posible.",
  "Separar hechos verificables de interpretaciones.",
  "Mantener solicitudes claras, acotadas y respetuosas.",
];

const sourceLinks = [
  {
    label: "Plataforma Nacional de Transparencia",
    href: "https://www.plataformadetransparencia.org.mx/",
  },
  {
    label: "Manuales de la PNT",
    href: "https://www.plataformadetransparencia.org.mx/manuales",
  },
  {
    label: "Preguntas frecuentes de la PNT",
    href: "https://www.plataformadetransparencia.org.mx/preguntas-frecuentes",
  },
  {
    label: "Ley Federal de Transparencia y Acceso a la Información Pública",
    href: "https://sc.inegi.org.mx/repositorioNormateca/L_trans.pdf",
  },
];

const copyToClipboard = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
};

export default function PntGuide() {
  const [copiedId, setCopiedId] = useState("");

  const copyTemplate = async (id: string, text: string) => {
    try {
      await copyToClipboard(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((current) => (current === id ? "" : current)), 1800);
    } catch {
      setCopiedId("");
    }
  };

  return (
    <div className="bg-paper">
      <section className="border-b border-line bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[1.15fr_0.85fr] lg:px-8">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Guía ciudadana
            </p>
            <h1 className="mt-4 max-w-3xl font-display text-[2.35rem] font-medium leading-tight tracking-tight text-ink sm:text-[3.4rem]">
              Usar la PNT cuando ODJ no tenga el documento
            </h1>
            <p className="mt-5 max-w-2xl text-[15px] leading-7 text-muted">
              Si Open Data Jalisco no tiene un archivo, no lo inventamos ni lo presentamos como
              hecho. Te mostramos cómo solicitarlo por la Plataforma Nacional de Transparencia con
              una petición clara, técnica y apartidista.
            </p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <a
                href={PNT_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-brand-strong px-5 text-sm font-semibold text-white transition hover:bg-brand"
              >
                Abrir PNT <ExternalLink className="h-4 w-4" />
              </a>
              <a
                href="#modelos"
                className="inline-flex h-11 items-center gap-2 rounded-xl border border-line-strong bg-paper px-5 text-sm font-semibold text-ink transition hover:bg-surface"
              >
                Ver modelos <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </div>

          <GuidePanel icon={FileSearch} title="Pensada para datos públicos municipales">
            <p>
              Contratos, presupuestos, actas, padrones, pagos, directorios, programas, obras y
              documentos fuente. La guía prioriza solicitudes verificables y útiles para dar
              seguimiento a información municipal.
            </p>
          </GuidePanel>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            Antes de solicitar
          </p>
          <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
            Qué significa que no tengamos un documento
          </h2>
        </div>
        <div className="space-y-4 text-[15px] leading-7 text-muted">
          <p>
            Puede significar varias cosas: el documento no fue publicado, aún no lo hemos indexado,
            la fuente cambió de liga, el archivo fue retirado, está en otro portal o debe pedirse
            directamente al sujeto obligado.
          </p>
          <p className="rounded-card border border-line bg-surface p-5 text-sm leading-6">
            La ausencia en ODJ no prueba irregularidad por sí sola. Sirve como punto de partida para
            una solicitud mejor redactada y con trazabilidad.
          </p>
        </div>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
                Proceso
              </p>
              <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
                Cómo preparar una solicitud
              </h2>
            </div>
            <a
              href={PNT_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-10 items-center gap-2 self-start rounded-xl border border-line-strong bg-paper px-4 text-sm font-semibold text-ink transition hover:bg-surface sm:self-auto"
            >
              Abrir PNT <ExternalLink className="h-4 w-4" />
            </a>
          </div>

          <div className="mt-9 grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            {processSteps.map(({ number, icon: Icon, title, body }) => (
              <article key={number} className="rounded-card border border-line bg-paper p-5">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-[11px] font-semibold text-faint">{number}</span>
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand-soft text-brand">
                    <Icon className="h-4 w-4" />
                  </span>
                </div>
                <h3 className="mt-4 font-display text-lg font-semibold leading-6">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="modelos" className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            Redacción
          </p>
          <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
            Modelos para copiar y adaptar
          </h2>
          <p className="mt-4 text-[15px] leading-7 text-muted">
            Cambia los campos entre corchetes. Entre más concreta sea la solicitud, más fácil será
            evaluar la respuesta.
          </p>
        </div>

        <div className="mt-8 grid gap-4 lg:grid-cols-3">
          {requestTemplates.map((template) => (
            <article key={template.id} className="flex flex-col rounded-card border border-line bg-surface p-5">
              <h3 className="font-display text-lg font-semibold">{template.title}</h3>
              <p className="mt-3 flex-1 text-sm leading-6 text-muted">{template.text}</p>
              <button
                type="button"
                onClick={() => copyTemplate(template.id, template.text)}
                className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-line-strong bg-paper px-4 text-sm font-semibold text-ink transition hover:bg-surface"
              >
                {copiedId === template.id ? (
                  <>
                    <Check className="h-4 w-4 text-brand" /> Copiado
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" /> Copiar modelo
                  </>
                )}
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[0.85fr_1.15fr] lg:px-8">
          <GuidePanel icon={ShieldCheck} title="Criterio ODJ">
            <p>
              Consultar sin sobreinterpretar. ODJ ayuda a localizar, contrastar y preservar
              documentos; no convierte una ausencia documental en conclusión legal.
            </p>
          </GuidePanel>
          <div className="grid gap-3 sm:grid-cols-2">
            {odjCriteria.map((criterion) => (
              <div key={criterion} className="flex gap-3 rounded-card border border-line bg-paper p-4">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                <p className="text-sm leading-6 text-muted">{criterion}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Seguimiento
            </p>
            <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
              Qué hacer con la respuesta
            </h2>
            <p className="mt-4 text-[15px] leading-7 text-muted">
              Sube el folio, fecha, sujeto obligado, documento recibido y enlaces fuente a tu
              bitácora. Si la respuesta es incompleta o no corresponde, revisa si procede una
              aclaración o recurso de revisión en la propia PNT.
            </p>
            <p className="mt-5 rounded-card border border-line bg-surface p-5 text-sm leading-6 text-muted">
              En solicitudes por PNT se genera un folio para seguimiento. La solicitud debe describir
              la información buscada y puede incluir datos que ayuden a localizarla; si la descripción
              no basta, la autoridad puede pedir aclaración dentro del procedimiento.
            </p>
            <a
              href={PNT_URL}
              target="_blank"
              rel="noreferrer"
              className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl bg-brand-strong px-5 text-sm font-semibold text-white transition hover:bg-brand"
            >
              Ir a la Plataforma <ExternalLink className="h-4 w-4" />
            </a>
          </div>

          <GuidePanel icon={FileQuestion} title="Fuentes consultadas">
            <ul className="space-y-3">
              {sourceLinks.map((source) => (
                <li key={source.href}>
                  <a
                    href={source.href}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-start gap-2 font-semibold text-brand transition hover:text-ink"
                  >
                    <span>{source.label}</span>
                    <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0" />
                  </a>
                </li>
              ))}
            </ul>
            <p className="mt-5 text-xs leading-5 text-faint">
              Esta guía es orientativa y no sustituye asesoría legal.
            </p>
          </GuidePanel>
        </div>
      </section>
    </div>
  );
}

function GuidePanel({
  icon: Icon,
  title,
  children,
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
}) {
  return (
    <aside className="rounded-card border border-line bg-paper p-6">
      <span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-soft text-brand">
        <Icon className="h-5 w-5" />
      </span>
      <h2 className="mt-4 font-display text-xl font-semibold">{title}</h2>
      <div className="mt-3 text-sm leading-6 text-muted">{children}</div>
    </aside>
  );
}
