import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { Link } from "react-router-dom";
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

gsap.registerPlugin(ScrollTrigger);

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const PNT_URL = "https://www.plataformadetransparencia.org.mx/Inicio";

const processSteps: Array<{
  number: string;
  icon: LucideIcon;
  title: string;
  body: string;
  bg: string;
  accent: string;
}> = [
  {
    number: "01",
    icon: Search,
    title: "Busca primero",
    body: "Antes de redactar una solicitud, agota lo que ya es público: revisa el documento en ODJ, en el portal de transparencia del municipio (las obligaciones de oficio del art. 8) y en la propia PNT. Si lo encuentras, te ahorras el trámite; si no, guarda capturas, ligas y fechas de lo que sí consultaste. Eso te sirve para acotar la petición y para mostrar que la información no estaba disponible.",
    bg: "#0c1a2b",
    accent: "#7fb8ff",
  },
  {
    number: "02",
    icon: Building2,
    title: "Define el sujeto obligado",
    body: "Identifica a quién le corresponde tener el documento. En temas municipales suele ser el ayuntamiento, una dirección o secretaría (Obras Públicas, Tesorería, Padrón y Licencias), un organismo público descentralizado (agua, DIF, parques) o un comité. Si no estás seguro, en la PNT puedes dirigir la misma solicitud a varios sujetos obligados a la vez y dejar que cada uno responda lo que le compete.",
    bg: "#181230",
    accent: "#c3a6ff",
  },
  {
    number: "03",
    icon: FileText,
    title: "Pide documentos, no explicaciones",
    body: "El derecho de acceso obliga a entregar documentos que existen, no a generar análisis ni opiniones. Pide copias, versiones públicas, contratos, facturas, actas, padrones, presupuestos, oficios, anexos o bases de datos. Evita preguntas tipo «¿por qué…?» o «¿es correcto que…?»: se contestan con criterios, no con archivos, y suelen derivar en respuestas vagas o en una orientación que alarga el trámite.",
    bg: "#0d1f16",
    accent: "#8fe6b6",
  },
  {
    number: "04",
    icon: CalendarDays,
    title: "Acota periodo y formato",
    body: "Entre más concreta, mejor respuesta. Especifica fechas o ejercicio fiscal, municipio, área, programa, número de contrato, obra o expediente. Pide la entrega en formato digital abierto —CSV, XLSX, PDF buscable o liga de descarga— para poder reutilizar los datos. Acotar bien también reduce que te nieguen la información por «volumen excesivo» o que te cobren reproducción de copias.",
    bg: "#241a0b",
    accent: "#f3c987",
  },
  {
    number: "05",
    icon: ClipboardCheck,
    title: "Da seguimiento",
    body: "Guarda el folio: es tu identificador durante todo el procedimiento. La autoridad tiene plazos para responder y puede pedirte una aclaración dentro del trámite. Si la respuesta es incompleta, no corresponde, clasifica información sin fundarlo o declara inexistencia sin acreditarla, tienes derecho a interponer un recurso de revisión ante el órgano garante —gratuito y desde la misma PNT.",
    bg: "#06201f",
    accent: "#7fe6d8",
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
    id: "sueldos",
    title: "Sueldos y nómina",
    text: "Solicito el tabulador de sueldos y la nómina detallada del personal de [área/dependencia o todo el municipio] correspondiente al periodo [mes/año], desglosada por nombre o clave de empleado, puesto, tipo de plaza (base, confianza, eventual u honorarios), percepciones brutas, deducciones y pago neto.",
  },
  {
    id: "viaticos",
    title: "Viáticos y gastos de representación",
    text: "Solicito la relación de viáticos y gastos de representación ejercidos por [servidor público/área] durante [periodo], indicando motivo, destino, fechas y montos autorizados y comprobados, así como copia digital de los comprobantes fiscales y de los informes de comisión correspondientes.",
  },
  {
    id: "publicidad",
    title: "Publicidad oficial y comunicación social",
    text: "Solicito el monto total y el detalle del gasto en publicidad oficial y comunicación social durante [ejercicio fiscal], desglosado por proveedor o medio de comunicación, número de contrato, concepto, importe y modalidad de contratación, así como copia digital de los contratos respectivos.",
  },
  {
    id: "plantilla",
    title: "Estructura, plantilla y directorio",
    text: "Solicito el organigrama vigente, la plantilla de personal y el directorio de servidores públicos de [dependencia/municipio], indicando nombre, cargo, área de adscripción y tipo de contratación, con su fecha de actualización.",
  },
  {
    id: "licencias",
    title: "Licencias y permisos de construcción",
    text: "Solicito copia digital de la licencia o permiso de construcción y/o uso de suelo otorgado para el predio ubicado en [domicilio o referencia catastral], incluyendo el expediente, dictámenes técnicos, planos autorizados y el comprobante de pago de derechos, correspondiente al periodo [fechas].",
  },
  {
    id: "vehiculos",
    title: "Parque vehicular y combustible",
    text: "Solicito el inventario del parque vehicular de [municipio/dependencia], indicando marca, modelo, placa, área asignada y estatus, así como el gasto en combustible durante [periodo], desglosado por unidad o área y la bitácora o mecanismo de control de cargas.",
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
  const [activeStep, setActiveStep] = useState(0);
  const pageRef = useRef<HTMLDivElement | null>(null);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const railRef = useRef<HTMLDivElement | null>(null);

  // Scroll suave (Lenis) ↔ GSAP ScrollTrigger. Acotado a esta vista: se destruye
  // al desmontar y purga sus ScrollTriggers para no filtrar al resto del SPA.
  useLayoutEffect(() => {
    if (prefersReducedMotion()) return;
    const lenis = new Lenis({ lerp: 0.1 });
    lenis.on("scroll", ScrollTrigger.update);
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);

    const ctx = gsap.context(() => {
      // Reveal progresivo de cualquier bloque marcado con data-reveal.
      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((el) => {
        gsap.from(el, {
          y: 32,
          opacity: 0,
          duration: 0.8,
          ease: "power3.out",
          scrollTrigger: { trigger: el, start: "top 88%", once: true },
        });
      });

      // Stepper fijado: el panel queda sticky vía CSS; este trigger sólo mide el
      // progreso del recorrido para activar el paso y mover el riel.
      if (trackRef.current) {
        ScrollTrigger.create({
          trigger: trackRef.current,
          start: "top top",
          end: "bottom bottom",
          onUpdate: (self) => {
            const i = Math.min(
              processSteps.length - 1,
              Math.floor(self.progress * processSteps.length),
            );
            setActiveStep(i);
            if (railRef.current) gsap.set(railRef.current, { scaleY: self.progress });
          },
        });
      }
    }, pageRef);

    return () => {
      ctx.revert();
      gsap.ticker.remove(tick);
      lenis.destroy();
    };
  }, []);

  const copyTemplate = async (id: string, text: string) => {
    try {
      await copyToClipboard(text);
      setCopiedId(id);
      window.setTimeout(() => setCopiedId((current) => (current === id ? "" : current)), 1800);
    } catch {
      setCopiedId("");
    }
  };

  const active = processSteps[activeStep];

  return (
    <div ref={pageRef} className="bg-paper">
      {/* ── Hero (ocupa la altura visible menos el navbar fijo) ──────────────── */}
      <section className="flex min-h-[calc(100svh-var(--site-header-height))] items-center border-b border-line bg-surface">
        <div className="mx-auto grid w-full max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[1.15fr_0.85fr] lg:px-8">
          <div>
            <p data-reveal className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Guía ciudadana
            </p>
            <h1
              data-reveal
              className="mt-4 max-w-3xl font-display text-[2.35rem] font-medium leading-tight tracking-tight text-ink sm:text-[3.4rem]"
            >
              Usar la PNT cuando ODJ no tenga el documento
            </h1>
            <p data-reveal className="mt-5 max-w-2xl text-[15px] leading-7 text-muted">
              Si Open Data Jalisco no tiene un archivo, no lo inventamos ni lo presentamos como
              hecho. Te mostramos cómo solicitarlo por la Plataforma Nacional de Transparencia con
              una petición clara, técnica y apartidista.
            </p>
            <div data-reveal className="mt-7 flex flex-wrap items-center gap-3">
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

          <div data-reveal>
            <GuidePanel icon={FileSearch} title="Pensada para datos públicos municipales">
              <p>
                Contratos, presupuestos, actas, padrones, pagos, directorios, programas, obras y
                documentos fuente. La guía prioriza solicitudes verificables y útiles para dar
                seguimiento a información municipal.
              </p>
            </GuidePanel>
          </div>
        </div>
      </section>

      {/* ── Qué significa una ausencia ───────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-28 lg:px-8">
        <p data-reveal className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
          Antes de solicitar
        </p>
        <h2
          data-reveal
          className="mt-5 max-w-4xl font-display text-[2.1rem] font-medium leading-tight tracking-tight sm:text-[2.7rem]"
        >
          Que no tengamos un documento no significa que no exista.
        </h2>
        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <p data-reveal className="text-[15px] leading-7 text-muted">
            Puede significar varias cosas: el documento no fue publicado, aún no lo hemos indexado,
            la fuente cambió de liga, el archivo fue retirado, está en otro portal o debe pedirse
            directamente al sujeto obligado.
          </p>
          <p data-reveal className="rounded-card border border-line bg-surface p-6 text-[15px] leading-7">
            La ausencia en ODJ no prueba irregularidad por sí sola. Sirve como punto de partida para
            una solicitud mejor redactada y con trazabilidad.
          </p>
        </div>
      </section>

      {/* ── Proceso: stepper fijado (scrollytelling, color por paso) ─────────── */}
      <section
        id="proceso"
        ref={trackRef}
        className="relative text-white"
        style={{ backgroundColor: active.bg, transition: "background-color 700ms ease" }}
      >
        <div className="sticky top-0 flex min-h-screen items-center overflow-hidden">
          <div className="pointer-events-none absolute inset-0 opacity-[0.07]">
            <div className="tech-grid absolute inset-0" />
          </div>

          <div className="relative mx-auto grid w-full max-w-7xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
            {/* Riel de progreso + índice de pasos */}
            <div className="flex gap-6">
              <div className="relative w-px shrink-0 bg-white/15">
                <div
                  ref={railRef}
                  className="absolute inset-x-0 top-0 h-full origin-top"
                  style={{ backgroundColor: active.accent, transition: "background-color 700ms ease" }}
                  aria-hidden
                />
              </div>
              <ol className="flex flex-col justify-center gap-4">
                {processSteps.map((step, i) => (
                  <li
                    key={step.number}
                    className={`flex items-center gap-3 font-mono text-sm transition-all duration-500 ${
                      i === activeStep ? "text-white" : i < activeStep ? "text-white/45" : "text-white/30"
                    }`}
                  >
                    <span style={i === activeStep ? { color: active.accent } : undefined}>
                      {step.number}
                    </span>
                    <span className="hidden sm:inline">{step.title}</span>
                  </li>
                ))}
              </ol>
            </div>

            {/* Contenido del paso activo (cross-fade apilado) */}
            <div className="relative min-h-[20rem]">
              {processSteps.map((step, i) => {
                const Icon = step.icon;
                return (
                  <article
                    key={step.number}
                    className={`absolute inset-0 transition-all duration-700 ${
                      i === activeStep
                        ? "translate-y-0 opacity-100"
                        : "pointer-events-none translate-y-6 opacity-0"
                    }`}
                  >
                    <span
                      className="grid h-12 w-12 place-items-center rounded-xl bg-white/10"
                      style={{ color: step.accent }}
                    >
                      <Icon className="h-6 w-6" />
                    </span>
                    <p className="mt-6 font-display text-[5rem] font-medium leading-none text-white/12">
                      {step.number}
                    </p>
                    <h3 className="mt-2 font-display text-[2rem] font-semibold leading-tight sm:text-[2.6rem]">
                      {step.title}
                    </h3>
                    <p className="mt-5 max-w-xl text-[15px] leading-7 text-[#dbe3dd] sm:text-[17px]">
                      {step.body}
                    </p>
                  </article>
                );
              })}
            </div>
          </div>
        </div>

        {/* Altura del recorrido: una pantalla por paso para dar margen de scroll. */}
        <div aria-hidden style={{ height: `${processSteps.length * 100}vh` }} />
      </section>

      {/* ── Modelos para copiar ──────────────────────────────────────────────── */}
      <section id="modelos" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-28 lg:px-8">
        <div data-reveal className="max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            Redacción
          </p>
          <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight sm:text-[2.6rem]">
            Modelos para copiar y adaptar
          </h2>
          <p className="mt-4 text-[15px] leading-7 text-muted">
            Nueve plantillas sobre lo que más pide la ciudadanía. Cambia los campos entre corchetes:
            entre más concreta sea la solicitud, más fácil será evaluar la respuesta.
          </p>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {requestTemplates.map((template) => (
            <article
              key={template.id}
              data-reveal
              className="flex flex-col rounded-card border border-line bg-surface p-6"
            >
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

      {/* ── Criterio ODJ ─────────────────────────────────────────────────────── */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 sm:py-28 lg:grid-cols-[0.85fr_1.15fr] lg:px-8">
          <div data-reveal>
            <GuidePanel icon={ShieldCheck} title="Criterio ODJ">
              <p>
                Consultar sin sobreinterpretar. ODJ ayuda a localizar, contrastar y preservar
                documentos; no convierte una ausencia documental en conclusión legal.
              </p>
            </GuidePanel>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {odjCriteria.map((criterion) => (
              <div
                key={criterion}
                data-reveal
                className="flex gap-3 rounded-card border border-line bg-paper p-4"
              >
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                <p className="text-sm leading-6 text-muted">{criterion}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Seguimiento + fuentes ────────────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-28 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-[1.05fr_0.95fr]">
          <div data-reveal>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Seguimiento
            </p>
            <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight sm:text-[2.6rem]">
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
            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href={PNT_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-brand-strong px-5 text-sm font-semibold text-white transition hover:bg-brand"
              >
                Ir a la Plataforma <ExternalLink className="h-4 w-4" />
              </a>
              <Link
                to="/explorador"
                className="inline-flex h-11 items-center gap-2 rounded-xl border border-line-strong bg-paper px-5 text-sm font-semibold text-ink transition hover:bg-surface"
              >
                <FileSearch className="h-4 w-4" /> Buscar primero en ODJ
              </Link>
            </div>
          </div>

          <div data-reveal>
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
