"""Tests for techdraw_pdf.py — PDF merging, BOM table, and instructions generation."""

import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from techdraw_pdf import (
    _build_bom_table,
    _build_instructions_flowables,
    _generate_extra_pages_pdf,
    _md_inline_to_rl,
    generate_pdf,
)


class TestMdInlineToRl:
    def test_bold(self):
        assert _md_inline_to_rl("**hello**") == "<b>hello</b>"

    def test_italic(self):
        assert _md_inline_to_rl("*world*") == "<i>world</i>"

    def test_inline_code(self):
        assert _md_inline_to_rl("`code`") == '<font face="Courier">code</font>'

    def test_mixed(self):
        result = _md_inline_to_rl("**bold** and *italic*")
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result


class TestBuildBomTable:
    def test_returns_empty_for_no_file(self):
        assert _build_bom_table(None) == []
        assert _build_bom_table("/nonexistent/file.csv") == []

    def test_builds_table_from_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Index", "Name", "Quantity"])
            writer.writerow(["1", "Sphere", "1"])
            writer.writerow(["2", "Cube", "2"])
            f.flush()
            path = f.name

        try:
            flowables = _build_bom_table(path)
            assert len(flowables) >= 2  # Heading + Spacer + Table
        finally:
            os.unlink(path)


class TestBuildInstructionsFlowables:
    def test_returns_empty_for_no_file(self):
        assert _build_instructions_flowables(None) == []

    def test_parses_markdown_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Assembly Instructions\n\n")
            f.write("## Step 1\n\n")
            f.write("- Attach part A to part B\n")
            f.write("- Tighten with **M5 bolts**\n")
            f.flush()
            path = f.name

        try:
            flowables = _build_instructions_flowables(path)
            assert len(flowables) >= 4  # Title + Spacer + headings + bullets
        finally:
            os.unlink(path)


class TestGenerateExtraPagesPdf:
    def test_returns_none_with_no_content(self):
        result = _generate_extra_pages_pdf()
        assert result is None

    def test_generates_pdf_bytes_with_bom(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Part", "Qty"])
            writer.writerow(["Widget", "3"])
            f.flush()
            path = f.name

        try:
            result = _generate_extra_pages_pdf(bom_csv_path=path)
            assert result is not None
            assert len(result) > 100  # Valid PDF bytes
        finally:
            os.unlink(path)

    def test_generates_pdf_bytes_with_instructions(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Build Guide\n\nAssemble carefully.\n")
            f.flush()
            path = f.name

        try:
            result = _generate_extra_pages_pdf(instructions_path=path)
            assert result is not None
            assert len(result) > 100
        finally:
            os.unlink(path)


class TestGeneratePdf:
    """Test the main generate_pdf function (PDF merger)."""

    def _create_minimal_pdf(self, path):
        """Create a minimal valid PDF file for testing."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate

        doc = SimpleDocTemplate(path, pagesize=A4)
        styles = getSampleStyleSheet()
        doc.build([Paragraph("Test page", styles["Normal"])])

    def test_generates_pdf_from_page_pdfs(self):
        with tempfile.TemporaryDirectory() as td:
            # Create a fake TechDraw page PDF
            page_pdf = os.path.join(td, "page1.pdf")
            self._create_minimal_pdf(page_pdf)

            output = os.path.join(td, "output.pdf")
            result = generate_pdf([page_pdf], output)
            assert result is True
            assert os.path.exists(output)
            assert os.path.getsize(output) > 100

    def test_generates_pdf_with_bom_only(self):
        """Can generate a PDF with just BOM table on cover page (no TechDraw pages)."""
        with tempfile.TemporaryDirectory() as td:
            bom_path = os.path.join(td, "bom.csv")
            with open(bom_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Index", "Name", "Quantity"])
                writer.writerow(["1", "Sphere", "1"])
                writer.writerow(["2", "Cube", "2"])

            pdf_path = os.path.join(td, "output.pdf")
            metadata = {"title": "Test Project", "Author": "Tester", "Version": "1.0"}
            result = generate_pdf([], pdf_path, bom_csv_path=bom_path, metadata=metadata)
            assert result is True
            assert os.path.exists(pdf_path)
            assert os.path.getsize(pdf_path) > 100

    def test_generates_pdf_with_instructions_only(self):
        """Can generate a PDF with just instructions (no TechDraw pages)."""
        with tempfile.TemporaryDirectory() as td:
            instr_path = os.path.join(td, "INSTRUCTIONS.md")
            with open(instr_path, "w") as f:
                f.write("# Assembly Guide\n\n## Step 1\n\nAttach parts.\n")

            pdf_path = os.path.join(td, "output.pdf")
            result = generate_pdf([], pdf_path, instructions_path=instr_path)
            assert result is True
            assert os.path.exists(pdf_path)

    def test_generates_multi_page_pdf(self):
        """Can generate PDF with cover (BOM) + TechDraw page + instructions."""
        with tempfile.TemporaryDirectory() as td:
            # Create a fake TechDraw page PDF
            page_pdf = os.path.join(td, "page1.pdf")
            self._create_minimal_pdf(page_pdf)

            bom_path = os.path.join(td, "bom.csv")
            with open(bom_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Part", "Qty"])
                writer.writerow(["Widget", "3"])

            instr_path = os.path.join(td, "INSTRUCTIONS.md")
            with open(instr_path, "w") as f:
                f.write("# Build Guide\n\nAssemble carefully.\n")

            pdf_path = os.path.join(td, "output.pdf")
            metadata = {"title": "Multi Page Test", "Version": "2.0"}
            result = generate_pdf(
                [page_pdf],
                pdf_path,
                bom_csv_path=bom_path,
                instructions_path=instr_path,
                metadata=metadata,
            )
            assert result is True
            assert os.path.exists(pdf_path)
            assert os.path.getsize(pdf_path) > 500

    def test_returns_false_with_no_content(self):
        """Returns False when there's nothing to put in the PDF."""
        with tempfile.TemporaryDirectory() as td:
            pdf_path = os.path.join(td, "output.pdf")
            result = generate_pdf([], pdf_path)
            assert result is False

    def test_skips_missing_page_pdfs(self):
        """Missing page PDFs are skipped with a warning, not a crash."""
        with tempfile.TemporaryDirectory() as td:
            bom_path = os.path.join(td, "bom.csv")
            with open(bom_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Part", "Qty"])
                writer.writerow(["Widget", "1"])

            pdf_path = os.path.join(td, "output.pdf")
            metadata = {"title": "Skip Test"}
            result = generate_pdf(
                ["/nonexistent/page.pdf"],
                pdf_path,
                bom_csv_path=bom_path,
                metadata=metadata,
            )
            assert result is True  # Cover page with BOM still produces output

    def test_multiple_page_pdfs_merged(self):
        """Multiple TechDraw page PDFs are merged in order."""
        from pypdf import PdfReader

        with tempfile.TemporaryDirectory() as td:
            page1 = os.path.join(td, "page1.pdf")
            page2 = os.path.join(td, "page2.pdf")
            self._create_minimal_pdf(page1)
            self._create_minimal_pdf(page2)

            output = os.path.join(td, "output.pdf")
            result = generate_pdf([page1, page2], output)
            assert result is True

            reader = PdfReader(output)
            assert len(reader.pages) == 2


class TestPdfContent:
    """Tests that verify actual content (text) in generated PDFs."""

    def _get_pdf_text(self, pdf_path):
        """Extract all text from a PDF file."""
        from pypdf import PdfReader

        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text

    def test_bom_content_in_pdf(self):
        """BOM data should appear in the generated PDF."""
        with tempfile.TemporaryDirectory() as td:
            # Create BOM CSV with specific test data
            bom_path = os.path.join(td, "bom.csv")
            with open(bom_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Index", "Name", "Quantity"])
                writer.writerow(["1", "Sphere", "1"])
                writer.writerow(["2", "Cube", "2"])

            pdf_path = os.path.join(td, "output.pdf")
            result = generate_pdf([], pdf_path, bom_csv_path=bom_path, metadata={})
            assert result is True

            text = self._get_pdf_text(pdf_path)

            # Verify BOM section and data are in the PDF
            assert "Bill of Materials" in text
            assert "Index" in text
            assert "Name" in text
            assert "Quantity" in text
            assert "Sphere" in text
            assert "Cube" in text

    def test_metadata_content_in_pdf(self):
        """Metadata should appear in the generated PDF cover page."""
        with tempfile.TemporaryDirectory() as td:
            bom_path = os.path.join(td, "bom.csv")
            with open(bom_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Part", "Qty"])

            pdf_path = os.path.join(td, "output.pdf")
            metadata = {
                "title": "My Project",
                "Author": "John Doe",
                "Version": "1.0",
                "License": "CC-BY-SA-4.0",
                "Project": "Test Project",
                "Description": "A test description",
            }
            result = generate_pdf([], pdf_path, bom_csv_path=bom_path, metadata=metadata)
            assert result is True

            text = self._get_pdf_text(pdf_path)

            # Verify metadata is in the PDF
            assert "My Project" in text
            assert "John Doe" in text
            assert "1.0" in text
            assert "CC-BY-SA-4.0" in text
            assert "Test Project" in text
            assert "A test description" in text

    def test_bom_and_metadata_together_in_pdf(self):
        """Both BOM and metadata should appear when provided together."""
        with tempfile.TemporaryDirectory() as td:
            bom_path = os.path.join(td, "bom.csv")
            with open(bom_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Item", "Count"])
                writer.writerow(["Part1", "5"])

            pdf_path = os.path.join(td, "output.pdf")
            metadata = {"title": "Combined Test", "Author": "Tester", "Version": "2.0"}
            result = generate_pdf([], pdf_path, bom_csv_path=bom_path, metadata=metadata)
            assert result is True

            text = self._get_pdf_text(pdf_path)

            # Verify both BOM and metadata
            assert "Bill of Materials" in text
            assert "Part1" in text
            assert "Combined Test" in text
            assert "Tester" in text
            assert "2.0" in text
