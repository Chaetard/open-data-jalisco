import { useMemo } from "react";
import { Link } from "react-router-dom";
import { marked } from "marked";
import { ArrowLeft } from "lucide-react";
import apiMarkdown from "./content/api.md?raw";

// Slug estilo GitHub: minúsculas, conserva acentos y guiones bajos, cada
// espacio → un guion (sin colapsar). Hace funcionar el índice interno del doc.
const slugify = (text: string) =>
  text
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_-]/gu, "")
    .replace(/\s/g, "-");

// marked no añade id a los headings; los inyectamos para que los anclajes del
// índice (#get-health, …) naveguen. Contenido propio del repo → innerHTML seguro.
const renderDoc = (markdown: string) => {
  const html = marked.parse(markdown, { gfm: true }) as string;
  return html.replace(/<(h[1-4])>([\s\S]*?)<\/\1>/g, (_match, tag: string, inner: string) => {
    const text = inner.replace(/<[^>]+>/g, "");
    return `<${tag} id="${slugify(text)}">${inner}</${tag}>`;
  });
};

export default function ApiDocs() {
  const html = useMemo(() => renderDoc(apiMarkdown), []);

  return (
    <div className="mx-auto max-w-3xl px-4 py-9 sm:px-6 lg:px-8">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1.5 text-sm font-semibold text-brand transition hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" /> Volver al inicio
      </Link>
      <article className="doc" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
