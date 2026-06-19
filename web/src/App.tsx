import { useEffect, useState, type ReactNode } from "react";
import { Github, Landmark } from "lucide-react";
import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink as RouterNavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { api } from "./api";
import Landing from "./Landing";
import Explorer from "./Explorer";
import ApiDocs from "./ApiDocs";
import Assistant from "./Assistant";

// El asistente usa un layout de alto fijo (sin footer); el resto comparte el
// layout scrollable estándar. Solo necesitamos distinguir ese caso.
const isAssistantPath = (pathname: string) => pathname === "/asistente" || pathname === "/ask";

const migrateLegacyHashRoute = () => {
  if (typeof window === "undefined" || !window.location.hash.startsWith("#/")) return;

  const [legacyPath, legacyQuery] = window.location.hash.slice(1).split("?");
  const query = legacyQuery ? `?${legacyQuery}` : "";
  const nextPath =
    legacyPath === "/asistente" || legacyPath === "/ask"
      ? `/asistente${query}`
      : legacyPath === "/docs"
        ? `/api${query}`
        : "/";

  window.history.replaceState(null, "", nextPath);
};

function AppShell() {
  const location = useLocation();
  const isLanding = location.pathname === "/";
  const [apiOnline, setApiOnline] = useState(false);
  const [apiMeta, setApiMeta] = useState("API local");
  const [landingScrolled, setLandingScrolled] = useState(false);
  const [landingPastHero, setLandingPastHero] = useState(false);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  useEffect(() => {
    const controller = new AbortController();
    api
      .health({ signal: controller.signal })
      .then((health) => {
        setApiOnline(health.status === "ok");
        setApiMeta(`${health.version} · ${health.environment}`);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setApiOnline(false);
        setApiMeta("Sin conexión");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!isLanding) {
      setLandingScrolled(false);
      setLandingPastHero(false);
      return;
    }

    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const headerHeight = parseFloat(
          getComputedStyle(document.documentElement).getPropertyValue("--site-header-height"),
        ) || 64;
        setLandingScrolled(window.scrollY > 2);
        setLandingPastHero(window.scrollY >= window.innerHeight - headerHeight - 8);
      });
    };

    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [isLanding]);

  if (isAssistantPath(location.pathname)) {
    return (
      <div className="assistant-shell flex h-dvh flex-col overflow-hidden bg-paper text-ink">
        <SiteHeader apiOnline={apiOnline} apiMeta={apiMeta} />
        <Routes>
          <Route path="/asistente" element={<Assistant />} />
          <Route path="/ask" element={<Navigate to="/asistente" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    );
  }

  return (
    <main className="flex min-h-dvh flex-col bg-paper text-ink">
      <SiteHeader
        apiOnline={apiOnline}
        apiMeta={apiMeta}
        floating={isLanding}
        blurred={isLanding && landingScrolled}
        tone={isLanding ? (landingPastHero ? "green" : "transparent") : "light"}
      />

      <div className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/explorador" element={<Explorer />} />
          <Route path="/api" element={<ApiDocs />} />
          <Route path="/docs" element={<Navigate to="/api" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>

      <footer className="mt-4 border-t border-line px-4 py-6 text-sm text-muted sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span className="font-display">Open Data Jalisco — proyecto ciudadano y open source</span>
          <div className="flex gap-5">
            <Link to="/explorador" className="transition hover:text-brand">
              Explorador
            </Link>
            <Link to="/asistente" className="transition hover:text-brand">
              Asistente
            </Link>
            <Link to="/api" className="transition hover:text-brand">
              Documentación
            </Link>
            <a
              href="https://github.com/Chaetard/open-data-jalisco"
              target="_blank"
              rel="noreferrer"
              className="transition hover:text-brand"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}

function SiteHeader({
  apiOnline,
  apiMeta,
  blurred = true,
  floating = false,
  tone = "light",
}: {
  apiOnline: boolean;
  apiMeta: string;
  blurred?: boolean;
  floating?: boolean;
  tone?: "light" | "transparent" | "green";
}) {
  const isDark = tone === "transparent" || tone === "green";
  const headerTone =
    tone === "transparent"
      ? blurred
        ? "border-white/10 bg-[#101814]/18 text-white shadow-[0_12px_32px_rgba(16,24,20,0.08)]"
        : "border-transparent bg-transparent text-white"
      : tone === "green"
        ? "border-white/10 bg-[#1f5b43]/96 text-white shadow-[0_16px_40px_rgba(16,24,20,0.16)]"
        : "border-line bg-paper/85 text-ink";
  const blurClass = blurred ? "backdrop-blur" : "backdrop-blur-0";

  return (
    <header
      className={`${
        floating ? "fixed inset-x-0 top-0" : "sticky top-0"
      } z-50 h-[var(--site-header-height)] shrink-0 border-b transition-[background-color,border-color,box-shadow,backdrop-filter] duration-300 ${blurClass} ${headerTone}`}
    >
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <span
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${
              isDark ? "bg-white/10 text-[#b8efd5] ring-1 ring-white/12" : "bg-brand-strong text-white"
            }`}
          >
            <Landmark className="h-5 w-5" />
          </span>
          <div className="min-w-0 leading-tight">
            <p className="truncate font-display text-base font-semibold">Open Data Jalisco</p>
          </div>
        </Link>

        <nav className="flex items-center gap-4 text-sm font-semibold sm:gap-5">
          <NavLink to="/" tone={tone}>
            Inicio
          </NavLink>
          <NavLink to="/explorador" tone={tone}>
            Explorador
          </NavLink>
          <NavLink to="/asistente" tone={tone}>
            Asistente
          </NavLink>
          <NavLink to="/api" tone={tone}>
            API
          </NavLink>
        </nav>

        <div className="flex items-center gap-3">
          <span
            className={`hidden items-center gap-2 text-xs font-medium md:inline-flex ${
              isDark ? "text-white/70" : "text-muted"
            }`}
            title={apiOnline ? "API en línea" : "API sin conexión"}
          >
            <span
              className={`h-2 w-2 rounded-full ${apiOnline ? (isDark ? "bg-[#b8efd5]" : "bg-brand") : "bg-warn-ink"}`}
              aria-hidden
            />
            {apiMeta}
          </span>
          <a
            href="https://github.com/Chaetard/open-data-jalisco"
            target="_blank"
            rel="noreferrer"
            className={`grid h-9 w-9 place-items-center rounded-lg border transition ${
              isDark
                ? "border-white/14 text-white/78 hover:bg-white/10 hover:text-white"
                : "border-line-strong hover:bg-surface"
            }`}
            aria-label="Repositorio en GitHub"
          >
            <Github className="h-4 w-4" />
          </a>
        </div>
      </div>
    </header>
  );
}

function NavLink({
  to,
  children,
  tone = "light",
}: {
  to: string;
  children: ReactNode;
  tone?: "light" | "transparent" | "green";
}) {
  const isDark = tone === "transparent" || tone === "green";

  return (
    <RouterNavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `border-b-2 py-1 transition ${
          isDark
            ? isActive
              ? "border-[#b8efd5] text-white"
              : "border-transparent text-white/62 hover:text-white"
            : isActive
              ? "border-brand text-ink"
              : "border-transparent text-muted hover:text-ink"
        }`
      }
    >
      {children}
    </RouterNavLink>
  );
}

function App() {
  migrateLegacyHashRoute();

  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

export default App;
