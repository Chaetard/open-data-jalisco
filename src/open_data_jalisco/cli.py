# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .shared.config import get_settings
from .shared.logging import configure_logging

app = typer.Typer(
    name="odj",
    help="open-data-jalisco — CLI de ingesta, procesamiento y manifests.",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Operaciones de base de datos.")
sources_app = typer.Typer(help="Inspección de fuentes configuradas en YAML.")
sapumu_app = typer.Typer(help="Herramientas específicas para fuentes SAPUMU.")
discovered_app = typer.Typer(
    help="Inspección de candidatos descubiertos por `sapumu scan` (offline)."
)
app.add_typer(db_app, name="db")
app.add_typer(sources_app, name="sources")
app.add_typer(sapumu_app, name="sapumu")
app.add_typer(discovered_app, name="discovered")

console = Console()


@app.callback()
def _bootstrap() -> None:
    configure_logging(get_settings().log_level)


@app.command()
def version() -> None:
    """Imprime la versión de open-data-jalisco."""
    console.print(__version__)


@db_app.command("init")
def db_init() -> None:
    """Crea la extensión pgvector y todas las tablas. Idempotente."""
    from .adapters.persistence import init_db

    init_db()
    console.print("[green]DB inicializada.[/green]")


@sources_app.command("list")
def sources_list() -> None:
    """Lista las fuentes definidas en datasets/sources/*.yaml."""
    from .ingestion import iter_source_configs

    table = Table("slug", "municipality", "kind", "name")
    for cfg in iter_source_configs():
        table.add_row(cfg.slug, cfg.municipality, cfg.kind.value, cfg.name)
    console.print(table)


@app.command()
def ingest(
    source: Annotated[str, typer.Argument(help="slug de la fuente (ver `sources list`)")],
    limit: Annotated[
        int,
        typer.Option(min=1, max=1000, help="Máximo de documentos a fetchear por corrida."),
    ] = 5,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Sólo planea (sin red ni DB) y devuelve las URLs que se procesarían.",
        ),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(min=1, max=600, help="Timeout HTTP por request (segundos)."),
    ] = 30,
    user_agent: Annotated[
        str | None,
        typer.Option(help="Override del User-Agent enviado por el scraper."),
    ] = None,
) -> None:
    """Corre el scraper de una fuente y persiste documentos nuevos/versiones.

    Por defecto fetchea como máximo `--limit` documentos y deduplica por URL+SHA-256.
    Usa `--dry-run` para validar config y URLs sin tocar la red ni la DB.
    """
    from .adapters.persistence import (
        PostgresDocumentRepository,
        PostgresSourceRepository,
        get_session_factory,
    )
    from .adapters.storage.local_filesystem import LocalFilesystemRawStorage
    from .ingestion import IngestSourceUseCase, PlaceholderUrlError

    settings = get_settings()
    sf = get_session_factory()
    use_case = IngestSourceUseCase(
        source_repo=PostgresSourceRepository(sf),
        document_repo=PostgresDocumentRepository(sf),
        raw_storage=LocalFilesystemRawStorage(settings.raw_storage_path),
    )
    try:
        result = use_case.execute(
            source,
            limit=limit,
            dry_run=dry_run,
            timeout=timeout,
            user_agent=user_agent,
        )
    except PlaceholderUrlError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e
    console.print_json(data=result.__dict__)


@app.command()
def process(
    limit: Annotated[int, typer.Option(help="Documentos a procesar por corrida.")] = 50,
    retry_failed: Annotated[
        bool,
        typer.Option(
            "--retry-failed/--no-retry-failed",
            help="Incluye documentos en estado `failed` (e.g. para reintentar con un extractor nuevo).",
        ),
    ] = False,
) -> None:
    """Extrae texto, chunkea y embebe documentos en estado `pending`.

    Con ``--retry-failed`` también reintenta los que quedaron en ``failed``
    (útil cuando agregaste un extractor que antes no soportaba ese formato).
    """
    from .adapters.embeddings import build_embedding_provider
    from .adapters.extraction import build_default_registry
    from .adapters.persistence import (
        PostgresChunkRepository,
        PostgresDocumentRepository,
        get_session_factory,
    )
    from .adapters.storage.local_filesystem import LocalFilesystemRawStorage
    from .processing import ProcessDocumentsUseCase, build_chunker

    settings = get_settings()
    sf = get_session_factory()
    use_case = ProcessDocumentsUseCase(
        document_repo=PostgresDocumentRepository(sf),
        chunk_repo=PostgresChunkRepository(sf),
        raw_storage=LocalFilesystemRawStorage(settings.raw_storage_path),
        extractors=build_default_registry(),
        chunker=build_chunker(),
        embedder=build_embedding_provider(),
    )
    result = use_case.execute(limit=limit, retry_failed=retry_failed)
    console.print_json(data=result.__dict__)


@app.command()
def manifest(
    source: Annotated[str, typer.Argument(help="slug de la fuente.")],
    include_historical: Annotated[bool, typer.Option(help="Incluye versiones no-current.")] = True,
) -> None:
    """Genera un manifest JSON de auditoría en datasets/manifests/."""
    from .adapters.persistence import (
        PostgresDocumentRepository,
        PostgresSourceRepository,
        get_session_factory,
    )
    from .manifests import ManifestGenerator, write_manifest

    sf = get_session_factory()
    gen = ManifestGenerator(
        source_repo=PostgresSourceRepository(sf),
        document_repo=PostgresDocumentRepository(sf),
    )
    data = gen.generate(source, include_historical=include_historical)
    path = write_manifest(data)
    console.print(f"[green]Manifest escrito:[/green] {path}")
    console.print_json(data={"document_count": data["document_count"]})


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Consulta libre.")],
    limit: Annotated[int, typer.Option(help="Máximo de hits.")] = 5,
    municipality: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Búsqueda semántica sobre los chunks indexados (vía pgvector)."""
    from .adapters.embeddings import build_embedding_provider
    from .adapters.persistence import (
        PostgresChunkRepository,
        PostgresDocumentRepository,
        get_session_factory,
    )

    sf = get_session_factory()
    chunk_repo = PostgresChunkRepository(sf)
    doc_repo = PostgresDocumentRepository(sf)
    embedder = build_embedding_provider()
    [vec] = embedder.embed([query])
    results = chunk_repo.semantic_search(vec, limit=limit, municipality=municipality)

    payload = []
    for chunk, distance in results:
        doc = doc_repo.get_by_id(chunk.document_id)
        payload.append(
            {
                "score": round(max(0.0, 1.0 - float(distance)), 4),
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "section_title": chunk.section_title,
                "text": chunk.text[:240] + ("…" if len(chunk.text) > 240 else ""),
                "document": (
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "official_url": doc.official_url,
                        "sha256": doc.sha256,
                    }
                    if doc
                    else None
                ),
            }
        )
    console.print_json(data=payload)


# ---------------------------------------------------------------------
# sapumu — conservative discovery helpers (no DB, no PDF downloads)
# ---------------------------------------------------------------------


@sapumu_app.command("scan-content")
def sapumu_scan_content(
    source: Annotated[
        str,
        typer.Argument(
            help="slug de la fuente (lee scraper.content_page_template del YAML)."
        ),
    ],
    from_id: Annotated[
        int,
        typer.Option("--from-id", min=1, help="ID inicial inclusivo."),
    ],
    to_id: Annotated[
        int,
        typer.Option("--to-id", min=1, help="ID final inclusivo."),
    ],
    template: Annotated[
        str | None,
        typer.Option(
            help="Override del template (debe contener '{id}'). Default: scraper.content_page_template."
        ),
    ] = None,
    delay: Annotated[
        float,
        typer.Option(min=0.0, max=60.0, help="Segundos entre requests."),
    ] = 1.0,
    timeout: Annotated[int, typer.Option(min=1, max=600)] = 30,
    user_agent: Annotated[str | None, typer.Option()] = None,
    max_range: Annotated[
        int,
        typer.Option(min=1, max=10_000, help="Cap absoluto del rango (--to-id − --from-id + 1)."),
    ] = 500,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Sólo imprime las URLs que se buscarían, sin hacer requests.",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Exporta candidates+summary a archivo (extensión .json o .yaml).",
        ),
    ] = None,
) -> None:
    """Descubre documentos en páginas SAPUMU iterando ``contenido/{id}``.

    Conservador por diseño: respeta delay, tiene cap de rango, NUNCA toca la
    DB, NUNCA descarga PDFs — sólo fetchea HTML y extrae URLs del JSON
    embebido en ``<level-content :content="...">``.
    """
    import httpx

    from .discovery import (
        SapumuScanConfig,
        SapumuScanError,
        export_candidates,
        scan_content_pages,
    )
    from .ingestion import find_source_config

    if to_id < from_id:
        console.print("[red]error:[/red] --to-id must be >= --from-id")
        raise typer.Exit(code=2)

    range_size = to_id - from_id + 1
    if range_size > max_range:
        console.print(
            f"[red]error:[/red] requested range ({range_size}) exceeds --max-range "
            f"({max_range}). Increase --max-range explicitly if intentional."
        )
        raise typer.Exit(code=2)

    config = find_source_config(source)
    scraper_cfg = config.scraper or {}
    effective_template = template or scraper_cfg.get("content_page_template")
    if not effective_template:
        console.print(
            "[red]error:[/red] no template — pass --template or set "
            "scraper.content_page_template in the YAML."
        )
        raise typer.Exit(code=2)

    settings = get_settings()
    scan_cfg = SapumuScanConfig(
        template=effective_template,
        from_id=from_id,
        to_id=to_id,
        delay_seconds=delay,
        allowed_domains=list(scraper_cfg.get("allowed_domains") or []),
        document_extensions=list(scraper_cfg.get("document_extensions") or []),
    )
    try:
        scan_cfg.validate()
    except SapumuScanError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    ua = user_agent or settings.scraper_user_agent
    headers = {"User-Agent": ua}

    if dry_run:
        # Print the plan and exit without any network calls.
        payload = {
            "command": "sapumu scan-content",
            "source_slug": config.slug,
            "template": scan_cfg.template,
            "from_id": scan_cfg.from_id,
            "to_id": scan_cfg.to_id,
            "range_size": scan_cfg.range_size,
            "delay_seconds": scan_cfg.delay_seconds,
            "max_range": max_range,
            "dry_run": True,
            "urls_to_fetch": scan_cfg.urls(),
        }
        console.print_json(data=payload)
        return

    console.print(
        f"[yellow]scanning {scan_cfg.range_size} pages with {delay}s delay "
        f"(estimated minimum runtime: {delay * (scan_cfg.range_size - 1):.0f}s)[/yellow]"
    )

    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        def _fetch(url: str) -> str:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text

        result = scan_content_pages(scan_cfg, html_fetcher=_fetch)

    summary = {
        "source_slug": config.slug,
        "template": result.template,
        "from_id": result.from_id,
        "to_id": result.to_id,
        "pages_checked": result.pages_checked,
        "pages_with_documents": result.pages_with_documents,
        "pages_no_documents": result.pages_no_documents,
        "pages_failed": result.pages_failed,
        "documents_found": result.documents_found,
        "skipped_count": len(result.skipped),
        "first_candidates": [c.url for c in result.candidates[:5]],
    }
    console.print_json(data=summary)

    if output is not None:
        try:
            export_candidates(result, output)
        except SapumuScanError as e:
            console.print(f"[red]export error:[/red] {e}")
            raise typer.Exit(code=2) from e
        console.print(f"[green]wrote {len(result.candidates)} candidates to:[/green] {output}")


def _resolve_section_template(scraper_cfg: dict, section: str | None) -> str | None:
    """Look up ``section`` in scraper.section_templates with content_page_template fallback.

    Returns None if no template can be resolved.
    """
    section_templates = scraper_cfg.get("section_templates") or {}
    if section and section in section_templates:
        return str(section_templates[section])
    fallback = scraper_cfg.get("content_page_template")
    return str(fallback) if fallback else None


@sapumu_app.command("scan")
def sapumu_scan(
    source: Annotated[
        str,
        typer.Argument(help="slug de la fuente (ej. `tala`)."),
    ],
    section: Annotated[
        str,
        typer.Option(
            "--section",
            help="Sección a escanear (ej. `articulo_8`). Resuelve "
            "scraper.section_templates[section] con fallback a content_page_template.",
        ),
    ],
    from_id: Annotated[
        int,
        typer.Option("--from-id", min=1, help="ID inicial inclusivo."),
    ],
    to_id: Annotated[
        int,
        typer.Option("--to-id", min=1, help="ID final inclusivo."),
    ],
    limit_pages: Annotated[
        int | None,
        typer.Option(
            "--limit-pages",
            min=1,
            help="Cap opcional de páginas visitadas dentro del rango.",
        ),
    ] = None,
    delay_ms: Annotated[
        int,
        typer.Option(
            "--delay-ms",
            min=0,
            max=60_000,
            help="Delay entre requests en milisegundos.",
        ),
    ] = 1000,
    timeout: Annotated[int, typer.Option(min=1, max=600)] = 30,
    user_agent: Annotated[str | None, typer.Option()] = None,
    max_range: Annotated[
        int,
        typer.Option(min=1, max=10_000, help="Cap absoluto del rango."),
    ] = 500,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Sólo planea (sin red) y devuelve las URLs que se procesarían.",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Exporta candidates+summary a archivo (.json/.yaml).",
        ),
    ] = None,
) -> None:
    """Escáner SAPUMU experimental por sección (conservador, sin DB, sin descargas).

    Resuelve el template a usar mediante ``scraper.section_templates[section]``
    en el YAML de la fuente; si la sección no está mapeada, cae al
    ``content_page_template`` (fallback). Sólo descubre candidatos: no escribe
    en DB, no descarga documentos, no toca docs/MANIFEST.md.
    """
    import httpx

    from .discovery import (
        SapumuScanConfig,
        SapumuScanError,
        export_candidates,
        scan_content_pages,
    )
    from .ingestion import find_source_config

    if to_id < from_id:
        console.print("[red]error:[/red] --to-id must be >= --from-id")
        raise typer.Exit(code=2)

    range_size = to_id - from_id + 1
    if range_size > max_range:
        console.print(
            f"[red]error:[/red] requested range ({range_size}) exceeds --max-range "
            f"({max_range}). Increase --max-range explicitly if intentional."
        )
        raise typer.Exit(code=2)

    config = find_source_config(source)
    scraper_cfg = config.scraper or {}
    effective_template = _resolve_section_template(scraper_cfg, section)
    if not effective_template:
        console.print(
            f"[red]error:[/red] no template for section={section!r}. "
            "Add scraper.section_templates or scraper.content_page_template "
            "to the source YAML."
        )
        raise typer.Exit(code=2)

    settings = get_settings()
    delay_seconds = delay_ms / 1000.0
    scan_cfg = SapumuScanConfig(
        template=effective_template,
        from_id=from_id,
        to_id=to_id,
        delay_seconds=delay_seconds,
        allowed_domains=list(scraper_cfg.get("allowed_domains") or []),
        document_extensions=list(scraper_cfg.get("document_extensions") or []),
        section=section,
        limit_pages=limit_pages,
    )
    try:
        scan_cfg.validate()
    except SapumuScanError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    ua = user_agent or settings.scraper_user_agent

    if dry_run:
        payload = {
            "command": "sapumu scan",
            "source_slug": config.slug,
            "section": section,
            "template": scan_cfg.template,
            "from_id": scan_cfg.from_id,
            "to_id": scan_cfg.to_id,
            "limit_pages": scan_cfg.limit_pages,
            "effective_page_count": scan_cfg.effective_page_count,
            "delay_ms": delay_ms,
            "max_range": max_range,
            "dry_run": True,
            "urls_to_fetch": scan_cfg.urls(),
        }
        console.print_json(data=payload)
        return

    console.print(
        f"[yellow]scanning {scan_cfg.effective_page_count} pages with "
        f"{delay_ms}ms delay "
        f"(estimated minimum runtime: "
        f"{delay_seconds * (scan_cfg.effective_page_count - 1):.0f}s)[/yellow]"
    )

    headers = {"User-Agent": ua}
    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        def _fetch(url: str) -> str:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text

        result = scan_content_pages(scan_cfg, html_fetcher=_fetch)

    summary = {
        "source_slug": config.slug,
        "section": result.section,
        "template": result.template,
        "from_id": result.from_id,
        "to_id": result.to_id,
        "limit_pages": result.limit_pages,
        "pages_checked": result.pages_checked,
        "pages_found": result.pages_found,
        "pages_with_documents": result.pages_with_documents,
        "pages_no_documents": result.pages_no_documents,
        "pages_failed": result.pages_failed,
        "documents_found": result.documents_found,
        "skipped_pages": len(result.skipped),
        "sample_documents": result.sample_documents(5),
    }
    console.print_json(data=summary)

    if output is not None:
        try:
            export_candidates(result, output)
        except SapumuScanError as e:
            console.print(f"[red]export error:[/red] {e}")
            raise typer.Exit(code=2) from e
        console.print(
            f"[green]wrote {len(result.candidates)} candidates to:[/green] {output}"
        )


# ---------------------------------------------------------------------
# discovered — offline inspection of `sapumu scan` candidate exports
# ---------------------------------------------------------------------


@discovered_app.command("inspect")
def discovered_inspect(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Ruta al JSON exportado por `sapumu scan --output`.",
        ),
    ],
    year: Annotated[
        int | None,
        typer.Option("--year", help="Filtrar candidatos por año exacto."),
    ] = None,
    extension: Annotated[
        str | None,
        typer.Option(
            "--extension",
            help="Filtrar por extensión (ej. `pdf`). Case-insensitive.",
        ),
    ] = None,
    content_id: Annotated[
        int | None,
        typer.Option("--content-id", help="Filtrar por content_id de la página origen."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            min=0,
            max=1000,
            help="Cuántos documentos mostrar en la sección 'primeros'.",
        ),
    ] = 10,
) -> None:
    """Inspecciona un JSON de candidatos descubiertos. Sólo lectura.

    No descarga documentos, no escribe en DB, no toca docs/MANIFEST.md. Sirve para
    decidir qué subconjunto vale la pena ingresar antes de comprometer red.
    """
    from .discovery import (
        CandidateFilter,
        CandidatesInspectError,
        apply_filters,
        build_report,
        load_candidates,
    )

    try:
        candidates, metadata = load_candidates(path)
    except CandidatesInspectError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    filter_spec = CandidateFilter(
        year=year,
        extension=extension,
        content_id=content_id,
        limit=limit,
    )
    filtered = apply_filters(candidates, filter_spec)
    report = build_report(filtered, limit_first=limit)

    _render_inspection(path, metadata, filter_spec, len(candidates), report)


def _render_inspection(
    path: Path,
    metadata: dict,
    filter_spec: "object",  # CandidateFilter
    raw_total: int,
    report: "object",  # InspectionReport
) -> None:
    """Render an InspectionReport to the console via rich tables."""
    from .discovery import CandidateFilter, ContentBreakdown, InspectionReport

    assert isinstance(filter_spec, CandidateFilter)
    assert isinstance(report, InspectionReport)

    console.rule(f"[bold]discovered inspect[/bold] — {path}")

    header_lines = [
        f"file:           {path}",
        f"section:        {metadata.get('section')}",
        f"template:       {metadata.get('template')}",
        f"raw candidates: {raw_total}",
        f"after filters:  {report.total}",
    ]
    active_filters = []
    if filter_spec.year is not None:
        active_filters.append(f"year={filter_spec.year}")
    if filter_spec.extension is not None:
        active_filters.append(f"extension={filter_spec.extension}")
    if filter_spec.content_id is not None:
        active_filters.append(f"content_id={filter_spec.content_id}")
    header_lines.append(
        "filters:        " + (", ".join(active_filters) if active_filters else "(none)")
    )
    console.print("\n".join(header_lines))

    if report.total == 0:
        console.print(
            "\n[yellow]no candidates after filters — nothing more to show.[/yellow]"
        )
        return

    size_table = Table(title="Tamaño total estimado", show_header=False)
    size_table.add_row("total_size_bytes", f"{report.total_size_bytes:,}")
    size_table.add_row("total_size_mb", f"{report.total_size_mb:.2f}")
    size_table.add_row(
        "candidates_with_known_size",
        f"{report.candidates_with_known_size}/{report.total}",
    )
    size_table.add_row("missing_title", str(report.missing_title_count))
    size_table.add_row("missing_date_at", str(report.missing_date_at_count))
    size_table.add_row("duplicate_urls", str(len(report.duplicate_urls)))
    console.print(size_table)

    ext_table = Table("extension", "count", title="Por extensión")
    for ext, count in report.by_extension.items():
        ext_table.add_row(ext, str(count))
    console.print(ext_table)

    year_table = Table("year", "count", title="Por año")
    for yr, count in report.by_year.items():
        year_table.add_row(yr, str(count))
    console.print(year_table)

    content_table = Table(
        "content_id", "content_title", "count", title="Por content (todos)"
    )
    for cb in report.by_content:
        content_table.add_row(
            str(cb.content_id) if cb.content_id is not None else "",
            (cb.content_title or "")[:80],
            str(cb.count),
        )
    console.print(content_table)

    top_titles_table = Table(
        "content_title", "count", title="Top 20 content_title con más documentos"
    )
    for title, count in report.top_content_titles:
        top_titles_table.add_row(title[:80], str(count))
    console.print(top_titles_table)

    if report.duplicate_urls:
        dup_table = Table("url", "count", title="Posibles duplicados por URL")
        for url, count in report.duplicate_urls[:20]:
            dup_table.add_row(url, str(count))
        console.print(dup_table)

    first_table = Table(
        "url",
        "title",
        "ext",
        "year",
        "month",
        "size",
        title=f"Primeros {len(report.first_documents)} documentos",
    )
    for doc in report.first_documents:
        first_table.add_row(
            str(doc.get("url", "")),
            str(doc.get("title") or "")[:60],
            str(doc.get("extension") or ""),
            str(doc.get("year") or ""),
            str(doc.get("month") or ""),
            f"{doc.get('size'):,}" if isinstance(doc.get("size"), int) else "",
        )
    console.print(first_table)


@discovered_app.command("ingest")
def discovered_ingest(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="JSON exportado por `sapumu scan --output`.",
        ),
    ],
    source: Annotated[
        str,
        typer.Option(
            "--source",
            help="slug de la fuente (lee allowed_domains/document_extensions del YAML).",
        ),
    ],
    year: Annotated[int | None, typer.Option("--year")] = None,
    extension: Annotated[
        str | None,
        typer.Option("--extension", help="Filtra por extensión (ej. `pdf`)."),
    ] = None,
    content_id: Annotated[int | None, typer.Option("--content-id")] = None,
    content_title: Annotated[
        str | None,
        typer.Option(
            "--content-title",
            help="Filtro opcional por substring (case-insensitive) del content_title.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=1000, help="Tope de documentos a ingestar."),
    ] = 10,
    allow_sensitive_content: Annotated[
        bool,
        typer.Option(
            "--allow-sensitive-content/--no-allow-sensitive-content",
            help=(
                "Opt-in para content_ids sensibles "
                "(ej. 92 = declaraciones patrimoniales). Por defecto se bloquean."
            ),
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Sólo lista las URLs que se descargarían. No toca red ni DB.",
        ),
    ] = False,
    timeout: Annotated[int, typer.Option(min=1, max=600)] = 30,
    user_agent: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Ingesta controlada desde un JSON de candidatos descubiertos.

    Filtra el JSON, construye plan entries con metadata SAPUMU completa, y los
    pasa al pipeline existente (mismo hashing, mismo versionado, misma
    deduplicación por URL+sha256 que `ingest`). Por defecto bloquea content_ids
    sensibles (ej. 92 → declaraciones patrimoniales); usa
    ``--allow-sensitive-content`` para sobreescribir explícitamente.

    No descarga en dry-run. No escribe docs/MANIFEST.md. No genera contenido nuevo.
    """
    from .discovery import (
        CandidateIngestError,
        CandidateIngestFilter,
        CandidatesInspectError,
        load_candidates,
        select_entries,
    )
    from .ingestion import find_source_config

    try:
        candidates, metadata = load_candidates(path)
    except CandidatesInspectError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    config = find_source_config(source)
    scraper_cfg = config.scraper or {}

    filter_spec = CandidateIngestFilter(
        year=year,
        extension=extension,
        content_id=content_id,
        content_title=content_title,
        limit=limit,
        allow_sensitive_content=allow_sensitive_content,
    )

    try:
        entries, skipped = select_entries(
            candidates,
            filter_spec=filter_spec,
            allowed_domains=list(scraper_cfg.get("allowed_domains") or []),
            document_extensions=list(scraper_cfg.get("document_extensions") or []),
        )
    except CandidateIngestError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    blocked_sensitive = [
        s for s in skipped if s["reason"].startswith("sensitive_content_id_blocked")
    ]
    if blocked_sensitive and not allow_sensitive_content:
        console.print(
            f"[yellow]blocked {len(blocked_sensitive)} candidates with sensitive "
            "content_ids (pass --allow-sensitive-content to override).[/yellow]"
        )

    if not entries:
        console.print(
            "[yellow]no candidates passed the filters — nothing to ingest.[/yellow]"
        )
        console.print_json(
            data={
                "source_slug": source,
                "candidates_file": str(path),
                "filters": {
                    "year": year,
                    "extension": extension,
                    "content_id": content_id,
                    "content_title": content_title,
                    "limit": limit,
                    "allow_sensitive_content": allow_sensitive_content,
                },
                "planned_urls": [],
                "skipped_count": len(skipped),
                "skipped_samples": skipped[:5],
            }
        )
        return

    if dry_run:
        console.print_json(
            data={
                "command": "discovered ingest",
                "source_slug": source,
                "candidates_file": str(path),
                "section": metadata.get("section"),
                "dry_run": True,
                "filters": {
                    "year": year,
                    "extension": extension,
                    "content_id": content_id,
                    "content_title": content_title,
                    "limit": limit,
                    "allow_sensitive_content": allow_sensitive_content,
                },
                "planned_urls": [e.url for e in entries],
                "planned_count": len(entries),
                "skipped_count": len(skipped),
                "skipped_samples": skipped[:10],
                "first_metadata": entries[0].metadata if entries else None,
            }
        )
        return

    # Real run: only now do we wire up DB + storage. Keeps dry-run free of
    # any persistence-tier dependency (no DATABASE_URL needed to dry-run).
    from .adapters.persistence import (
        PostgresDocumentRepository,
        PostgresSourceRepository,
        get_session_factory,
    )
    from .adapters.storage.local_filesystem import LocalFilesystemRawStorage
    from .ingestion import IngestSourceUseCase, PlaceholderUrlError

    settings = get_settings()
    sf = get_session_factory()
    use_case = IngestSourceUseCase(
        source_repo=PostgresSourceRepository(sf),
        document_repo=PostgresDocumentRepository(sf),
        raw_storage=LocalFilesystemRawStorage(settings.raw_storage_path),
    )
    try:
        result = use_case.execute_from_entries(
            source,
            entries,
            dry_run=False,
            timeout=timeout,
            user_agent=user_agent,
        )
    except PlaceholderUrlError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=2) from e

    payload = {
        "source_slug": result.source_slug,
        "candidates_file": str(path),
        "documents_seen": result.documents_seen,
        "documents_inserted": result.documents_inserted,
        "documents_versioned": result.documents_versioned,
        "documents_unchanged": result.documents_unchanged,
        "documents_failed": result.documents_failed,
        "skipped_count": len(skipped),
        "errors": result.errors,
    }
    console.print_json(data=payload)


if __name__ == "__main__":
    app()
