import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

const DEFAULT_SITE_URL = "http://localhost:5173";
const SITE_TITLE = "Open Data Jalisco | Consulta pública verificable";
const SITE_DESCRIPTION =
  "Consulta documentos públicos municipales de Jalisco con trazabilidad hacia fuentes oficiales, manifests de integridad y búsqueda semántica sobre evidencia verificable.";

const normalizeSiteUrl = (value: string) => value.replace(/\/+$/, "");

const seoHtmlPlugin = (siteUrl: string): Plugin => ({
  name: "open-data-jalisco-seo-html",
  transformIndexHtml(html) {
    const buildDate = new Date().toISOString();
    return html
      .replaceAll("%SITE_URL%", siteUrl)
      .replaceAll("%SITE_TITLE%", SITE_TITLE)
      .replaceAll("%SITE_DESCRIPTION%", SITE_DESCRIPTION)
      .replaceAll("%BUILD_DATE%", buildDate);
  },
});

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const siteUrl = normalizeSiteUrl(env.VITE_SITE_URL || env.SITE_URL || DEFAULT_SITE_URL);

  return {
    plugins: [react(), tailwindcss(), seoHtmlPlugin(siteUrl)],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  };
});
