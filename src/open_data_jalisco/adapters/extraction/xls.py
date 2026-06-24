# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Legacy XLS (BIFF / OLE2) text extractor backed by xlrd.

openpyxl reads only the OOXML ``.xlsx`` family; pre-2007 ``.xls`` files are the
OLE2 compound format, which xlrd reads. Output mirrors the XLSX extractor (one
``ExtractedPage`` per non-empty worksheet, rows joined by ``" | "``, same cell
formatting) so ``.xls`` and ``.xlsx`` documents are indistinguishable
downstream. Unreadable files yield an empty document (``needs_ocr=False``) so
the pipeline marks ``no_text`` rather than crashing the batch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ...ports.text_extractor import ExtractedDocument, ExtractedPage
from ...shared.logging import get_logger
from .xlsx import _MAX_CELLS_PER_SHEET, _format_cell

logger = get_logger(__name__)

# Match .xls by extension primarily: the OLE2 magic also covers legacy .doc, so
# we never claim generic 'application/CDFV2' by mime alone.
_XLS_MIME = {"application/vnd.ms-excel", "application/x-xls", "application/excel"}
_XLS_EXTENSIONS = {"xls"}


class XlsTextExtractor:
    def can_handle(self, mime_type: str, extension: str) -> bool:
        return (
            extension.lower().lstrip(".") in _XLS_EXTENSIONS
            or mime_type.lower() in _XLS_MIME
        )

    def extract(self, path: Path) -> ExtractedDocument:
        import xlrd

        try:
            book = xlrd.open_workbook(str(path), on_demand=True)
        except Exception as e:
            # Not a real OLE2/BIFF file, encrypted, or corrupt.
            logger.warning("xls.extract.open_error path=%s err=%r", path, e)
            return ExtractedDocument(
                full_text="",
                pages=[],
                needs_ocr=False,
                metadata={"error": f"open_error: {e!r}"},
            )

        pages: list[ExtractedPage] = []
        sheet_names: list[str] = []
        total_rows = 0
        truncated_sheets: list[str] = []
        try:
            for idx in range(book.nsheets):
                sheet = book.sheet_by_index(idx)
                sheet_names.append(sheet.name)
                rows_text, row_count, truncated = _sheet_text(sheet, book.datemode)
                total_rows += row_count
                if truncated:
                    truncated_sheets.append(sheet.name)
                if rows_text:
                    page_text = f"# {sheet.name}\n" + "\n".join(rows_text)
                    pages.append(ExtractedPage(page_number=idx + 1, text=page_text))
                book.unload_sheet(idx)  # release per-sheet memory (on_demand)
        finally:
            book.release_resources()

        full_text = "\n\n".join(p.text for p in pages if p.text)
        metadata: dict[str, Any] = {
            "sheet_names": sheet_names,
            "sheet_count": len(sheet_names),
            "non_empty_sheet_count": len(pages),
            "row_count": total_rows,
        }
        if truncated_sheets:
            metadata["truncated_sheets"] = truncated_sheets
        return ExtractedDocument(
            full_text=full_text, pages=pages, needs_ocr=False, metadata=metadata
        )


def _sheet_text(sheet, datemode: int) -> tuple[list[str], int, bool]:
    """Return (non-empty row strings, non-empty row count, truncated)."""
    rows_text: list[str] = []
    row_count = 0
    cells_seen = 0
    truncated = False
    for r in range(sheet.nrows):
        cells: list[str] = []
        for c in range(sheet.ncols):
            val = _xls_cell_value(sheet.cell(r, c), datemode)
            if val is None or (isinstance(val, str) and not val.strip()):
                continue
            cells.append(_format_cell(val))
        cells_seen += sheet.ncols
        if cells:
            rows_text.append(" | ".join(cells))
            row_count += 1
        if cells_seen >= _MAX_CELLS_PER_SHEET:
            truncated = True
            logger.warning(
                "xls.extract.sheet_truncated sheet=%s cells_seen=%d limit=%d",
                sheet.name, cells_seen, _MAX_CELLS_PER_SHEET,
            )
            break
    return rows_text, row_count, truncated


def _xls_cell_value(cell, datemode: int) -> Any:
    """xlrd cell → native python value (None for empty/error). Dates → datetime."""
    import xlrd

    t = cell.ctype
    if t in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR):
        return None
    if t == xlrd.XL_CELL_DATE:
        try:
            return xlrd.xldate.xldate_as_datetime(cell.value, datemode)
        except Exception:
            return cell.value
    if t == xlrd.XL_CELL_BOOLEAN:
        return bool(cell.value)
    return cell.value  # text (str) or number (float) — _format_cell handles both
