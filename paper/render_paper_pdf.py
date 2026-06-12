#!/usr/bin/env python3
"""Render paper/ELEX_Research_Paper.md to a clean, figure-embedded PDF.

Single source of truth is the markdown file, so the PDF always reflects the
committed metrics. Figures 4-9 are embedded from ./outputs; Figures 1-3 are
conceptual and rendered as captions only. Pure-Python (reportlab), no system
binaries. Run:  python paper/render_paper_pdf.py
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib
from reportlab.lib.colors import HexColor, grey, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MD = HERE / "ELEX_Research_Paper.md"
OUT_PDF = HERE / "ELEX_Research_Paper.pdf"
OUTPUTS = ROOT / "outputs"

FIG_IMAGES = {
    "4": "algorithm_variants.png",
    "5": "simulation_steps.png",
    "6": "pdi_barplot.png",
    "7": "confusion_risk_barplot.png",
    "8": "trigger_plot.png",
    "9": "carplay_mockup.png",
}

# ---- Fonts (DejaVu shipped with matplotlib -> full unicode incl. arrows) ----
TTF = Path(matplotlib.get_data_path()) / "fonts" / "ttf"


def _reg(name, filename, fallback):
    p = TTF / filename
    if p.exists():
        pdfmetrics.registerFont(TTFont(name, str(p)))
        return name
    return fallback


BODY = _reg("Body", "DejaVuSerif.ttf", "Times-Roman")
BODY_B = _reg("Body-B", "DejaVuSerif-Bold.ttf", "Times-Bold")
BODY_I = _reg("Body-I", "DejaVuSerif-Italic.ttf", "Times-Italic")
BODY_BI = _reg("Body-BI", "DejaVuSerif-BoldItalic.ttf", "Times-BoldItalic")
HEAD = _reg("Head", "DejaVuSans-Bold.ttf", "Helvetica-Bold")
MONO = _reg("Mono", "DejaVuSansMono.ttf", "Courier")
pdfmetrics.registerFontFamily(BODY, normal=BODY, bold=BODY_B, italic=BODY_I,
                              boldItalic=BODY_BI)

INK = HexColor("#1a1a1a")
MUTED = HexColor("#444444")
ACCENT = HexColor("#0b3d66")

styles = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("title", fontName=HEAD, fontSize=18, leading=22,
                            alignment=TA_CENTER, textColor=ACCENT, spaceAfter=8),
    "subtitle": ParagraphStyle("subtitle", fontName=BODY, fontSize=10.5,
                               leading=14, alignment=TA_CENTER, textColor=MUTED),
    "author": ParagraphStyle("author", fontName=BODY_B, fontSize=11.5,
                             leading=15, alignment=TA_CENTER, textColor=INK,
                             spaceBefore=4),
    "h1": ParagraphStyle("h1", fontName=HEAD, fontSize=13.5, leading=17,
                         textColor=ACCENT, spaceBefore=14, spaceAfter=5),
    "h2": ParagraphStyle("h2", fontName=HEAD, fontSize=11, leading=14,
                         textColor=INK, spaceBefore=9, spaceAfter=3),
    "body": ParagraphStyle("body", fontName=BODY, fontSize=10, leading=14.5,
                          alignment=TA_JUSTIFY, textColor=INK, spaceAfter=7),
    "caption": ParagraphStyle("caption", fontName=BODY_I, fontSize=9,
                             leading=12, alignment=TA_CENTER, textColor=MUTED,
                             spaceBefore=4, spaceAfter=12),
    "code": ParagraphStyle("code", fontName=MONO, fontSize=7, leading=9,
                          textColor=INK, backColor=HexColor("#f5f5f5"),
                          leftIndent=4, rightIndent=4, borderPadding=5,
                          spaceBefore=4, spaceAfter=8),
    "cell": ParagraphStyle("cell", fontName=BODY, fontSize=8.5, leading=11),
    "cellh": ParagraphStyle("cellh", fontName=BODY_B, fontSize=8.5, leading=11,
                           textColor=white),
}

CAPTION_RE = re.compile(r"^\*\*(Figure|Table)\s+(\d+)\.?\s*(.*?)\*\*\s*$")


def inline(text: str) -> str:
    """Markdown inline -> reportlab mini-markup. No bare-URL linkify (safe)."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+?)`", r'<font face="%s">\1</font>' % MONO, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  r'<a href="\2" color="#0b3d66">\1</a>', text)
    return text


def fit_image(path: Path, max_w: float, max_h: float) -> Image:
    iw, ih = ImageReader(str(path)).getSize()
    scale = min(max_w / iw, max_h / ih)
    img = Image(str(path), width=iw * scale, height=ih * scale)
    img.hAlign = "CENTER"
    return img


def build():
    raw = MD.read_text(encoding="utf-8").split("\n")
    doc = SimpleDocTemplate(
        str(OUT_PDF), pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title="Improving 2D Navigation Clarity at Multi-Level Interchanges with ELEX",
        author="Satya Mani Sathkruth Damera",
    )
    avail_w = doc.width
    story = []
    seen_section = False
    title_done = False
    i = 0
    n = len(raw)
    while i < n:
        line = raw[i].rstrip("\n")
        s = line.strip()

        if not s:
            i += 1
            continue

        # Title (first H1)
        if not title_done and s.startswith("# ") and not s.startswith("## "):
            story.append(Paragraph(inline(s[2:].strip()), S["title"]))
            title_done = True
            i += 1
            continue

        # Section / subsection
        if s.startswith("### "):
            story.append(Paragraph(inline(s[4:].strip()), S["h2"]))
            i += 1
            continue
        if s.startswith("## "):
            seen_section = True
            story.append(Paragraph(inline(s[3:].strip()), S["h1"]))
            i += 1
            continue

        # Figure / Table caption line
        m = CAPTION_RE.match(s)
        if m:
            kind, num, rest = m.group(1), m.group(2), m.group(3).strip()
            if kind == "Figure" and num in FIG_IMAGES:
                imgpath = OUTPUTS / FIG_IMAGES[num]
                if imgpath.exists():
                    story.append(Spacer(1, 4))
                    story.append(fit_image(imgpath, avail_w, 4.0 * inch))
            cap = "<b>%s %s.</b> %s" % (kind, num, inline(rest))
            story.append(Paragraph(cap, S["caption"]))
            i += 1
            continue

        # Code fence
        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not raw[i].strip().startswith("```"):
                buf.append(raw[i])
                i += 1
            i += 1  # skip closing fence
            story.append(Preformatted("\n".join(buf), S["code"]))
            continue

        # Markdown table
        if s.startswith("|"):
            block = []
            while i < n and raw[i].strip().startswith("|"):
                block.append(raw[i].strip())
                i += 1
            rows = []
            for r_idx, rowline in enumerate(block):
                cells = [c.strip() for c in rowline.strip("|").split("|")]
                if r_idx == 1 and all(set(c) <= set("-: ") for c in cells):
                    continue  # separator row
                rows.append(cells)
            ncols = max(len(r) for r in rows)
            data = []
            for r_idx, r in enumerate(rows):
                r = r + [""] * (ncols - len(r))
                st = S["cellh"] if r_idx == 0 else S["cell"]
                data.append([Paragraph(inline(c), st) for c in r])
            col_w = [avail_w / ncols] * ncols
            tbl = Table(data, colWidths=col_w, repeatRows=1, hAlign="CENTER")
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f3f6f9")]),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#bcc7d1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(Spacer(1, 2))
            story.append(tbl)
            story.append(Spacer(1, 10))
            continue

        # Plain text line
        if not seen_section:
            story.append(Paragraph(inline(s), S["subtitle"] if not s.startswith("**Author")
                                   else S["author"]))
        else:
            story.append(Paragraph(inline(s), S["body"]))
        i += 1

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(BODY, 8)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(letter[0] / 2, 0.5 * inch, str(d.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("Wrote", OUT_PDF, "(%d KB)" % (OUT_PDF.stat().st_size // 1024))


if __name__ == "__main__":
    build()
