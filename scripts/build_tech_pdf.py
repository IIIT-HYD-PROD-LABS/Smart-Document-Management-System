"""Build TaxSync_Technical_Documentation.pdf from the markdown source.

Pipeline: markdown-it-py -> HTML with embedded professional CSS -> Chrome headless -> PDF.
Why Chrome headless: native CSS @page support (margins, page numbers), excellent table
rendering, no LaTeX/pandoc dependency.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "docs" / "reference" / "TaxSync_Technical_Documentation.md"
HTML_PATH = ROOT / "docs" / "exports" / "TaxSync_Technical_Documentation.html"
PDF_PATH = ROOT / "docs" / "exports" / "TaxSync_Technical_Documentation.pdf"

CSS = """
@page {
    size: A4;
    margin: 22mm 18mm 22mm 18mm;

    @top-right {
        content: "TaxSync Technical Documentation";
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 9pt;
        color: #6b7280;
    }
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 9pt;
        color: #6b7280;
    }
    @bottom-left {
        content: "v2.0.1";
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 9pt;
        color: #6b7280;
    }
}

@page :first {
    margin: 0;
    @top-right { content: none; }
    @bottom-center { content: none; }
    @bottom-left { content: none; }
}

* { box-sizing: border-box; }

html, body {
    margin: 0;
    padding: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #111827;
    -webkit-font-smoothing: antialiased;
}

/* Cover page */
.cover {
    page-break-after: always;
    height: 297mm;
    width: 210mm;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f172a 100%);
    color: #f8fafc;
    position: relative;
    overflow: hidden;
}
.cover::before {
    content: "";
    position: absolute;
    top: -150px;
    right: -150px;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.25), transparent 70%);
}
.cover::after {
    content: "";
    position: absolute;
    bottom: -100px;
    left: -100px;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.18), transparent 70%);
}
.cover-header {
    padding: 30mm 25mm 0 25mm;
    position: relative;
    z-index: 1;
}
.cover-brand {
    font-size: 14pt;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #94a3b8;
    margin-bottom: 8mm;
}
.cover-title {
    font-size: 44pt;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
    margin: 0 0 6mm 0;
    color: #f8fafc;
}
.cover-subtitle {
    font-size: 16pt;
    font-weight: 400;
    color: #cbd5e1;
    line-height: 1.4;
    max-width: 140mm;
}
.cover-meta {
    padding: 0 25mm 30mm 25mm;
    position: relative;
    z-index: 1;
}
.cover-divider {
    width: 80mm;
    height: 2px;
    background: linear-gradient(90deg, #6366f1, transparent);
    margin-bottom: 10mm;
}
.cover-meta-row {
    display: flex;
    gap: 20mm;
    margin-bottom: 6mm;
}
.cover-meta-item .label {
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #94a3b8;
    margin-bottom: 2mm;
}
.cover-meta-item .value {
    font-size: 11pt;
    color: #f1f5f9;
    font-weight: 500;
}
.cover-tagline {
    font-size: 9pt;
    color: #64748b;
    margin-top: 8mm;
    font-style: italic;
}

/* Document body */
.doc {
    padding: 0;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', system-ui, sans-serif;
    font-weight: 600;
    color: #0f172a;
    letter-spacing: -0.01em;
    line-height: 1.25;
}

h1 {
    font-size: 24pt;
    margin: 0 0 6mm 0;
    padding-bottom: 4mm;
    border-bottom: 2px solid #1e293b;
    page-break-before: always;
    page-break-after: avoid;
}
.doc > h1:first-of-type { page-break-before: avoid; }

h2 {
    font-size: 16pt;
    margin: 9mm 0 4mm 0;
    color: #1e293b;
    page-break-after: avoid;
}

h3 {
    font-size: 12.5pt;
    margin: 6mm 0 3mm 0;
    color: #334155;
    page-break-after: avoid;
}

h4 {
    font-size: 10.5pt;
    margin: 4mm 0 2mm 0;
    color: #475569;
    page-break-after: avoid;
}

p {
    margin: 0 0 3mm 0;
    text-align: justify;
}

strong { color: #0f172a; font-weight: 600; }
em { color: #334155; }

a { color: #4f46e5; text-decoration: none; }

/* Lists */
ul, ol {
    margin: 0 0 4mm 0;
    padding-left: 6mm;
}
ul li, ol li {
    margin-bottom: 1.5mm;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 4mm 0 5mm 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}
thead {
    background: #1e293b;
    color: #f1f5f9;
}
thead th {
    text-align: left;
    padding: 2.5mm 3mm;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.02em;
    border-bottom: 2px solid #0f172a;
}
tbody td {
    padding: 2mm 3mm;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
}
tbody tr:nth-child(even) { background: #f8fafc; }
tbody tr:hover { background: #f1f5f9; }
tbody td strong { color: #0f172a; }

/* Code */
code {
    font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
    font-size: 9pt;
    background: #f1f5f9;
    color: #0f172a;
    padding: 0.5mm 1.5mm;
    border-radius: 2px;
    border: 1px solid #e2e8f0;
}
pre {
    background: #0f172a;
    color: #e2e8f0;
    padding: 4mm;
    border-radius: 3px;
    overflow-x: auto;
    margin: 3mm 0 5mm 0;
    page-break-inside: avoid;
    font-size: 8.5pt;
    line-height: 1.5;
    white-space: pre;
}
pre code {
    background: transparent;
    border: none;
    color: inherit;
    padding: 0;
    font-size: inherit;
}

/* Blockquotes */
blockquote {
    border-left: 3px solid #6366f1;
    padding: 2mm 4mm;
    margin: 3mm 0;
    background: #f8fafc;
    color: #334155;
    font-style: italic;
}

/* Horizontal rules */
hr {
    border: 0;
    border-top: 1px solid #e2e8f0;
    margin: 8mm 0;
}

/* TOC styling - the markdown TOC is just a list */
.toc-section {
    page-break-after: always;
}
.toc-section ol, .toc-section ul {
    list-style: none;
    padding-left: 0;
}
.toc-section li {
    padding: 1.5mm 0;
    border-bottom: 1px dotted #cbd5e1;
    margin-bottom: 0;
    font-size: 11pt;
}
.toc-section li a {
    color: #1e293b;
    font-weight: 500;
}

/* Section anchors */
h1[id], h2[id], h3[id] {
    scroll-margin-top: 20mm;
}

/* Print-specific avoids */
table, pre, blockquote {
    page-break-inside: avoid;
}
"""

COVER_HTML = """
<section class="cover">
    <div class="cover-header">
        <div class="cover-brand">TaxSync</div>
        <h1 class="cover-title">Technical<br/>Documentation</h1>
        <p class="cover-subtitle">
            Smart Document Management and Compliance Platform
            for Indian Regulatory Practice
        </p>
    </div>
    <div class="cover-meta">
        <div class="cover-divider"></div>
        <div class="cover-meta-row">
            <div class="cover-meta-item">
                <div class="label">Product Version</div>
                <div class="value">v2.0.1</div>
            </div>
            <div class="cover-meta-item">
                <div class="label">Document Date</div>
                <div class="value">8 May 2026</div>
            </div>
            <div class="cover-meta-item">
                <div class="label">Status</div>
                <div class="value">Production-Ready</div>
            </div>
        </div>
        <div class="cover-meta-row">
            <div class="cover-meta-item">
                <div class="label">Production Features</div>
                <div class="value">64 features across 9 areas</div>
            </div>
            <div class="cover-meta-item">
                <div class="label">Test Coverage</div>
                <div class="value">389 automated tests</div>
            </div>
        </div>
        <p class="cover-tagline">
            This document describes the production-shipped capability of the TaxSync platform.
        </p>
    </div>
</section>
"""


def md_to_html_body(md_text: str) -> str:
    md = MarkdownIt("commonmark", {"html": False, "breaks": False, "linkify": False})
    md.enable("table")
    md.enable("strikethrough")
    body_html = md.render(md_text)
    return body_html


def build_html(body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>TaxSync — Technical Documentation</title>
    <style>{CSS}</style>
</head>
<body>
    {COVER_HTML}
    <article class="doc">{body_html}</article>
</body>
</html>"""


def find_chrome() -> str:
    for candidate in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("Chrome or Chromium not found on PATH")


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = find_chrome()
    file_url = f"file://{html_path.resolve()}"
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--virtual-time-budget=10000",
        f"--print-to-pdf={pdf_path.resolve()}",
        file_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"Chrome PDF render failed (exit {result.returncode})")


def main() -> None:
    if not MD_PATH.exists():
        raise SystemExit(f"Source markdown not found: {MD_PATH}")
    md_text = MD_PATH.read_text(encoding="utf-8")
    body_html = md_to_html_body(md_text)
    html = build_html(body_html)
    HTML_PATH.write_text(html, encoding="utf-8")
    render_pdf(HTML_PATH, PDF_PATH)
    size_kb = PDF_PATH.stat().st_size / 1024
    print(f"PDF written: {PDF_PATH} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
