import { useEffect, useRef, useState, type ReactNode } from "react";
import gsap from "gsap";
import Lenis from "lenis";
import { Link } from "react-router-dom";
import {
  Archive,
  ArrowRight,
  ArrowUpRight,
  Check,
  Code2,
  EyeOff,
  FileSearch,
  Fingerprint,
  Github,
  Globe,
  Scale,
  ScrollText,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";
import { api, StatsResponse } from "./api";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const REPO_URL = "https://github.com/Chaetard/open-data-jalisco";
const HERO_VIDEO_URL =
  "https://rr4---sn-hxb5j5cax-bqak.googlevideo.com/videoplayback?expire=1781920887&ei=F6A1au64IfiWsfIP1MvPsQI&ip=2806%3A3aa%3A109%3A300%3A406b%3A9e1a%3A7a39%3A4d8d&id=o-AP25nb-JytP64YYpRUJli2LJzENnF6qNw91LTb8XHfK5&itag=313&aitags=133%2C134%2C135%2C136%2C137%2C160%2C242%2C243%2C244%2C247%2C248%2C271%2C278%2C313&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=444&gcr=mx&bui=ARmQxEVmTaPjU4OpnAn-djEH4O1grlgd_rp4i-f_RMuoXJjmcej8EAgtUyMMl3drB5es4wByJms2lbur&vprv=1&svpuc=1&mime=video%2Fwebm&ns=U0nsuoMJsQ26Of61m4-v1LEW&rqh=1&gir=yes&clen=113070589&dur=80.121&lmt=1716254546601793&keepalive=yes&lmw=1&fexp=51565115,51565682,51987687&c=TVHTML5&sefc=1&txp=531F224&n=7ZnQ1nIjT66DKA&sparams=expire%2Cei%2Cip%2Cid%2Caitags%2Csource%2Crequiressl%2Cxpc%2Cgcr%2Cbui%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Cgir%2Cclen%2Cdur%2Clmt&sig=AHEqNM4wRQIgbLrvBHJu3v5_dZmm_-bmY_owRu36aJthdh177dWD0KMCIQCVI_RO-lsapQxoQZ2TuW8iLXGaEqzGaH71C3WkwsQb5Q%3D%3D&rm=sn-opqpmoxuhm-j00e7l,sn-2imk7l&rrc=79,104&req_id=b9f097d5cb8da3ee&cmsv=e&rms=rdu,au&redirect_counter=2&cms_redirect=yes&ipbypass=yes&met=1781899303,&mh=zk&mip=2806:261:6483:9d59:b523:5d03:6e6:a9af&mm=29&mn=sn-hxb5j5cax-bqak&ms=rdu&mt=1781898788&mv=m&mvi=4&pl=53&lsparams=cps,ipbypass,met,mh,mip,mm,mn,ms,mv,mvi,pl,rms&lsig=APaTxxMwRAIgG8Ujao_KRovMWMEFvo1puzesaIqYGUs25ZWiN-6GCLkCIDaFI8TjmQFIP7ILIlThyYItn8FXPNMv05SkAnlIT-dN";

const endpoints: Array<{ method: "GET" | "POST"; path: string; desc: string }> = [
  { method: "GET", path: "/stats", desc: "Métricas agregadas del corpus." },
  { method: "GET", path: "/sources", desc: "Fuentes oficiales (municipios y portales)." },
  { method: "GET", path: "/documents", desc: "Documentos con filtros y paginación." },
  { method: "POST", path: "/search", desc: "Búsqueda semántica sobre el texto extraído." },
  { method: "POST", path: "/ask", desc: "Agente: pregunta en lenguaje natural con citas." },
  { method: "GET", path: "/manifests", desc: "Manifiestos de integridad del corpus." },
  { method: "GET", path: "/source", desc: "Divulgación de código fuente (AGPLv3 §13)." },
];

const principles = [
  {
    icon: Scale,
    title: "Neutralidad política",
    body: "Apartidista. El sistema no asume corrupción, dolo ni mala fe. Cuando detecta inconsistencias documentales las describe; no las convierte en acusaciones.",
  },
  {
    icon: Fingerprint,
    title: "Trazabilidad documental",
    body: "La fuente de verdad no es la IA ni la base vectorial: son los documentos originales, sus URLs oficiales, fechas de captura, hashes y manifiestos.",
  },
  {
    icon: Archive,
    title: "Integridad y preservación",
    body: "Los documentos capturados no se modifican. Si la fuente oficial cambia uno, se guarda una versión nueva con nuevo hash; jamás se sobrescribe la anterior.",
  },
  {
    icon: Code2,
    title: "Transparencia técnica",
    body: "Código abierto. Scrapers, pipelines, extractores, manifiestos y criterios de contribución son públicamente auditables.",
  },
  {
    icon: Globe,
    title: "Acceso público y gratuito",
    body: "Consulta gratuita de la información pública procesada, sujeta a límites operativos razonables, sin convertirse en una barrera comercial.",
  },
  {
    icon: EyeOff,
    title: "Protección de datos personales",
    body: "Que un documento sea público no obliga a amplificar datos personales. Aplican criterios de minimización, contexto y responsabilidad.",
  },
];

const isList = [
  "Encuentra documentos públicos dispersos en portales y formatos distintos.",
  "Los preserva con huella SHA-256 y versionado por URL.",
  "Permite buscarlos por contenido con búsqueda semántica.",
  "Mantiene siempre la trazabilidad hacia la fuente oficial.",
];

const isNotList = [
  "Una autoridad fiscalizadora, auditoría oficial, fiscalía o tribunal.",
  "Una herramienta partidista ni de propaganda.",
  "Una plataforma para acusar personas.",
  "Una sustitución de solicitudes formales ni de las fuentes oficiales.",
  "Una prueba automática de irregularidades.",
];

const documentTypes = [
  "Contratos",
  "Licitaciones",
  "Adjudicaciones",
  "Compras y obra pública",
  "Reglamentos",
  "Actas",
  "Presupuestos",
  "Leyes de ingresos y egresos",
  "Transparencia activa",
  "Directorios institucionales",
  "Gacetas municipales",
];

const audiences = [
  "Ciudadanía",
  "Estudiantes",
  "Periodistas",
  "Investigadores",
  "Organizaciones civiles",
  "Desarrolladores",
  "Áreas de transparencia",
];

// Catálogo a dos columnas: la primera lleva el sobrante cuando el total es impar.
const documentColumns = [
  documentTypes.slice(0, Math.ceil(documentTypes.length / 2)),
  documentTypes.slice(Math.ceil(documentTypes.length / 2)),
];

export default function Landing() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const pageRef = useRef<HTMLDivElement | null>(null);
  const heroBgRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void api.stats({ signal: controller.signal }).then(setStats).catch(() => undefined);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!pageRef.current) return;
    // Mismo patrón de entrada que el explorador (gsap.context + clearProps evita
    // que un tween interrumpido por StrictMode deje elementos en opacity:0).
    const ctx = gsap.context(() => {
      gsap.from("[data-enter]", {
        y: 14,
        opacity: 0,
        duration: 0.5,
        stagger: 0.06,
        ease: "power2.out",
        clearProps: "opacity,transform",
      });
    }, pageRef);
    return () => ctx.revert();
  }, []);

  // Scroll suave (Lenis) + parallax del fondo del hero. Acotado a esta vista:
  // se destruye al desmontar para no afectar al explorador ni al asistente.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const lenis = new Lenis({ lerp: 0.1 });
    let frame = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);
    const onScroll = ({ scroll }: { scroll: number }) => {
      if (heroBgRef.current) gsap.set(heroBgRef.current, { y: scroll * 0.35 });
    };
    lenis.on("scroll", onScroll);
    return () => {
      cancelAnimationFrame(frame);
      lenis.destroy();
    };
  }, []);

  const indexed =
    stats?.documents_by_status.find((status) => status.status === "indexed")?.count ?? null;

  return (
    <div ref={pageRef}>
      {/* ── Hero ─────────────────────────────────────────────────────────────── */}
      <section className="hero-shell relative overflow-hidden border-b border-line bg-[#101814] text-white">
        {/* Capa de fondo con parallax (movida por Lenis vía heroBgRef). */}
        <div
          ref={heroBgRef}
          className="pointer-events-none absolute inset-x-0 -top-[12%] h-[132%] will-change-transform"
          aria-hidden
        >
          <video
            className="hero-image absolute inset-0 h-full w-full object-cover"
            src={HERO_VIDEO_URL}
            autoPlay
            muted
            loop
            playsInline
            preload="metadata"
          />
          <div className="hero-image-wash absolute inset-0" />
          <div className="hero-mesh absolute inset-0" />
          <div className="tech-grid absolute inset-0 opacity-[0.12]" />
        </div>

        <div className="hero-atmosphere pointer-events-none absolute inset-0" aria-hidden />

        <a
          href="https://www.youtube.com/watch?v=BgztRUjJ3Oo"
          target="_blank"
          rel="noreferrer"
          className="hero-credit group absolute z-10 inline-flex h-8 min-w-8 items-center justify-center overflow-hidden rounded-full border border-white/16 bg-[#101814]/42 px-2.5 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-white/72 backdrop-blur transition-all duration-300 hover:w-[13.5rem] hover:border-white/30 hover:bg-[#101814]/64 hover:text-white focus-visible:w-[13.5rem] focus-visible:border-white/30 focus-visible:bg-[#101814]/64 focus-visible:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/28"
          aria-label="Video de fondo por EDavidM en YouTube"
        >
          <span className="shrink-0">!</span>
          <span className="ml-2 hidden whitespace-nowrap group-hover:inline group-focus-visible:inline">
            Video: EDavidM / YouTube
          </span>
        </a>

        <div className="relative mx-auto flex h-full max-w-7xl flex-col justify-end px-4 pb-5 pt-10 sm:px-6 sm:pb-7 lg:px-8 lg:pt-12">
          <div className="max-w-6xl pb-4 sm:pb-5 lg:pb-6">
            <div>
              <h1
                data-enter
                className="max-w-[15ch] font-display text-[2.6rem] font-medium leading-[0.94] tracking-normal text-white sm:text-[4.35rem] lg:text-[5.65rem]"
              >
                La memoria pública de Jalisco, organizada para que cualquiera pueda buscar,
                entender y verificar.
              </h1>
              <p
                data-enter
                className="mt-5 max-w-3xl text-[14.5px] leading-7 text-[#d7e1d9] sm:text-[16px]"
              >
                PDFs, hojas y portales municipales convertidos en un índice de lectura pública:
                URL oficial, hash SHA-256, texto extraído y citas recuperables desde API.
              </p>

              <div data-enter className="mt-6 flex flex-wrap items-center gap-3">
                <Link
                  to="/explorador"
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-white px-5 text-sm font-semibold text-[#101814] transition hover:bg-[#d9efe5]"
                >
                  Abrir el corpus
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/api"
                  className="inline-flex h-11 items-center gap-2 rounded-xl border border-white/20 bg-white/8 px-5 text-sm font-semibold text-white backdrop-blur transition hover:border-white/35 hover:bg-white/14"
                >
                  <ScrollText className="h-4 w-4" />
                  Ver contrato API
                </Link>
                <a
                  href={REPO_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-11 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-[#b8c8bd] transition hover:text-white"
                >
                  <Github className="h-4 w-4" />
                  Código fuente
                  <ArrowUpRight className="h-4 w-4" />
                </a>
              </div>

              <dl
                data-enter
                className="hero-proof mt-8 grid gap-3 border-t border-white/14 pt-4 sm:grid-cols-2 lg:grid-cols-4"
              >
                <CountUpStat label="Fuentes" value={stats?.sources_total} />
                <CountUpStat label="Documentos" value={stats?.documents_total} />
                <CountUpStat label="Indexados" value={indexed} />
                <CountUpStat label="Fragmentos" value={stats?.chunks_total} />
              </dl>
            </div>
          </div>
        </div>
      </section>

      {/* ── Visión ───────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div data-enter className="max-w-3xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
            La visión
          </p>
          <p className="mt-5 font-display text-[1.75rem] leading-snug tracking-tight text-ink sm:text-[2.1rem]">
            Imagina poder preguntar{" "}
            <span className="text-brand">
              “¿qué contratos de obra pública hubo en Tala durante 2021?”
            </span>{" "}
            y recibir documentos, fechas, enlaces oficiales y fragmentos verificables —no una
            opinión.
          </p>
          <p className="mt-5 max-w-2xl text-[15px] leading-7 text-muted">
            La información pública existe para ser consultada, reutilizada y entendida. Pero suele
            vivir dispersa en PDFs, hojas de cálculo y portales poco indexados. Open Data Jalisco
            reduce esa fricción con una capa abierta de consulta documental que nunca pierde de
            vista la fuente original.
          </p>
        </div>
      </section>

      {/* ── Principios ───────────────────────────────────────────────────────── */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
          <div data-enter className="max-w-2xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Principios
            </p>
            <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
              Seis compromisos que rigen el proyecto
            </h2>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {principles.map(({ icon: Icon, title, body }) => (
              <article key={title} data-enter className="rounded-card border border-line bg-paper p-6">
                <span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-soft text-brand">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 font-display text-lg font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ── Qué es / Qué no es ───────────────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div className="grid gap-4 lg:grid-cols-2">
          <article data-enter className="rounded-card border border-line bg-surface p-7">
            <h2 className="font-display text-xl font-semibold">Qué hace</h2>
            <ul className="mt-5 space-y-3">
              {isList.map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm leading-6 text-[#46524a]">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                  {item}
                </li>
              ))}
            </ul>
          </article>
          <article data-enter className="rounded-card border border-line bg-surface p-7">
            <h2 className="font-display text-xl font-semibold">Qué no es</h2>
            <ul className="mt-5 space-y-3">
              {isNotList.map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm leading-6 text-[#46524a]">
                  <X className="mt-0.5 h-4 w-4 shrink-0 text-danger-ink" />
                  {item}
                </li>
              ))}
            </ul>
            <p className="mt-6 rounded-lg border-l-2 border-line-strong bg-paper px-4 py-3 text-xs leading-5 text-muted">
              La ausencia de un documento en la base no significa que no exista. Una inconsistencia
              detectada no significa, por sí misma, una irregularidad legal.
            </p>
          </article>
        </div>
      </section>

      {/* ── La API ───────────────────────────────────────────────────────────── */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:px-8">
          <div data-enter>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              API pública
            </p>
            <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
              REST sobre FastAPI, sólo lectura, sin llaves
            </h2>
            <p className="mt-4 text-[15px] leading-7 text-muted">
              Endpoints JSON sin autenticación, documentados con OpenAPI (
              <code className="rounded bg-paper px-1.5 py-0.5 font-mono text-[0.85em]">/docs</code> y{" "}
              <code className="rounded bg-paper px-1.5 py-0.5 font-mono text-[0.85em]">
                /openapi.json
              </code>
              ). La búsqueda corre sobre embeddings multilingües (
              <code className="rounded bg-paper px-1.5 py-0.5 font-mono text-[0.85em]">
                multilingual-e5-small
              </code>
              , 384d) indexados en PostgreSQL + pgvector.
            </p>

            <div className="mt-6">
              <CodeBlock>{`curl -X POST http://localhost:8000/search \\
  -H "Content-Type: application/json" \\
  -d '{"q":"presupuesto municipal","limit":5}'`}</CodeBlock>
            </div>

            <Link
              to="/api"
              className="mt-6 inline-flex items-center gap-1.5 text-sm font-semibold text-brand transition hover:text-ink"
            >
              Referencia completa de la API <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <div data-enter className="overflow-hidden rounded-card border border-line bg-paper">
            <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
              <h3 className="font-display text-base font-semibold">Endpoints principales</h3>
              <span className="text-xs text-muted">{endpoints.length}</span>
            </div>
            <ul className="divide-y divide-line">
              {endpoints.map((endpoint) => (
                <li key={endpoint.path} className="flex items-start gap-3 px-5 py-3.5">
                  <span
                    className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold ${
                      endpoint.method === "POST"
                        ? "bg-brand-soft text-brand"
                        : "bg-surface text-muted"
                    }`}
                  >
                    {endpoint.method}
                  </span>
                  <div className="min-w-0">
                    <code className="font-mono text-sm font-semibold text-ink">{endpoint.path}</code>
                    <p className="mt-0.5 text-xs leading-5 text-muted">{endpoint.desc}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Alcance + audiencia ──────────────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-[1.4fr_1fr]">
          <div data-enter>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Alcance documental
            </p>
            <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
              Qué tipo de información se indexa
            </h2>
            <p className="mt-4 max-w-xl text-[15px] leading-7 text-muted">
              Nuevas fuentes se incorporan mediante configuración versionada (YAML), no por
              modificación del código de producción —así la incorporación es auditable y replicable.
            </p>
            <div className="mt-8 grid gap-x-12 sm:grid-cols-2">
              {documentColumns.map((column, columnIndex) => (
                <ul key={columnIndex} className="divide-y divide-line">
                  {column.map((type, rowIndex) => (
                    <li key={type} className="flex items-baseline gap-3.5 py-2.5">
                      <span className="font-mono text-[11px] tabular-nums text-faint">
                        {String(columnIndex * documentColumns[0].length + rowIndex + 1).padStart(2, "0")}
                      </span>
                      <span className="text-[15px] text-ink">{type}</span>
                    </li>
                  ))}
                </ul>
              ))}
            </div>
          </div>
          <div data-enter>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              ¿Para quién?
            </p>
            <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
              Infraestructura para consultar y verificar
            </h2>
            <p className="mt-4 text-[15px] leading-7 text-muted">
              Pensado como infraestructura útil para quien necesite encontrar, comparar o auditar
              información pública municipal.
            </p>
            <p className="mt-7 font-display text-[1.4rem] leading-relaxed tracking-tight text-ink">
              {audiences.map((audience, index) => (
                <span key={audience}>
                  {audience}
                  {index < audiences.length - 1 ? (
                    <span className="text-line-strong"> · </span>
                  ) : null}
                </span>
              ))}
            </p>
          </div>
        </div>
      </section>

      {/* ── Para desarrolladores ─────────────────────────────────────────────── */}
      <section className="border-y border-line bg-surface">
        <div className="mx-auto grid max-w-7xl items-start gap-10 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:px-8">
          <div data-enter>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
              Open source
            </p>
            <h2 className="mt-4 font-display text-[2rem] font-medium leading-tight tracking-tight">
              <Terminal className="mr-2 inline h-7 w-7 -translate-y-0.5 text-brand" />
              Clónalo, audítalo, levántalo
            </h2>
            <p className="mt-4 text-[15px] leading-7 text-muted">
              Backend en Python 3.12 (FastAPI + Typer) sobre PostgreSQL con pgvector, gestionado con
              <code className="mx-1 rounded bg-paper px-1.5 py-0.5 font-mono text-[0.85em]">uv</code>;
              frontend en React + Vite. El setup completo —base de datos, variables de entorno y
              embeddings— está documentado paso a paso en el README del repositorio.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-brand-strong px-5 text-sm font-semibold text-white transition hover:bg-brand"
              >
                <Github className="h-4 w-4" />
                Guía de instalación
                <ArrowUpRight className="h-4 w-4" />
              </a>
              <Link
                to="/api"
                className="inline-flex h-11 items-center gap-2 rounded-xl border border-line-strong bg-paper px-5 text-sm font-semibold text-ink transition hover:bg-surface"
              >
                <ScrollText className="h-4 w-4" />
                Referencia de la API
              </Link>
            </div>
          </div>

          <div data-enter className="lg:pt-1">
            <CodeBlock>{`# Clona el repositorio
git clone ${REPO_URL}.git
cd open-data-jalisco

# Sigue la "Sección técnica" del README:
#   · Postgres + pgvector   make db-up
#   · entorno y deps        uv sync --extra dev
#   · API y frontend        make api  ·  npm run dev`}</CodeBlock>
          </div>
        </div>
      </section>

      {/* ── IA + licencia ────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div className="grid gap-4 lg:grid-cols-2">
          <article data-enter className="rounded-card border border-line bg-surface p-7">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-soft text-brand">
              <Sparkles className="h-5 w-5" />
            </span>
            <h2 className="mt-4 font-display text-xl font-semibold">IA como interfaz, no autoridad</h2>
            <p className="mt-3 text-sm leading-6 text-muted">
              El asistente no responde afirmaciones sustantivas sin respaldo documental recuperado.
              Lee los documentos por ti, los resume y cita la evidencia; si no la encuentra, lo dice.
              La fuente de verdad siempre es el documento original, no el modelo.
            </p>
          </article>
          <article data-enter className="rounded-card border border-line bg-surface p-7">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-brand-soft text-brand">
              <Scale className="h-5 w-5" />
            </span>
            <h2 className="mt-4 font-display text-xl font-semibold">Licencia AGPL-3.0-or-later</h2>
            <p className="mt-3 text-sm leading-6 text-muted">
              Si operas una versión modificada como servicio, debes publicar tus cambios bajo los
              mismos términos. Toda instancia expone{" "}
              <code className="rounded bg-paper px-1.5 py-0.5 font-mono text-[0.85em]">/source</code>{" "}
              con el repositorio y la versión en ejecución. Los documentos oficiales recopilados no
              son propiedad del proyecto: se preservan, referencian e indexan.
            </p>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-brand transition hover:text-ink"
            >
              Ver el repositorio <ArrowUpRight className="h-4 w-4" />
            </a>
          </article>
        </div>
      </section>

      {/* ── CTA final + frase guía ───────────────────────────────────────────── */}
      <section className="border-t border-line bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
          <div
            data-enter
            className="flex flex-col items-start gap-6 lg:flex-row lg:items-center lg:justify-between"
          >
            <div className="max-w-xl">
              <h2 className="font-display text-[2rem] font-medium leading-tight tracking-tight">
                Empieza a explorar el corpus
              </h2>
              <p className="mt-3 text-[15px] leading-7 text-muted">
                Busca por contenido, pregúntale al asistente o contribuye en GitHub para sumar tu
                municipio.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/explorador"
                className="inline-flex h-12 items-center gap-2 rounded-xl bg-brand-strong px-6 text-sm font-semibold text-white transition hover:bg-brand"
              >
                <FileSearch className="h-4 w-4" />
                Abrir el explorador
              </Link>
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-12 items-center gap-2 rounded-xl border border-line-strong bg-paper px-6 text-sm font-semibold text-ink transition hover:bg-surface"
              >
                <Github className="h-4 w-4" />
                Contribuir
              </a>
            </div>
          </div>

          <p
            data-enter
            className="mt-14 border-t border-line pt-10 font-display text-[1.5rem] leading-snug tracking-tight text-ink sm:text-[1.85rem]"
          >
            Información pública, verificable y consultable para una ciudadanía más informada.
          </p>
        </div>
      </section>
    </div>
  );
}

// Contador que cuenta hasta el valor con GSAP. Cada instancia gestiona su propio
// estado para no re-renderizar a todo el hero en cada frame del tween.
function CountUpStat({ label, value }: { label: string; value?: number | null }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (value == null) return;
    if (prefersReducedMotion()) {
      setDisplay(value);
      return;
    }
    const counter = { v: 0 };
    const tween = gsap.to(counter, {
      v: value,
      duration: 1.4,
      ease: "power3.out",
      onUpdate: () => setDisplay(Math.round(counter.v)),
    });
    return () => {
      tween.kill();
    };
  }, [value]);

  return (
    <div aria-label={label}>
      <p className="font-display text-3xl font-semibold tabular-nums leading-none sm:text-[2.25rem]">
        {value == null ? "-" : display.toLocaleString("es-MX")}
      </p>
      <p className="mt-1.5 text-[10px] uppercase tracking-[0.14em] text-faint">{label}</p>
    </div>
  );
}

function CodeBlock({ children }: { children: ReactNode }) {
  return (
    <pre className="overflow-x-auto rounded-xl bg-brand-strong px-4 py-3.5 font-mono text-[12.5px] leading-relaxed text-[#e8ece6]">
      <code>{children}</code>
    </pre>
  );
}
