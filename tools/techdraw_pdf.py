#!/usr/bin/env python3
"""
TechDraw PDF merger — runs in venv (outside FreeCAD).

Merges individual TechDraw page PDFs (exported by techdraw_export.py via
TechDrawGui.exportPageAsPdf) with optional BOM table and instructions pages
into a single multi-page PDF.

Uses pypdf for PDF merging and reportlab for generating BOM/instructions pages.
"""

import csv
import io
import json
import logging
import os
import re
import sys
from xml.sax.saxutils import escape as xml_escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)


# ─── Cover Page ────────────────────────────────────────────────────


def _build_cover_page(metadata, toc_entries, bom_csv_path=None):
    """
    Build a compact cover page with document metadata, TOC, and inline BOM.

    Everything fits on a single page: title, metadata, TOC, then BOM table.

    Args:
        metadata: Dict with keys like title, source, date, Author,
                  Version, GitCommit, GitBranch, GitTags, etc.
        toc_entries: List of (page_number, label) tuples for TOC.
        bom_csv_path: Optional path to BOM CSV — rendered inline on the cover page.

    Returns:
        Tuple of (flowables, resolved_date) where flowables is a list of
        reportlab flowables and resolved_date is the date string used.
    """
    from datetime import datetime

    styles = getSampleStyleSheet()
    flowables = []

    # ── Title
    title = metadata.get("title") or metadata.get("name", "Technical Drawing Package")
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        spaceAfter=2 * mm,
    )
    flowables.append(Paragraph(title, title_style))

    # ── Subtitle line: source + version
    parts = []
    source = metadata.get("source", "")
    if source:
        parts.append(source)
    version = metadata.get("Version") or metadata.get("version", "")
    if version:
        parts.append(f"v{version}")
    if parts:
        subtitle_style = ParagraphStyle(
            "CoverSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            spaceAfter=3 * mm,
        )
        flowables.append(Paragraph(" — ".join(parts), subtitle_style))

    flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    flowables.append(Spacer(1, 3 * mm))

    # ── Metadata table (compact key-value pairs)
    meta_rows = []

    date_str = metadata.get("date") or datetime.now().strftime("%Y-%m-%d %H:%M")
    # Return resolved date via a copy — do not mutate the caller's dict
    resolved_date = date_str
    meta_rows.append(("Created", date_str))

    author = metadata.get("Author") or metadata.get("author", "")
    if author:
        meta_rows.append(("Author", author))

    if version:
        meta_rows.append(("Version", version))

    # Git info — single compact line: hash (branch, tag)
    git_parts = []
    if metadata.get("GitCommit"):
        git_parts.append(metadata["GitCommit"])
    if metadata.get("GitBranch"):
        git_parts.append(metadata["GitBranch"])
    if metadata.get("GitTags"):
        tags = metadata["GitTags"]
        if isinstance(tags, list):
            tags = ", ".join(tags)
        if tags:
            git_parts.append(tags)
    if git_parts:
        git_str = git_parts[0]
        if len(git_parts) > 1:
            git_str += f" ({', '.join(git_parts[1:])})"
        meta_rows.append(("Revision", git_str))

    # Any extra metadata keys not already handled
    shown_keys = {
        "title",
        "name",
        "source",
        "date",
        "author",
        "Author",
        "version",
        "Version",
        "GitBranch",
        "GitCommit",
        "GitCommitFull",
        "GitTags",
        "GitRemote",
        "_resolved_date",
    }
    for key, val in metadata.items():
        if key not in shown_keys and val:
            meta_rows.append((key, str(val)))

    if meta_rows:
        label_style = ParagraphStyle(
            "MetaLabel", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#666666")
        )
        value_style = ParagraphStyle("MetaValue", parent=styles["Normal"], fontSize=8)

        table_data = [[Paragraph(label, label_style), Paragraph(str(value), value_style)] for label, value in meta_rows]
        meta_table = Table(table_data, colWidths=[22 * mm, 148 * mm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("LEFTPADDING", (0, 0), (0, -1), 0),
                ]
            )
        )
        flowables.append(meta_table)
        flowables.append(Spacer(1, 4 * mm))

    # ── Table of Contents
    if toc_entries:
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
        flowables.append(Spacer(1, 2 * mm))

        section_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading3"],
            fontSize=10,
            spaceAfter=2 * mm,
            spaceBefore=0,
        )
        flowables.append(Paragraph("Contents", section_style))

        toc_style = ParagraphStyle("TOCEntry", parent=styles["Normal"], fontSize=8, leftIndent=3 * mm, spaceAfter=0)
        page_num_style = ParagraphStyle("TOCPage", parent=styles["Normal"], fontSize=8, alignment=2)  # right-aligned

        toc_data = [
            [Paragraph(label, toc_style), Paragraph(str(page_num), page_num_style)] for page_num, label in toc_entries
        ]
        toc_table = Table(toc_data, colWidths=[150 * mm, 20 * mm])
        toc_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                    ("LEFTPADDING", (0, 0), (0, -1), 0),
                ]
            )
        )
        flowables.append(toc_table)
        flowables.append(Spacer(1, 4 * mm))

    # ── Inline BOM table (compact, on same page)
    bom_flowables = _build_bom_table_compact(bom_csv_path)
    if bom_flowables:
        flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
        flowables.append(Spacer(1, 2 * mm))
        flowables.extend(bom_flowables)

    return flowables, resolved_date


def _build_bom_table_compact(bom_csv_path):
    """
    Build a compact BOM table suitable for embedding on the cover page.

    Uses smaller fonts and tighter spacing than the standalone BOM page.

    Returns:
        List of reportlab flowables (heading + table), or empty list.
    """
    if not bom_csv_path or not os.path.exists(bom_csv_path):
        return []

    styles = getSampleStyleSheet()

    flowables = []
    section_style = ParagraphStyle(
        "BOMSectionHeading",
        parent=styles["Heading3"],
        fontSize=10,
        spaceAfter=2 * mm,
        spaceBefore=0,
    )
    flowables.append(Paragraph("Bill of Materials", section_style))

    with open(bom_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return flowables

    header = rows[0]
    data_rows = rows[1:]

    cell_style = ParagraphStyle("BOMCellCompact", parent=styles["Normal"], fontSize=7, leading=9)
    header_style = ParagraphStyle(
        "BOMHeaderCompact", parent=styles["Normal"], fontSize=7, leading=9, fontName="Helvetica-Bold"
    )

    table_data = [[Paragraph(xml_escape(c), header_style) for c in header]]
    for row in data_rows:
        table_data.append([Paragraph(xml_escape(c), cell_style) for c in row])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    flowables.append(table)
    return flowables


# ─── BOM Table ─────────────────────────────────────────────────────


def _build_bom_table(bom_csv_path):
    """
    Build a reportlab Table from a CSV file.

    Returns:
        List of reportlab flowables (heading + table)
    """
    if not bom_csv_path or not os.path.exists(bom_csv_path):
        return []

    styles = getSampleStyleSheet()

    flowables = []
    flowables.append(Paragraph("Bill of Materials", styles["Heading1"]))
    flowables.append(Spacer(1, 6 * mm))

    with open(bom_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        flowables.append(Paragraph("No BOM data available.", styles["Normal"]))
        return flowables

    # Style header row differently
    header = rows[0]
    data_rows = rows[1:]

    # Wrap cell text in Paragraphs for word wrapping
    cell_style = ParagraphStyle("BOMCell", parent=styles["Normal"], fontSize=9, leading=11)
    header_style = ParagraphStyle(
        "BOMHeader", parent=styles["Normal"], fontSize=9, leading=11, fontName="Helvetica-Bold"
    )

    table_data = [[Paragraph(xml_escape(c), header_style) for c in header]]
    for row in data_rows:
        table_data.append([Paragraph(xml_escape(c), cell_style) for c in row])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    flowables.append(table)
    return flowables


# ─── Instructions ──────────────────────────────────────────────────


def _build_instructions_flowables(instructions_path):
    """
    Build reportlab flowables from a markdown/text instructions file.

    Supports basic markdown: headings (#), bold (**), italic (*), bullet lists (-),
    numbered lists, and paragraphs.

    Returns:
        List of reportlab flowables
    """
    if not instructions_path or not os.path.exists(instructions_path):
        return []

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("InstructionsBody", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6)
    h1_style = ParagraphStyle("InstrH1", parent=styles["Heading1"], spaceAfter=8)
    h2_style = ParagraphStyle("InstrH2", parent=styles["Heading2"], spaceAfter=6)
    h3_style = ParagraphStyle("InstrH3", parent=styles["Heading3"], spaceAfter=4)
    bullet_style = ParagraphStyle("InstrBullet", parent=body_style, leftIndent=20, bulletIndent=10)

    with open(instructions_path, encoding="utf-8") as f:
        text = f.read()

    flowables = []
    flowables.append(Paragraph("Instructions", styles["Title"]))
    flowables.append(Spacer(1, 6 * mm))

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            flowables.append(Spacer(1, 3 * mm))
            continue

        # Convert basic markdown inline formatting for reportlab
        formatted = _md_inline_to_rl(stripped)

        # Headings
        if stripped.startswith("### "):
            flowables.append(Paragraph(_md_inline_to_rl(stripped[4:]), h3_style))
        elif stripped.startswith("## "):
            flowables.append(Paragraph(_md_inline_to_rl(stripped[3:]), h2_style))
        elif stripped.startswith("# "):
            flowables.append(Paragraph(_md_inline_to_rl(stripped[2:]), h1_style))
        # Bullet lists
        elif stripped.startswith("- ") or stripped.startswith("* "):
            flowables.append(Paragraph(f"• {_md_inline_to_rl(stripped[2:])}", bullet_style))
        # Numbered lists
        elif re.match(r"^\d+\.\s", stripped):
            flowables.append(Paragraph(formatted, bullet_style))
        else:
            flowables.append(Paragraph(formatted, body_style))

    return flowables


def _md_inline_to_rl(text):
    """Convert basic markdown inline formatting to reportlab XML tags.

    Escapes XML-special characters (&, <, >) first to prevent reportlab
    ParseError or unintended markup injection, then applies markdown
    replacements on the escaped text.
    """
    # Escape XML-special chars before any markup conversion
    text = xml_escape(text)
    # Bold: **text** → <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Italic: *text* → <i>text</i>
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Inline code: `text` → <font face="Courier">text</font>
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    return text


# ─── PDF Generation Helpers ────────────────────────────────────────


def _generate_extra_pages_pdf(bom_csv_path=None, instructions_path=None):
    """
    Generate a PDF containing BOM table and/or instructions pages.

    Returns:
        bytes of the PDF, or None if no content.
    """
    flowables = []

    bom_flowables = _build_bom_table(bom_csv_path)
    if bom_flowables:
        flowables.extend(bom_flowables)

    instr_flowables = _build_instructions_flowables(instructions_path)
    if instr_flowables:
        if flowables:
            flowables.append(PageBreak())
        flowables.extend(instr_flowables)

    if not flowables:
        return None

    buf = io.BytesIO()
    margin = 15 * mm
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )
    doc.build(flowables)
    return buf.getvalue()


def _stamp_page_footers(writer, metadata=None, resolved_date=""):
    """
    Stamp a consistent footer on every page in the PdfWriter.

    Footer layout: left=title | center=Page X of Y | right=date + version
    Adapts to each page's actual dimensions (handles mixed landscape/portrait).
    """
    total = len(writer.pages)
    if total == 0:
        return

    title = ""
    right_text = ""
    if metadata:
        title = metadata.get("title") or metadata.get("name", "")
        date_str = resolved_date
        version = metadata.get("Version") or metadata.get("version", "")
        right_parts = []
        if date_str:
            right_parts.append(date_str)
        if version:
            right_parts.append(f"v{version}")
        right_text = " | ".join(right_parts)

    for i, page in enumerate(writer.pages):
        page_num = i + 1

        media_box = page.mediabox
        page_width = float(media_box.width)
        page_height = float(media_box.height)

        margin = 10 * mm
        y_pos = 5 * mm

        buf = io.BytesIO()
        c = pdf_canvas.Canvas(buf, pagesize=(page_width, page_height))
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#888888"))

        # Left: title
        if title:
            c.drawString(margin, y_pos, title)

        # Center: page number
        c.drawCentredString(page_width / 2, y_pos, f"Page {page_num} of {total}")

        # Right: date + version
        if right_text:
            c.drawRightString(page_width - margin, y_pos, right_text)

        c.save()

        overlay_reader = PdfReader(io.BytesIO(buf.getvalue()))
        page.merge_page(overlay_reader.pages[0])


# ─── Main Entry Point ──────────────────────────────────────────────


def generate_pdf(page_pdfs, output_path, bom_csv_path=None, instructions_path=None, metadata=None):
    """
    Merge TechDraw page PDFs with cover page, BOM, and instructions into a cohesive report.

    Structure:
    1. Cover page (metadata + TOC + inline BOM table)
    2. TechDraw drawing pages
    3. Instructions (if provided)
    4. Consistent footer on every page: title | Page X of Y | date + version

    BOM is embedded on the cover page (not a separate page) for compact projects.

    Args:
        page_pdfs: List of file paths to individual TechDraw page PDFs
        output_path: Path for the output merged PDF file
        bom_csv_path: Optional path to BOM CSV (shown on cover page)
        instructions_path: Optional path to instructions markdown file
        metadata: Optional dict with document metadata (title, source, Author, Version, git info)

    Returns:
        True on success, False on failure
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        writer = PdfWriter()

        # Pre-scan page counts for TOC
        page_labels = []
        for pdf_path in page_pdfs:
            if not os.path.exists(pdf_path):
                continue
            reader = PdfReader(pdf_path)
            name = os.path.splitext(os.path.basename(pdf_path))[0]
            page_labels.append((name, len(reader.pages)))

        # Build TOC entries (cover = page 1, drawings start at page 2)
        toc_entries = []
        current_page = 2  # after cover
        for name, count in page_labels:
            toc_entries.append((current_page, f"Drawing — {name}"))
            current_page += count

        if instructions_path and os.path.exists(instructions_path):
            toc_entries.append((current_page, "Assembly Instructions"))

        # 1. Cover page (with inline BOM)
        # Generate cover when metadata is provided, or when BOM exists (use empty dict as default)
        resolved_date = ""
        effective_metadata = metadata if metadata else ({} if bom_csv_path else None)
        if effective_metadata is not None:
            cover_flowables, resolved_date = _build_cover_page(
                effective_metadata, toc_entries, bom_csv_path=bom_csv_path
            )
            if cover_flowables:
                buf = io.BytesIO()
                margin = 15 * mm
                doc = SimpleDocTemplate(
                    buf,
                    pagesize=A4,
                    leftMargin=margin,
                    rightMargin=margin,
                    topMargin=margin,
                    bottomMargin=15 * mm,
                )
                doc.build(cover_flowables)
                cover_reader = PdfReader(io.BytesIO(buf.getvalue()))
                for page in cover_reader.pages:
                    writer.add_page(page)
                logger.info("Added cover page")

        # 2. TechDraw drawing pages
        for pdf_path in page_pdfs:
            if not os.path.exists(pdf_path):
                logger.warning(f"Page PDF not found: {pdf_path}")
                continue
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                writer.add_page(page)
            logger.info(f"Added TechDraw page: {pdf_path}")

        # 3. Instructions pages (BOM is on cover, not here)
        if instructions_path:
            extra_pdf_bytes = _generate_extra_pages_pdf(instructions_path=instructions_path)
            if extra_pdf_bytes:
                extra_reader = PdfReader(io.BytesIO(extra_pdf_bytes))
                for page in extra_reader.pages:
                    writer.add_page(page)
                logger.info(f"Added {len(extra_reader.pages)} instructions page(s)")

        if len(writer.pages) == 0:
            logger.error("No content to generate PDF from")
            return False

        # 4. Stamp consistent footer on every page
        _stamp_page_footers(writer, metadata=metadata, resolved_date=resolved_date)

        with open(output_path, "wb") as f:
            writer.write(f)

        logger.info(f"PDF generated: {output_path} ({os.path.getsize(output_path)} bytes)")
        return True

    except Exception as e:
        logger.exception(f"Failed to generate PDF: {e}")
        return False


def create_from_json_config(config_json):
    """
    Create PDF from a JSON configuration (called via subprocess from fc_export.py).

    Expected JSON structure:
    {
        "page_pdfs": ["/path/to/Page.pdf", ...],
        "output_path": "path/to/output.pdf",
        "bom_csv_path": "path/to/bom.csv",              // optional
        "instructions_path": "path/to/INSTRUCTIONS.md",  // optional
        "metadata": { "title": "...", ... }              // optional
    }
    """
    config = json.loads(config_json) if isinstance(config_json, str) else config_json

    return generate_pdf(
        page_pdfs=config.get("page_pdfs", []),
        output_path=config["output_path"],
        bom_csv_path=config.get("bom_csv_path"),
        instructions_path=config.get("instructions_path"),
        metadata=config.get("metadata"),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print("Usage: techdraw_pdf.py <config.json>")
        print("  config.json contains page_pdfs, output_path, bom_csv_path, instructions_path")
        sys.exit(1)

    config_path = sys.argv[1]
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    success = create_from_json_config(config)
    sys.exit(0 if success else 1)
