"""
generate_final_esad.py
======================
Generates the complete Bridgestone IT AI Assistant Enterprise Solution Architecture Document (BST-ESAD-2026-001)
with embedded dark-themed PNG diagrams, detailed 2-5 sentence figure explanations, professional tables,
and automatic Table of Contents. Exports both .docx and .pdf files.
"""

import os
import sys
import subprocess
from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DOCX_OUTPUT = r"C:\Projects\bridgestone-it-agent\BST-ESAD-2026-001_Bridgestone_IT_Agent_Final.docx"
PDF_OUTPUT  = r"C:\Projects\bridgestone-it-agent\BST-ESAD-2026-001_Bridgestone_IT_Agent_Final.pdf"
DIAGRAMS_DIR = r"C:\Projects\bridgestone-it-agent\diagrams"

C_RED        = "C80000"   # Bridgestone Red
C_NAVY       = "1A1A2E"   # Dark Navy
C_CORP_BLUE  = "2E4A7A"   # Corporate Blue
C_GREY_BG    = "F0F4F8"   # Alt table row
C_WHITE      = "FFFFFF"
C_NEAR_BLACK = "1A1A1A"
C_LIGHT_BLUE = "EBF3FB"   # Note box
C_AMBER_BG   = "FFF8E1"   # Important box
C_MID_GREY   = "888888"

BODY_FONT    = "Calibri"
HEAD_FONT    = "Calibri"

fig_counter  = [0]
tbl_counter  = [0]

def cell_shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    for existing in tcPr.findall(qn("w:shd")):
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)

def cell_margins(cell, top=80, bottom=80, left=120, right=120):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for side, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        tcMar.append(el)
    tcPr.append(tcMar)

def para_border_bottom(para, color=C_RED, sz="6"):
    pPr = para._p.get_or_add_pPr()
    for old in pPr.findall(qn("w:pBdr")):
        pPr.remove(old)
    pBdr = OxmlElement("w:pBdr")
    bot  = OxmlElement("w:bottom")
    bot.set(qn("w:val"),   "single")
    bot.set(qn("w:sz"),    sz)
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), color)
    pBdr.append(bot)
    pPr.append(pBdr)

def para_border_top(para, color=C_RED, sz="4"):
    pPr = para._p.get_or_add_pPr()
    for old in pPr.findall(qn("w:pBdr")):
        pPr.remove(old)
    pBdr = OxmlElement("w:pBdr")
    top  = OxmlElement("w:top")
    top.set(qn("w:val"),   "single")
    top.set(qn("w:sz"),    sz)
    top.set(qn("w:space"), "1")
    top.set(qn("w:color"), color)
    pBdr.append(top)
    pPr.append(pBdr)

def add_page_field(para):
    r = OxmlElement("w:r")
    r.append(OxmlElement("w:rPr"))
    fc1 = OxmlElement("w:fldChar")
    fc1.set(qn("w:fldCharType"), "begin")
    r.append(fc1)
    para._p.append(r)

    r2 = OxmlElement("w:r")
    r2.append(OxmlElement("w:rPr"))
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = " PAGE "
    r2.append(it)
    para._p.append(r2)

    r3 = OxmlElement("w:r")
    r3.append(OxmlElement("w:rPr"))
    fc2 = OxmlElement("w:fldChar")
    fc2.set(qn("w:fldCharType"), "end")
    r3.append(fc2)
    para._p.append(r3)

def add_toc_field(para):
    r = OxmlElement("w:r")
    fc1 = OxmlElement("w:fldChar")
    fc1.set(qn("w:fldCharType"), "begin")
    r.append(fc1)
    para._p.append(r)

    r2 = OxmlElement("w:r")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = ' TOC \\o "1-3" \\h \\z \\u '
    r2.append(it)
    para._p.append(r2)

    r3 = OxmlElement("w:r")
    fc2 = OxmlElement("w:fldChar")
    fc2.set(qn("w:fldCharType"), "end")
    r3.append(fc2)
    para._p.append(r3)

def set_col_width(cell, width_cm):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcW")):
        tcPr.remove(old)
    tcW = OxmlElement("w:tcW")
    tcW.set(qn("w:w"),    str(int(width_cm * 567)))
    tcW.set(qn("w:type"), "dxa")
    tcPr.append(tcW)

def set_table_borders(tbl, color="CCCCCC"):
    tblPr = tbl._tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl._tbl.insert(0, tblPr)
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)
    tblBdr = OxmlElement("w:tblBorders")
    for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        tblBdr.append(el)
    tblPr.append(tblBdr)

def _run(para, text, bold=False, italic=False, size=None, color=None, font=BODY_FONT, underline=False):
    r = para.add_run(text)
    r.bold      = bold
    r.italic    = italic
    r.underline = underline
    r.font.name = font
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    return r

def _new_para(doc, align=None, space_before=0, space_after=6, keep_with_next=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before   = Pt(space_before)
    pf.space_after    = Pt(space_after)
    pf.keep_with_next = keep_with_next
    if align is not None:
        p.alignment = align
    return p

def spacer(doc, pts=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(pts)
    p.paragraph_format.space_after  = Pt(0)
    return p

def hr(doc, color=C_RED):
    p = _new_para(doc, space_before=4, space_after=4)
    para_border_bottom(p, color=color, sz="6")
    return p

def h1(doc, text, num=None):
    full = f"{num}. {text}" if num else text
    p = doc.add_heading(level=1)
    p.clear()
    pf = p.paragraph_format
    pf.space_before   = Pt(18)
    pf.space_after    = Pt(6)
    pf.keep_with_next = True
    r = p.add_run(full)
    r.font.name       = HEAD_FONT
    r.font.size       = Pt(16)
    r.font.bold       = True
    r.font.color.rgb  = RGBColor.from_string(C_NAVY)
    para_border_bottom(p, color=C_RED, sz="8")
    return p

def h2(doc, text):
    p = doc.add_heading(level=2)
    p.clear()
    pf = p.paragraph_format
    pf.space_before   = Pt(12)
    pf.space_after    = Pt(4)
    pf.keep_with_next = True
    r = p.add_run(text)
    r.font.name       = HEAD_FONT
    r.font.size       = Pt(13)
    r.font.bold       = True
    r.font.color.rgb  = RGBColor.from_string(C_RED)
    return p

def h3(doc, text):
    p = doc.add_heading(level=3)
    p.clear()
    pf = p.paragraph_format
    pf.space_before   = Pt(8)
    pf.space_after    = Pt(3)
    pf.keep_with_next = True
    r = p.add_run(text)
    r.font.name       = HEAD_FONT
    r.font.size       = Pt(11)
    r.font.bold       = True
    r.font.color.rgb  = RGBColor.from_string(C_CORP_BLUE)
    return p

def body(doc, text, space_after=5):
    p = _new_para(doc, space_before=1, space_after=space_after)
    _run(p, text, size=10.5, color=C_NEAR_BLACK)
    return p

def bul(doc, text, level=0):
    style = "List Bullet" if level == 0 else "List Bullet 2"
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_after = Pt(3)
    _run(p, text, size=10.5, color=C_NEAR_BLACK)
    return p

def fig_caption(doc, text):
    fig_counter[0] += 1
    p = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=4)
    _run(p, f"Figure {fig_counter[0]} — {text}", italic=True, size=9, color="555555")
    return p

def fig_explanation(doc, explanation_text):
    p = _new_para(doc, space_before=2, space_after=12)
    _run(p, explanation_text, italic=True, size=9.5, color="333333")
    return p

def tbl_caption(doc, text):
    tbl_counter[0] += 1
    p = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=6)
    _run(p, f"Table {tbl_counter[0]} — {text}", italic=True, size=9, color="555555")
    return p

def note(doc, text):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_borders(tbl, color="CCCCCC")
    cell = tbl.cell(0, 0)
    cell_shade(cell, C_LIGHT_BLUE)
    cell_margins(cell, top=80, bottom=80, left=140, right=140)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(0)
    _run(p, "NOTE  ", bold=True, size=9.5, color=C_CORP_BLUE)
    _run(p, text, size=9.5, color=C_NEAR_BLACK)
    spacer(doc, 6)

def important(doc, *lines):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_borders(tbl, color="F0A500")
    cell = tbl.cell(0, 0)
    cell_shade(cell, C_AMBER_BG)
    cell_margins(cell, top=80, bottom=80, left=140, right=140)
    for i, line in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(3)
        if i == 0:
            _run(p, "IMPORTANT  ", bold=True, size=9.5, color="B85C00")
        _run(p, line, size=9.5, color=C_NEAR_BLACK)
    spacer(doc, 6)

def ptable(doc, headers, rows, col_widths_cm=None, caption_text=None):
    n_cols = len(headers)
    tbl = doc.add_table(rows=1 + len(rows), cols=n_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    set_table_borders(tbl, color="A0A0A0")

    for i, hdr in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        cell_shade(cell, C_NAVY)
        cell_margins(cell, top=80, bottom=80, left=120, right=80)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(0)
        _run(p, hdr, bold=True, size=9.5, color=C_WHITE, font=HEAD_FONT)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        if col_widths_cm and i < len(col_widths_cm):
            set_col_width(cell, col_widths_cm[i])

    for r_idx, row_data in enumerate(rows):
        bg = C_GREY_BG if r_idx % 2 == 1 else C_WHITE
        for c_idx, val in enumerate(row_data):
            cell = tbl.rows[r_idx + 1].cells[c_idx]
            cell_shade(cell, bg)
            cell_margins(cell, top=70, bottom=70, left=120, right=80)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(0)
            _run(p, str(val), size=9.5, color=C_NEAR_BLACK)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            if col_widths_cm and c_idx < len(col_widths_cm):
                set_col_width(cell, col_widths_cm[c_idx])

    spacer(doc, 4)
    if caption_text:
        tbl_caption(doc, caption_text)
    return tbl

def embed_diagram_with_explanation(doc, diagram_name, caption_text, explanation_text, width_inches=6.2):
    """
    Embed rendered dark-themed Mermaid PNG image into the Word document,
    append the figure caption, and write a 2-5 sentence technical architectural explanation.
    """
    png_path = os.path.join(DIAGRAMS_DIR, f"{diagram_name}.png")
    if os.path.exists(png_path):
        p = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=8, space_after=4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run()
        run.add_picture(png_path, width=Inches(width_inches))
        fig_caption(doc, caption_text)
        fig_explanation(doc, explanation_text)
    else:
        p = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=4)
        _run(p, f"[Diagram Image Pending: {diagram_name}.png]", italic=True, color=C_RED)
        fig_caption(doc, caption_text)
        fig_explanation(doc, explanation_text)

def apply_header_footer(doc):
    for section in doc.sections:
        section.header_distance = Cm(1.0)
        section.footer_distance = Cm(1.0)

        hdr = section.header
        hdr.is_linked_to_previous = False
        hp = hdr.paragraphs[0] if hdr.paragraphs else hdr.add_paragraph()
        hp.clear()
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.paragraph_format.space_before = Pt(0)
        hp.paragraph_format.space_after  = Pt(2)
        _run(hp, "Enterprise Solution Architecture Document  |  Bridgestone IT AI Assistant",
             italic=True, size=8, color=C_MID_GREY)
        para_border_bottom(hp, color=C_RED, sz="4")

        ftr = section.footer
        ftr.is_linked_to_previous = False
        fp = ftr.paragraphs[0] if ftr.paragraphs else ftr.add_paragraph()
        fp.clear()
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.paragraph_format.space_before = Pt(2)
        fp.paragraph_format.space_after  = Pt(0)
        para_border_top(fp, color=C_RED, sz="4")
        _run(fp, "Bridgestone IT AI Assistant  |  v1.0.0  |  Internal — Engineering Leadership  |  Page ",
             size=8, color="666666")
        add_page_field(fp)
        _run(fp, "  |  BST-ESAD-2026-001", size=8, color="666666")

def set_margins(doc, top=2.54, bottom=2.54, left=2.8, right=2.54):
    for s in doc.sections:
        s.top_margin    = Cm(top)
        s.bottom_margin = Cm(bottom)
        s.left_margin   = Cm(left)
        s.right_margin  = Cm(right)

def build_esad_doc():
    doc = Document()
    doc.styles["Normal"].font.name = BODY_FONT
    doc.styles["Normal"].font.size = Pt(10.5)
    set_margins(doc)

    # ── COVER PAGE ─────────────────────────────────────────────────────────────
    spacer(doc, 40)
    r1 = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0)
    _run(r1, "─" * 78, size=8, color=C_RED)
    spacer(doc, 14)

    p_org = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2)
    _run(p_org, "BRIDGESTONE IT ENGINEERING", bold=True, size=11, color="888888", font=HEAD_FONT)

    p_dept = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0)
    _run(p_dept, "Platform Engineering — AI & Automation", italic=True, size=10, color="AAAAAA")

    spacer(doc, 28)
    p_dtype = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=6)
    _run(p_dtype, "ENTERPRISE SOLUTION ARCHITECTURE DOCUMENT", bold=True, size=12, color="888888", font=HEAD_FONT)

    p_title = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=8)
    _run(p_title, "Bridgestone IT AI Assistant", bold=True, size=28, color=C_NAVY, font=HEAD_FONT)

    p_sub = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=6)
    _run(p_sub, "Enterprise AI-Powered IT Service Management Platform", italic=True, size=14, color=C_RED)

    spacer(doc, 28)
    r2 = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0)
    _run(r2, "─" * 78, size=8, color=C_RED)
    spacer(doc, 22)

    meta_data = [
        ("Document ID",     "BST-ESAD-2026-001"),
        ("Version",         "1.0.0"),
        ("Status",          "Released"),
        ("Date",            "July 2026"),
        ("Owner",           "Platform Engineering — AI & Automation"),
        ("Audience",        "Engineering Leadership · Principal Engineers · Enterprise Architects"),
        ("Classification",  "Internal — Engineering Leadership"),
    ]
    ctbl = doc.add_table(rows=len(meta_data), cols=2)
    ctbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(ctbl, color="888888")
    for i, (k, v) in enumerate(meta_data):
        lc = ctbl.rows[i].cells[0]
        rc = ctbl.rows[i].cells[1]
        cell_shade(lc, C_NAVY)
        cell_shade(rc, C_GREY_BG if i % 2 == 0 else C_WHITE)
        cell_margins(lc, top=90, bottom=90, left=140, right=100)
        cell_margins(rc, top=90, bottom=90, left=100, right=100)
        set_col_width(lc, 4.5)
        set_col_width(rc, 10.0)
        pl = lc.paragraphs[0]
        pl.paragraph_format.space_before = Pt(0)
        pl.paragraph_format.space_after  = Pt(0)
        _run(pl, k, bold=True, size=9.5, color=C_WHITE, font=HEAD_FONT)
        pr = rc.paragraphs[0]
        pr.paragraph_format.space_before = Pt(0)
        pr.paragraph_format.space_after  = Pt(0)
        _run(pr, v, size=9.5, color=C_NEAR_BLACK)

    doc.add_page_break()

    # ── REVISION HISTORY ──────────────────────────────────────────────────────
    h1(doc, "Revision History")
    ptable(doc,
           ["Version", "Date", "Author", "Description"],
           [
               ["0.1", "May 2026",  "Platform Engineering", "Initial draft — AI pipeline and integration architecture"],
               ["0.5", "June 2026", "Platform Engineering", "Security, database and deployment chapters added"],
               ["0.9", "July 2026", "Platform Engineering", "Full review; ADR, observability and roadmap added"],
               ["1.0", "July 2026", "Platform Engineering", "Final release for engineering leadership review"],
           ],
           col_widths_cm=[2.2, 2.8, 5.0, 10.0])

    doc.add_page_break()

    # ── TABLE OF CONTENTS ─────────────────────────────────────────────────────
    h1(doc, "Table of Contents")
    note(doc, "Open this document in Microsoft Word, then press Ctrl+A followed by F9 to populate the Table of Contents with page numbers.")
    toc_para = _new_para(doc, space_before=4, space_after=4)
    add_toc_field(toc_para)
    doc.add_page_break()

    # ── CH 3: EXECUTIVE SUMMARY ────────────────────────────────────────────────
    h1(doc, "Executive Summary", num=3)
    body(doc, "The Bridgestone IT AI Assistant is an enterprise-grade, AI-augmented IT Service Desk platform designed to reduce Level-1 support load, improve Mean Time To Resolution (MTTR), and preserve ServiceNow as the authoritative system of record.")
    body(doc, "The platform routes employee IT issues through a 23-node LangGraph agentic pipeline before escalating to human intervention. The AI agent conducts structured interviews, retrieves enterprise knowledge, executes diagnostic tools (VPN, Active Directory, Network), performs root-cause reflection, and — where self-service resolution is impossible — creates a properly enriched, validated ServiceNow Incident automatically.")
    body(doc, "A dual-approval workflow governs privileged software installation requests, routing through Manager approval and IT Admin grant operations without human triage. Four-role JWT-secured RBAC separates employee, manager, admin and superadmin concerns across dedicated portal surfaces.")
    spacer(doc, 4)
    important(doc,
        "Platform Impact:",
        "  • Eliminates manual first-line triage for common IT issue categories",
        "  • Removes classification errors through AI-validated, schema-driven ServiceNow field mapping",
        "  • Provides real-time SLA visibility with automated seven-state escalation",
        "  • Delivers complete auditability through an append-only immutable audit trail")

    # ── CH 4: BUSINESS PROBLEM ────────────────────────────────────────────────
    h1(doc, "Business Problem", num=4)
    h2(doc, "4.1 Context")
    body(doc, "Enterprise IT helpdesks operating at scale face a structural imbalance: ticket volume grows linearly with headcount, while Level-1 staffing is constrained by cost. At Bridgestone, this produces five measurable failure modes.")
    h2(doc, "4.2 Failure Modes")
    ptable(doc,
           ["Failure Mode", "Root Cause", "Business Impact"],
           [
               ["High L1 ticket volume",             "Manual triage of repetitive issues",                    "Increased cost per ticket, slow MTTR"],
               ["Incorrect ServiceNow classification","Human error in category / assignment group selection",  "Mis-routed tickets, SLA breach"],
               ["Approval process latency",          "Manual manager notification for privileged requests",    "Delayed productivity recovery"],
               ["SLA breach detection lag",          "Reactive monitoring; no automated escalation",           "SLA compliance risk, degraded experience"],
               ["Lack of self-service resolution",   "No intelligent guidance before ticket creation",         "Unnecessary L1 escalation for solvable issues"],
           ],
           col_widths_cm=[5.0, 6.5, 6.5],
           caption_text="Business Failure Modes")
    h2(doc, "4.3 Architectural Constraints")
    for c in [
        "ServiceNow must remain the system of record — no parallel ticket stores.",
        "Existing Microsoft ecosystem (Active Directory, Microsoft Graph, Outlook) must be respected.",
        "The solution must be deployable inside the Bridgestone network perimeter.",
        "AI output must never directly create side effects without deterministic validation.",
    ]:
        bul(doc, c)

    # ── CH 5: BUSINESS OBJECTIVES ─────────────────────────────────────────────
    h1(doc, "Business Objectives", num=5)
    ptable(doc,
           ["#", "Objective", "Measurement"],
           [
               ["O-1", "Reduce L1 ticket volume",                         "Percentage of issues resolved without ticket creation"],
               ["O-2", "Reduce MTTR",                                     "Average time from report to resolution"],
               ["O-3", "Improve ticket classification accuracy",          "ServiceNow field validation pass rate"],
               ["O-4", "Automate privileged software approval workflow",   "End-to-end time: request to access grant"],
               ["O-5", "Improve employee self-service experience",        "First-contact resolution rate"],
               ["O-6", "Maintain complete auditability",                  "Audit log coverage across all state transitions"],
               ["O-7", "Preserve ServiceNow as system of record",        "All incidents traceable to a ServiceNow INC number"],
               ["O-8", "Enforce SLA compliance with automated escalation","Percentage of tickets escalated before SLA breach"],
           ],
           col_widths_cm=[1.5, 7.5, 9.0],
           caption_text="Business Objectives")

    # ── CH 6: SOLUTION OVERVIEW ───────────────────────────────────────────────
    h1(doc, "Solution Overview", num=6)
    h2(doc, "6.1 Architecture Pattern")
    body(doc, "The platform is built on a Hybrid AI + Deterministic architecture. AI reasoning handles ambiguous, contextual decisions — intent detection, diagnostic planning, root-cause analysis, reflection and classification. Deterministic services handle all outcomes governed by business rules — approval routing, SLA computation, ServiceNow field mapping and state machine transitions.")
    body(doc, "This separation is deliberate. AI output is non-deterministic by nature. Every AI decision that produces a side effect (ticket creation, approval, access grant) is gated by deterministic validation before execution.")

    h2(doc, "6.2 Platform Layers")
    ptable(doc,
           ["Layer", "Technology", "Responsibility"],
           [
               ["Presentation Layer",   "Next.js 16 / React 19",            "Four role-separated portal surfaces (Employee · Manager · Admin · SuperAdmin)"],
               ["API Gateway Layer",    "FastAPI + Uvicorn",                 "Authentication, RBAC, rate limiting, security headers, PromptGuard"],
               ["AI Orchestration",     "LangGraph StateGraph",             "23-node conditional AI pipeline with multi-step diagnostic loops"],
               ["Deterministic Logic",  "Classification & SLA Services",     "Business-rule enforcement on all AI outcomes before system mutation"],
               ["Integration Layer",    "ServiceNow, Graph, AD, VPN Adapters","Adapter-pattern enterprise system connectors with mock/live toggle"],
               ["Data Tier",            "PostgreSQL 14 & Redis",            "ACID relational storage and metadata / session caching"],
           ],
           col_widths_cm=[4.0, 5.0, 9.0],
           caption_text="Platform Architecture Layers")

    h2(doc, "6.3 Platform Scope")
    ptable(doc,
           ["In Scope", "Out of Scope"],
           [
               ["L1 AI-driven issue diagnosis",                  "L2/L3 deep infrastructure troubleshooting"],
               ["ServiceNow incident creation and lifecycle",    "ServiceNow configuration and CMDB management"],
               ["Privileged software request approval workflow", "Software licensing management"],
               ["SLA monitoring and automated escalation",       "ITSM capacity planning"],
               ["RBAC-separated portal surfaces",                "HR and payroll integration"],
               ["Audit logging for compliance",                  "SOC/SIEM integration (roadmap)"],
           ],
           col_widths_cm=[9.0, 9.0],
           caption_text="Platform Scope")

    # ── CH 7: FUNCTIONAL CAPABILITIES ─────────────────────────────────────────
    h1(doc, "Functional Capabilities", num=7)
    h2(doc, "7.1 Core Capabilities")
    ptable(doc,
           ["Capability", "Description"],
           [
               ["Conversational AI Triage",            "Employees describe issues in natural language; the agent conducts a structured diagnostic interview before escalating"],
               ["Multi-Step Troubleshooting",          "The agent iteratively executes tool chains (VPN, AD, network) and loops until resolution or escalation"],
               ["Automatic ServiceNow Incident Creation","Issues that cannot be self-resolved are classified, enriched, validated and submitted to ServiceNow via OAuth2"],
               ["Dual-Approval Workflow",              "Privileged requests route through Manager approval, then Admin access grant, tracked in DB and ServiceNow"],
               ["SLA Engine",                          "APScheduler job evaluates open tickets every 60 seconds, progressing through seven escalation states"],
               ["Role-Separated Portals",              "Four purpose-built surfaces for Employee, Manager, IT Admin and SuperAdmin roles"],
               ["Analytics Dashboard",                 "Ticket volume by category and team, priority breakdown, SLA compliance trend"],
               ["Knowledge Base",                      "Admin-managed KB articles with AI-assisted article suggestion from resolved ticket context"],
           ],
           col_widths_cm=[5.5, 12.5])

    h2(doc, "7.2 Platform-Level Capabilities")
    ptable(doc,
           ["Capability", "Implementation"],
           [
               ["Prompt Injection Protection", "Three-tier risk classifier (HIGH → reject, MEDIUM → sanitise, LOW → warn) on every user message"],
               ["Rate Limiting",               "Per-user/per-IP sliding-window limiter on /chat, /auth/login, /upload — no external dependencies"],
               ["Immutable Audit Log",          "Append-only RBAC audit trail: SHA-256 payload hash, correlation ID, actor, ISO-8601 timestamp"],
               ["Distributed Tracing",          "OpenTelemetry-compatible trace_span context manager instruments every pipeline node and LLM call"],
               ["Structured JSON Logging",      "Per-request correlation ID propagated via Python contextvars through every log statement"],
               ["Auto Schema Migration",        "Missing database columns detected and added on startup — no manual migration tooling required"],
           ],
           col_widths_cm=[5.5, 12.5])

    # ── CH 8: ENTERPRISE BUSINESS WORKFLOW ────────────────────────────────────
    h1(doc, "Enterprise Business Workflow", num=8)

    h2(doc, "8.1 Employee Issue Resolution Flow")
    body(doc, "The interaction sequence below details how an employee request moves from raw chat input through the security gateway, diagnostic graph, tool execution, and optional ServiceNow incident creation.")
    embed_diagram_with_explanation(
        doc,
        "fig_8_1_issue_resolution",
        "Employee Issue Resolution — End-to-End Sequence Diagram",
        "Figure 1 illustrates the end-to-end processing sequence for employee IT support interactions. Inbound HTTP requests traverse a mandatory FastAPI middleware security chain (Rate Limiter, JWT Auth, RBAC, and PromptGuard) before reaching the LangGraph StateGraph engine. Within the pipeline, diagnostic tools are invoked iteratively to gather evidence; if self-service resolution fails, an enriched ServiceNow incident is created via OAuth2 REST APIs, returning an official ticket number to the user."
    )

    h2(doc, "8.2 Privileged Software Approval Workflow")
    body(doc, "Requests for privileged software (e.g. VS Code, SAP GUI, Adobe CC) follow a strict two-stage human-in-the-loop approval workflow before local access is granted.")
    embed_diagram_with_explanation(
        doc,
        "fig_8_2_approval_workflow",
        "Privileged Software Dual-Approval Workflow Sequence",
        "Figure 2 depicts the state synchronization across the platform database, ServiceNow, Manager portal, and IT Admin queue for privileged requests. When an employee requests restricted software, the AI classifies the intent as a software installation requiring approval and immediately persists a ticket in WAITING_MANAGER status while notifying ServiceNow. Following Manager approval, the status transitions to READY_FOR_ADMIN, whereupon an IT Administrator issues temporary credentials (LAPS) and completes the ticket in ServiceNow."
    )

    h2(doc, "8.3 SLA Escalation State Machine")
    body(doc, "The platform SLA engine evaluates open incidents every 60 seconds against defined operational level agreements.")
    embed_diagram_with_explanation(
        doc,
        "fig_8_3_sla_state_machine",
        "SLA Escalation State Machine — Workflow States",
        "Figure 3 details the seven-state SLA lifecycle transition matrix enforced by the background scheduler. Tickets originate in the HEALTHY state and progress through WARNING_75 (75% elapsed) and WARNING_90 (90% elapsed) triggers, notifying Managers and IT Administrators accordingly. If 100% of the SLA window elapses before resolution, the ticket transitions to BREACHED and automatically initiates Level-1, Level-2, and Level-3 management escalations at 30-minute intervals."
    )

    # ── CH 9: HIGH-LEVEL SYSTEM ARCHITECTURE ──────────────────────────────────
    h1(doc, "High-Level System Architecture", num=9)
    h2(doc, "9.1 Architecture Overview")
    body(doc, "The Bridgestone IT AI Assistant platform is structured into clean architectural tiers ensuring complete isolation between presentation, gateway, agentic reasoning, deterministic logic, and persistent storage.")
    embed_diagram_with_explanation(
        doc,
        "fig_9_1_high_level_arch",
        "High-Level System Architecture — Component Topology",
        "Figure 4 presents the macro architectural topology of the platform across seven isolated layers. Nginx handles intranet ingress and TLS termination, routing web traffic to Next.js portal surfaces and API requests to FastAPI gateway middleware. Business logic is cleanly segmented between LangGraph agentic reasoning, deterministic validation services, enterprise integration adapters (ServiceNow, Active Directory, VPN), and persistent data stores (PostgreSQL, Redis)."
    )

    h2(doc, "9.2 Architectural Zones")
    ptable(doc,
           ["Zone", "Responsibility", "Key Design Decision"],
           [
               ["Client Layer",          "Role-separated portal surfaces",                          "Single Next.js app; portal views gated by JWT role"],
               ["API Gateway",           "Auth, authorisation, rate limiting, injection guard",     "All cross-cutting concerns resolved before business logic executes"],
               ["AI Orchestration",      "Multi-step reasoning, planning, tool execution",          "LangGraph StateGraph provides deterministic routing between AI nodes"],
               ["Deterministic Services","Classification, enrichment, SLA, approval",              "AI output is never directly submitted to external systems — always validated first"],
               ["Integration Layer",     "Enterprise system adapters",                             "Adapter pattern with mock/live toggle per environment variable"],
               ["Data Layer",            "Persistence and caching",                               "SQLAlchemy ORM; database-agnostic for dev/prod parity"],
           ],
           col_widths_cm=[4.0, 5.5, 8.5])

    # ── CH 10: AI ARCHITECTURE ────────────────────────────────────────────────
    h1(doc, "AI Architecture", num=10)
    h2(doc, "10.1 Purpose & AI System Responsibilities")
    body(doc, "The AI subsystem performs four distinct functions: natural language intent recognition, diagnostic interview planning, root-cause hypothesis reflection, and ITSM taxonomy classification. To eliminate non-deterministic failure modes, AI components operate within strict boundaries.")

    h2(doc, "10.2 AI Provider Fallback Architecture")
    body(doc, "To prevent platform outage during primary LLM rate-limiting or provider failure, the AI abstraction layer implements a three-tier resilient fallback model.")
    embed_diagram_with_explanation(
        doc,
        "fig_10_1_ai_fallback",
        "AI Provider Three-Tier Fallback Architecture",
        "Figure 5 illustrates the multi-provider failover strategy implemented behind the BaseAIProvider abstraction. Inbound requests are first routed to Google Gemini 2.5 Flash for high-speed intent detection and tool planning; upon API timeout or rate-limit exceptions, traffic seamlessly fails over to Anthropic Claude 3 Sonnet. If all external LLM services become unavailable, the pipeline falls back to a deterministic 11-domain keyword regular expression engine to maintain triage availability."
    )

    h2(doc, "10.3 AI Responsibilities by Node")
    ptable(doc,
           ["Node", "AI Role", "Deterministic Gate"],
           [
               ["Router",              "Classify message as CHAT or TROUBLESHOOT",                         "Exact string match on output"],
               ["Context Router",      "Route to correct pipeline branch",                                 "Output constrained to four enum values"],
               ["Intent",              "Classify IT issue category",                                       "Validated against valid_categories from incident_config.json"],
               ["Diagnostic Interview","Determine information sufficiency; generate targeted questions",    "Short-circuit to END if questions are pending"],
               ["Planner",             "Generate ordered tool execution plan",                             "Plan validated against registered tool registry"],
               ["Knowledge",           "Retrieve and rank relevant KB articles",                          "Top-N selected by relevance score"],
               ["Tool",                "Select and execute enterprise tool",                              "Tool result validated before state update"],
               ["Multi-Step",          "Evaluate tool results; decide whether to loop or escalate",       "troubleshooting_complete boolean controls loop exit"],
               ["Root Cause",          "Synthesise hypothesis from tool chain results",                   "Structured JSON output validated by Pydantic"],
               ["Reflection",          "Evaluate reasoning quality; flag low-confidence decisions",       "Reflection score used by Decision node"],
               ["Decision",            "Choose: CREATE_TICKET, EXECUTE_ACTION, or ASK_MORE_INFO",        "Enum output; unknown values default to ASK_MORE_INFO"],
               ["Approval",            "Evaluate whether action requires approval",                       "Approval status: PENDING, APPROVED, REJECTED"],
               ["Classification",      "Assign ITSM category, subcategory, assignment group, CI",        "Validated against live ServiceNow metadata before submission"],
           ],
           col_widths_cm=[4.0, 5.5, 8.5],
           caption_text="AI Node Responsibilities and Deterministic Gates")

    h2(doc, "10.4 Classification Service Design")
    body(doc, "The ClassificationService acts as the boundary between AI output and ServiceNow incident creation. It enforces confidence thresholds (HIGH >= 0.90, MEDIUM 0.70-0.89, LOW < 0.70) and routes responses through Pydantic schema validation before payload construction.")

    # ── CH 11: LANGGRAPH WORKFLOW ─────────────────────────────────────────────
    h1(doc, "LangGraph Workflow", num=11)
    h2(doc, "11.1 StateGraph Architecture")
    body(doc, "The core AI reasoning pipeline is implemented as a 23-node LangGraph StateGraph (`backend/app/graph/graph.py`). The state graph enforces TypedDict schema validation across every turn and decouples node logic from graph routing.")

    h2(doc, "11.2 AgentState Schema & Field Groups")
    ptable(doc,
           ["Field Group", "Fields"],
           [
               ["Session Context", "session_id, username, user_role, user_message"],
               ["Routing",         "decision, route, intent"],
               ["AI Outputs",      "root_cause_analysis, reflection, plan, knowledge_context, tool_result"],
               ["Approval",        "approval_required, approval_status, approval_action"],
               ["Ticket",          "ticket, ticket_lifecycle, assigned_team"],
               ["Multi-Step",      "tool_chain, hypothesis_tracker, troubleshooting_iterations, troubleshooting_complete, next_tool"],
               ["Diagnostic",      "diagnostic_interview, conversation_goal, active_issue"],
               ["SLA",             "sla, notifications"],
           ],
           col_widths_cm=[4.5, 13.5],
           caption_text="AgentState TypedDict — Field Groups")

    h2(doc, "11.3 23-Node StateGraph Topology")
    body(doc, "The 23-node state graph controls execution flow through conditional edge routing based on conversation state, intent classification, and diagnostic completion.")
    embed_diagram_with_explanation(
        doc,
        "fig_11_1_langgraph_workflow",
        "LangGraph 23-Node Workflow — Conditional State Graph Topology",
        "Figure 6 details the full 23-node state machine governing the AI agent execution lifecycle. Inbound interactions enter through the Router node, which separates conversational chat from diagnostic troubleshooting. The multi-step diagnostic loop iteratively invokes system tools (VPN, Active Directory, Ping) and routes through Root Cause and Reflection nodes before rendering terminal decisions (Ticket Creation, Action Execution, or User Clarification)."
    )

    h2(doc, "11.4 Conditional Routing Logic")
    ptable(doc,
           ["Conditional Edge", "Routing Logic"],
           [
               ["route_after_router",              "decision == 'CHAT' → conversation; otherwise → memory"],
               ["context_router",                  "Lambda on state['route']: ticket_lifecycle | ticket_status | service_request | intent"],
               ["route_after_diagnostic_interview", "decision_response populated → END; else → planner"],
               ["route_after_multi_step",           "troubleshooting_complete is False and next_tool is not None → tool; else → root_cause"],
               ["route_decision",                   "CREATE_TICKET → ticket; EXECUTE_ACTION → approval; else → END"],
               ["route_after_approval",             "approval_status == 'APPROVED' → action; else → END"],
               ["route_after_lifecycle",            "ticket['ticket_id'] exists → assignment; else → notification"],
           ],
           col_widths_cm=[6.0, 12.0],
           caption_text="LangGraph Conditional Edge Routing Logic")

    # ── CH 12: CONVERSATION LIFECYCLE ─────────────────────────────────────────
    h1(doc, "Conversation Lifecycle", num=12)
    h2(doc, "12.1 Session State & Memory Persistence")
    body(doc, "Conversations are keyed by session_id in the platform database (`conversations` and `conversation_events` tables). The Memory node fetches dialogue history prior to pipeline execution and serializes updated state context upon completion.")

    h2(doc, "12.2 Diagnostic Interview & Information Sufficiency")
    body(doc, "The Diagnostic Interview node evaluates whether sufficient contextual details (device ID, error codes, network location) are present before diagnostic planning begins. If required fields are missing, targeted clarification questions are rendered to the employee, pausing pipeline execution until the next turn.")

    # ── CH 13: SERVICENOW INTEGRATION ────────────────────────────────────────
    h1(doc, "ServiceNow Integration Architecture", num=13)
    h2(doc, "13.1 Adapter Pattern & ServiceNow Client")
    body(doc, "Enterprise integrations implement an adapter design pattern with explicit mock/live environment toggles. `ServiceNowClient` manages OAuth2 Password Grant tokens with thread-safe RLock refresh protection.")
    embed_diagram_with_explanation(
        doc,
        "fig_12_1_integration_topology",
        "Enterprise Integration Adapter Topology",
        "Figure 7 illustrates the system integration topology connecting the core FastAPI backend with enterprise endpoints. ServiceNow interactions pass through a thread-safe token manager and a 3600-second metadata cache. External API calls to ServiceNow Table API, Microsoft Graph (Entra ID), and GlobalProtect VPN gateways are abstracted behind unified interfaces that toggle between live HTTPS calls and mock fixtures based on environment settings."
    )

    h2(doc, "13.2 ServiceNow Metadata Validation Pipeline")
    body(doc, "To prevent invalid field submission errors when creating incidents, the platform routes AI outputs through a rigorous 4-stage validation pipeline.")
    embed_diagram_with_explanation(
        doc,
        "fig_12_2_servicenow_validation",
        "ServiceNow Metadata Validation Pipeline",
        "Figure 8 outlines the deterministic validation chain applied to LLM classification outputs before invoking ServiceNow REST APIs. Raw AI predictions are first mapped to canonical ServiceNow choice values by the FieldMappingService using `incident_config.json`. The MetadataValidator checks choice existence against cached instance choices; if an invalid choice is detected, local taxonomy defaults apply before IncidentEnrichmentService computes impact, urgency, and priority values."
    )

    h2(doc, "13.3 ServiceNow Incident Lifecycle")
    ptable(doc,
           ["Platform Status", "ServiceNow Trigger / Action", "Valid Next Status"],
           [
               ["NEW",            "Platform creates INC via OAuth2",          "IN_PROGRESS or WAITING_MANAGER"],
               ["WAITING_MANAGER","SOFTWARE_INSTALLATION / privileged request","READY_FOR_ADMIN or REJECTED"],
               ["READY_FOR_ADMIN","Manager approves",                         "ACCESS_GRANTED"],
               ["ACCESS_GRANTED", "Admin grants LAPS credentials",            "COMPLETED"],
               ["IN_PROGRESS",    "Assigned to team",                         "RESOLVED"],
               ["RESOLVED",       "Engineer resolves",                        "CLOSED (auto)"],
               ["CLOSED",         "Final state",                              "—"],
               ["REJECTED",       "Manager rejects request",                  "CLOSED"],
           ],
           col_widths_cm=[4.5, 7.0, 6.5],
           caption_text="ServiceNow Incident Lifecycle — Platform Status States")

    # ── CH 14: SECURITY ARCHITECTURE ──────────────────────────────────────────
    h1(doc, "Security Architecture", num=14)
    h2(doc, "14.1 Defence-in-Depth Layer Stack")
    body(doc, "The security model implements strict defence-in-depth across perimeter, transport, application, and compliance audit layers.")
    embed_diagram_with_explanation(
        doc,
        "fig_13_1_security_stack",
        "Security Defence-in-Depth Layered Architecture",
        "Figure 9 details the 4-layer security architecture enforcing corporate data protection standards. Perimeter TLS 1.3 termination at Nginx is fortified by transport-layer HTTP security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options). Application middleware enforces 512 KB request payload limits, sliding-window rate limiting, PromptGuard injection scanning, and JWT RBAC checks, while all state modifications append to an immutable SHA-256 audit log."
    )

    h2(doc, "14.2 Authentication & Authorization Flow")
    body(doc, "User authentication utilizes bcrypt password hashing and PyJWT HS256 token issuance. Every endpoint verifies token claims and role authorization via `RoleChecker` dependencies.")
    embed_diagram_with_explanation(
        doc,
        "fig_13_2_auth_flow",
        "Authentication and Authorisation Sequence Flow",
        "Figure 10 demonstrates the credential verification and Bearer token lifecycle. Upon successful `/auth/login` authentication against bcrypt password hashes in the database, the API issues a 30-minute access token and a 7-day refresh token. Subsequent request headers are parsed by FastAPI `oauth2_scheme`, verifying HS256 signatures, token expiry, and user role entitlements prior to pipeline invocation."
    )

    h2(doc, "14.3 Role-Based Access Control (RBAC)")
    ptable(doc,
           ["Role", "Permitted Endpoints"],
           [
               ["EMPLOYEE",   "/chat, /my-tickets, /auth/me"],
               ["MANAGER",    "/chat, /manager/tickets/*, /analytics/*, /auth/me"],
               ["ADMIN",      "/tickets/*, /admin/queue, /admin/tickets/*, /analytics/*, /knowledge/*, /auth/me"],
               ["SUPERADMIN", "All endpoints"],
           ],
           col_widths_cm=[3.5, 14.5],
           caption_text="Role-Based Access Control Model")

    h2(doc, "14.4 PromptGuard Injection Classifier")
    body(doc, "PromptGuard protects the LLM pipeline against prompt injection attacks using full-phrase anchored regular expressions.")
    ptable(doc,
           ["Risk Level", "Action", "Pattern Examples"],
           [
               ["HIGH",   "HTTP 400 + ImmutableAuditLog entry",     "'ignore all instructions', 'you are now DAN', 'forget your previous instructions'"],
               ["MEDIUM", "Sanitise fragment — pipeline continues",  "'act as X without restrictions', 'from now on you must', [INST] markers"],
               ["LOW",    "Allow — emit structured warning log",     "Ambiguous phrasing partially matching medium patterns"],
           ],
           col_widths_cm=[2.8, 5.2, 10.0],
           caption_text="PromptGuard Three-Tier Injection Classification")

    h2(doc, "14.5 Immutable Audit Logging")
    body(doc, "Compliance auditability is maintained by `ImmutableAuditLog`, which exposes only an append-only `record()` method. Every entry captures correlation ID, actor identity, action type, timestamp, and a SHA-256 hash of the JSON payload.")

    # ── CH 15: DATABASE ARCHITECTURE ──────────────────────────────────────────
    h1(doc, "Database Architecture", num=15)
    h2(doc, "15.1 Data Model Overview")
    body(doc, "The database tier encompasses 19 SQLAlchemy ORM models organized across Identity, ITSM Workflow, AI Pipeline, Compliance Audit, SLA Tracking, and Platform Operations domains.")

    h2(doc, "15.2 Core Entity Relationship Diagram")
    body(doc, "Primary data models maintain relational integrity across user identities, tickets, approval records, and SLA event histories.")
    embed_diagram_with_explanation(
        doc,
        "fig_14_1_er_diagram",
        "Core Database Entity Relationship Diagram",
        "Figure 11 defines the core entity relationship schema governing the relational database. User records maintain 1-to-many relationships with Ticket entities. Each Ticket tracks historical lifecycle changes across SlaEscalationHistory, SlaAuditEvent, ApprovalHistory, TicketTimeline, and TicketComment tables, while AuditLog and RbacAuditLog maintain unconstrained append-only audit structures."
    )

    h2(doc, "15.3 Core Entities Table")
    ptable(doc,
           ["Entity", "Table", "Key Fields"],
           [
               ["User",                "users",                   "id, username (UK), role, hashed_password, is_active"],
               ["Ticket",              "tickets",                 "ticket_id (UK), category, status, request_type, servicenow_id, servicenow_number, sla_state, approval_status, laps_*"],
               ["AuditLog",            "audit_logs",              "correlation_id, event_type, actor, payload_hash, payload_json, timestamp"],
               ["SlaEscalationHistory","sla_escalation_history",  "ticket_id (FK), escalation_level, notified_recipients, escalated_at"],
               ["SlaAuditEvent",       "sla_audit_events",        "ticket_id (FK), event_type, sla_pct, sla_state, event_at"],
               ["RbacAuditLog",        "rbac_audit_logs",         "username, role, action, resource, outcome, correlation_id, timestamp"],
               ["ApprovalHistory",     "approval_history",        "ticket_id (FK), action, performed_by, notes, performed_at"],
               ["Conversation",        "conversations",           "session_id (UK), username, history_json, created_at, updated_at"],
               ["KnowledgeDraft",      "knowledge_drafts",        "title, root_cause, resolution, category, confidence, status, source_ticket_id (FK)"],
           ],
           col_widths_cm=[4.5, 4.5, 9.0],
           caption_text="Core Database Entities — Key Fields")

    # ── CH 16: API REQUEST LIFECYCLE ──────────────────────────────────────────
    h1(doc, "API Request Lifecycle", num=16)
    h2(doc, "16.1 End-to-End Chat API Request Lifecycle")
    body(doc, "Inbound HTTP requests to `/chat` traverse sequential middleware components prior to AI state graph invocation.")
    embed_diagram_with_explanation(
        doc,
        "fig_15_1_api_lifecycle",
        "Chat Endpoint API Request Lifecycle Sequence",
        "Figure 12 traces the multi-layered execution path of an incoming POST `/chat` payload. Request execution begins at Nginx, moving sequentially through RequestSizeLimitMiddleware (<=512 KB), RateLimiter (30 req/min sliding window), JWT Auth & RoleChecker dependencies (EMPLOYEE role verification), and PromptGuard injection scanning. Only payloads successfully clearing all validation gates enter the LangGraph execution engine."
    )

    h2(doc, "16.2 Middleware Failure Handling")
    ptable(doc,
           ["Layer", "Failure Response", "Audit Action"],
           [
               ["Request Size Limit", "HTTP 413",                             "Warning log"],
               ["Rate Limiter",       "HTTP 429 + Retry-After header",        "Warning log"],
               ["JWT Auth",           "HTTP 401",                             "SECURITY_UNAUTHORIZED_TOTAL metric incremented"],
               ["Role Checker",       "HTTP 403",                             "RBAC audit log entry + SECURITY_PERMISSION_DENIED_TOTAL"],
               ["PromptGuard HIGH",   "HTTP 400",                             "ImmutableAuditLog entry with matched pattern"],
               ["PromptGuard MEDIUM", "Request sanitised — pipeline continues","Structured warning log emitted"],
           ],
           col_widths_cm=[4.0, 5.5, 8.5],
           caption_text="Middleware Chain Failure Responses")

    h2(doc, "16.3 Full API Surface")
    ptable(doc,
           ["Method", "Endpoint", "Role", "Description"],
           [
               ["POST", "/auth/login",                        "Public",           "Issue JWT access + refresh tokens"],
               ["GET",  "/auth/me",                           "Authenticated",    "Return current user identity and role"],
               ["POST", "/chat",                              "EMPLOYEE",         "Submit message to AI pipeline"],
               ["GET",  "/my-tickets",                        "EMPLOYEE",         "List user's own tickets"],
               ["GET",  "/tickets",                           "ADMIN, MANAGER",   "List all tickets"],
               ["GET",  "/tickets/{id}",                      "ADMIN, MANAGER",   "Get full ticket detail"],
               ["PUT",  "/tickets/{id}/status",               "ADMIN",            "Update ticket status"],
               ["GET",  "/manager/tickets",                   "MANAGER, ADMIN",   "Pending approval queue"],
               ["POST", "/manager/tickets/{id}/approve",      "MANAGER",          "Approve privileged request"],
               ["POST", "/manager/tickets/{id}/reject",       "MANAGER",          "Reject privileged request"],
               ["GET",  "/admin/queue",                       "ADMIN",            "Admin action queue"],
               ["POST", "/admin/tickets/{id}/grant-access",   "ADMIN",            "Grant temporary admin access (LAPS)"],
               ["POST", "/admin/tickets/{id}/complete",       "ADMIN",            "Mark ticket complete"],
               ["GET",  "/analytics/*",                       "ADMIN, MANAGER",   "Analytics and reporting endpoints"],
               ["GET",  "/knowledge/*",                       "ADMIN",            "Knowledge base management"],
               ["GET",  "/health",                            "Public",           "Liveness probe"],
               ["GET",  "/metrics",                           "Internal",         "Prometheus metrics scrape endpoint"],
           ],
           col_widths_cm=[1.8, 6.2, 3.5, 6.5],
           caption_text="Full API Surface")

    # ── CH 17: DEPLOYMENT ARCHITECTURE ────────────────────────────────────────
    h1(doc, "Deployment Architecture", num=17)
    h2(doc, "17.1 Production Docker Topology")
    body(doc, "Production deployment utilizes Docker Compose with isolated container networks, persistent named volumes, and container health check dependencies.")
    embed_diagram_with_explanation(
        doc,
        "fig_16_1_deployment_topology",
        "Docker Compose Production Deployment Topology",
        "Figure 13 illustrates the containerized service composition operating within the isolated `bridgestone-network` bridge. Nginx acts as the single external gateway exposing ports 80 and 443. Next.js frontend and FastAPI backend containers communicate over internal ports, depending on PostgreSQL and Redis health checks before accepting incoming connections."
    )

    h2(doc, "17.2 Environment Matrix")
    ptable(doc,
           ["Environment", "Database", "ServiceNow", "Graph / AD", "Compose File"],
           [
               ["Development",   "SQLite (local)",                              "Mock", "Mock", "docker-compose.dev.yml"],
               ["QA",            "PostgreSQL (container)",                      "Mock", "Mock", "docker-compose.qa.yml"],
               ["Backend-only",  "SQLite (local)",                              "Mock", "Mock", "docker-compose.backend-only.yml"],
               ["Production",    "PostgreSQL (container, persistent volume)",   "Live", "Live", "docker-compose.prod.yml"],
           ],
           col_widths_cm=[3.0, 5.5, 2.8, 2.8, 4.4],
           caption_text="Environment Matrix")

    # ── CH 18: MONITORING AND LOGGING ─────────────────────────────────────────
    h1(doc, "Monitoring & Observability Architecture", num=18)
    h2(doc, "18.1 Observability Architecture & Metrics")
    body(doc, "The observability framework integrates Prometheus metric scraping (`/metrics`), Grafana dashboards, structured JSON logging, and OpenTelemetry-compatible tracing spans.")

    h2(doc, "18.2 Prometheus Metric Categories")
    ptable(doc,
           ["Category", "Key Metrics"],
           [
               ["HTTP",        "http_requests_total, http_failures_total, http_request_duration_seconds"],
               ["Security",    "security_logins_total, security_failed_logins_total, security_permission_denied_total, security_jwt_expired_total"],
               ["LLM",         "llm_requests_total, llm_success_total, llm_failure_total, llm_latency_seconds"],
               ["AI Agent",    "agent_execution_duration_seconds  [label: agent_name]"],
               ["Pipeline",    "pipeline_span_duration_seconds  [labels: service, provider, status]"],
               ["Database",    "db_connections_active"],
               ["SLA",         "sla_escalation_total, sla_breaches_total"],
               ["ServiceNow",  "servicenow_api_calls_total, servicenow_api_errors_total"],
           ],
           col_widths_cm=[3.5, 14.5],
           caption_text="Prometheus Metric Categories")

    h2(doc, "18.3 Background Jobs & APScheduler")
    ptable(doc,
           ["Job", "Schedule", "Responsibility"],
           [
               ["sla_monitor_job",  "Every 60 seconds",             "Evaluate open tickets against SLA thresholds; transition SLA state machine"],
               ["notification_job", "Every 30 seconds",             "Dispatch pending notifications to recipients"],
               ["auto_close_job",   "Every 60 seconds",             "Auto-close tickets in PENDING state beyond hold period"],
               ["cleanup_job",      "Daily at midnight (0 0 * * *)", "Purge expired sessions and stale temporary records"],
           ],
           col_widths_cm=[4.0, 4.5, 9.5],
           caption_text="APScheduler Background Jobs")

    # ── CH 19: TECHNOLOGY STACK ───────────────────────────────────────────────
    h1(doc, "Technology Stack", num=19)
    h2(doc, "19.1 Backend Stack")
    ptable(doc,
           ["Component", "Technology", "Version", "Justification"],
           [
               ["Runtime",          "Python",              "3.12",              "Latest stable; required by LangGraph and google-genai SDK"],
               ["API Framework",    "FastAPI + Uvicorn",   "0.115",             "Async-native, OpenAPI auto-documentation, Pydantic v2 integration"],
               ["AI Orchestration", "LangGraph StateGraph","Latest",            "Deterministic, testable AI pipeline control flow with conditional edges"],
               ["Primary AI",       "Google Gemini",       "gemini-2.5-flash",  "Large context window, function calling, developer free-tier access"],
               ["Fallback AI",      "Anthropic Claude",    "Claude 3 Sonnet",   "Independent provider for resilience against Gemini outages"],
               ["ORM",              "SQLAlchemy",          "2.x",               "Database-agnostic; SQLite and PostgreSQL parity"],
               ["Auth",             "PyJWT + bcrypt",      "—",                 "HS256 token issuance; bcrypt password hashing"],
               ["HTTP Client",      "requests",            "—",                 "Synchronous HTTP for ServiceNow REST API calls"],
               ["Scheduling",       "APScheduler",         "—",                 "In-process job scheduler with interval and cron triggers"],
               ["Metrics",          "prometheus-client",   "—",                 "Standard Prometheus Counter, Gauge, Histogram instrumentation"],
               ["Validation",       "Pydantic v2",         "—",                 "Schema enforcement on all AI outputs and API models"],
           ],
           col_widths_cm=[3.5, 3.8, 3.5, 7.2])

    h2(doc, "19.2 Frontend Stack")
    ptable(doc,
           ["Component", "Technology", "Version", "Justification"],
           [
               ["Framework", "Next.js",      "16.2",  "App Router, SSR, API route proxying to backend"],
               ["Runtime",   "React",        "19",    "Server Components, concurrent rendering"],
               ["Language",  "TypeScript",   "5",     "Type safety across all four portal surfaces"],
               ["Styling",   "Tailwind CSS", "4",     "Utility-first; design system consistency"],
               ["Animation", "Framer Motion","12",    "Micro-animations for portal interactions"],
               ["Charts",    "Recharts",     "3",     "Analytics dashboard visualisations"],
               ["Icons",     "Lucide React", "Latest","Consistent enterprise iconography"],
           ],
           col_widths_cm=[3.5, 3.8, 2.5, 8.2])

    h2(doc, "19.3 Infrastructure Stack")
    ptable(doc,
           ["Component", "Technology", "Justification"],
           [
               ["Reverse Proxy",      "Nginx stable-alpine","TLS termination, path-based routing, upstream proxy"],
               ["Database (prod)",    "PostgreSQL 14",      "ACID compliance, persistent volume, health check support"],
               ["Cache",              "Redis",              "Session cache and ServiceNow metadata cache (production)"],
               ["Containerisation",   "Docker + Compose",   "Environment-consistent deployment across dev, QA and production"],
               ["Metrics Collection", "Prometheus",         "Industry-standard scrape-based metrics"],
               ["Dashboards",         "Grafana",            "Prometheus datasource; provisioning-as-code via volume mounts"],
           ],
           col_widths_cm=[4.0, 4.5, 9.5])

    # ── CH 20: ARCHITECTURE DECISION RECORDS ──────────────────────────────────
    h1(doc, "Architecture Decision Records", num=20)
    body(doc, "Architecture Decision Records (ADRs) capture major architectural choices, design rationale, and accepted technical trade-offs.")

    adrs = [
        ("ADR-001", "LangGraph StateGraph for AI Pipeline Orchestration",
         "The AI pipeline requires conditional branching, state persistence across nodes and multi-step tool-execution loops.",
         "Use LangGraph StateGraph with typed AgentState TypedDict and conditional edge routing functions.",
         "Nodes are independently testable; routing logic is centralised in edge functions."),
        ("ADR-002", "Three-Tier AI Provider Fallback",
         "A single AI provider dependency creates a single point of failure.",
         "Implement BaseAIProvider abstraction: Gemini (primary) → Claude (fallback) → keyword-rules deterministic engine.",
         "Guarantees operational continuity during provider outages."),
        ("ADR-003", "Configuration-Driven ITSM Taxonomy",
         "ServiceNow field values change when the instance is reconfigured.",
         "All ITSM taxonomy externalised to incident_config.json, loaded at startup by ConfigurationService.",
         "Taxonomy changes require only JSON updates without Python code edits."),
        ("ADR-004", "In-Process Sliding-Window Rate Limiter",
         "External rate limiting dependencies add complexity for single-process setups.",
         "Implement pure-Python _SlidingWindowStore using threading.Lock and collections.deque.",
         "Zero external dependencies for single-instance deployments."),
        ("ADR-005", "Adapter Pattern with Mock/Live Toggle",
         "Enterprise integrations require live credentials unavailable in dev/CI.",
         "All integrations implement a BaseAdapter interface with mock toggles via env vars.",
         "Enables complete local offline pipeline testing."),
        ("ADR-006", "ServiceNow as Authoritative System of Record",
         "Without clear authority boundaries, ticket state could diverge.",
         "Every platform ticket carries servicenow_id and servicenow_number. ServiceNow is authoritative.",
         "All incidents remain fully traceable to a ServiceNow INC number."),
        ("ADR-007", "Append-Only Immutable Audit Log",
         "Enterprise compliance requires tamper-evident audit logs.",
         "ImmutableAuditLog exposes only record(). SHA-256 payload hashes stored alongside JSON payloads.",
         "Audit trail is non-repudiable under normal operation."),
        ("ADR-008", "Auto Schema Migration on Startup",
         "Maintaining Alembic migration chains adds friction during rapid POC iteration.",
         "On startup, inspect schema and add missing columns via ALTER TABLE idempotently.",
         "Zero-friction schema evolution during development phases."),
    ]

    for adr_id, adr_title, context, decision, consequences in adrs:
        h2(doc, f"{adr_id} — {adr_title}")
        ptable(doc,
               ["Field", "Content"],
               [
                   ["Status",       "Accepted"],
                   ["Context",      context],
                   ["Decision",     decision],
                   ["Consequences", consequences],
               ],
               col_widths_cm=[3.0, 15.0])

    # ── CH 21: ENGINEERING CHALLENGES ─────────────────────────────────────────
    h1(doc, "Engineering Challenges", num=21)
    challenges = [
        ("21.1 AI Non-Determinism at ITSM Boundaries",
         "LLM outputs are stochastic. Category values produced by AI may fail ServiceNow validation.",
         "Four-stage validation chain: AI output → FieldMappingService → MetadataValidator → IncidentEnrichmentService before submitting API payloads."),
        ("21.2 Multi-Step Troubleshooting Loop Termination",
         "Tool execution loops must terminate deterministically without token budget exhaustion.",
         "AgentState tracks troubleshooting_iterations and troubleshooting_complete flag, enforcing loop exit conditions."),
        ("21.3 Concurrent ServiceNow OAuth2 Token Refresh",
         "Multiple concurrent requests could trigger duplicate token refresh calls.",
         "ServiceNowClient uses a threading.RLock gating refresh calls with a 60-second safety buffer."),
        ("21.4 ServiceNow Metadata Cache Consistency",
         "Instance reconfiguration can render choice values stale.",
         "TTL-based cache with graceful fallback to incident_config.json on API downtime."),
        ("21.5 Approval Workflow State Race Conditions",
         "Concurrent manager approval and admin access grants could cause inconsistent state.",
         "Strict pre-condition state checks in ApprovalService with full audit trail logging."),
        ("21.6 Prompt Injection Without Over-Blocking",
         "Keyword guards risk blocking valid IT prompts containing words like 'system' or 'act'.",
         "Full-phrase anchored regex patterns in PromptGuard ensuring accurate classification."),
    ]
    for ch_title, challenge, resolution in challenges:
        h2(doc, ch_title)
        ptable(doc,
               ["", ""],
               [
                   ["Challenge",  challenge],
                   ["Resolution", resolution],
               ],
               col_widths_cm=[3.0, 15.0])

    # ── CH 22: FUTURE ROADMAP ─────────────────────────────────────────────────
    h1(doc, "Future Roadmap", num=22)
    h2(doc, "22.1 Near-Term (0–6 Months)")
    ptable(doc,
           ["Initiative", "Architectural Impact"],
           [
               ["Alembic Migration Chain",              "Replace auto-migration with versioned schema migrations"],
               ["Redis-Backed Rate Limiter",             "Replace in-process store with Redis to support multi-replica scaling"],
               ["Bi-Directional ServiceNow Sync",       "Webhook receiver for ServiceNow state alignment"],
               ["Entra ID Live Integration",            "Replace mock AD adapter with production MS Graph OAuth2 flow"],
               ["Knowledge Base Vector Search",          "Upgrade keyword retrieval to vector embeddings (pgvector)"],
           ],
           col_widths_cm=[6.0, 12.0])

    h2(doc, "22.2 Medium-Term (6–18 Months)")
    ptable(doc,
           ["Initiative", "Architectural Impact"],
           [
               ["Windows LAPS / CyberArk PAM",  "Replace mock credentials with live LAPS / PAM integration"],
               ["Kubernetes Deployment",          "Multi-replica deployment with Redis shared state"],
               ["OpenTelemetry Integration",      "Export traces to Jaeger, Datadog or Azure Monitor"],
               ["Multi-Model AI Routing",         "Route requests to domain-optimised AI models"],
           ],
           col_widths_cm=[6.0, 12.0])

    h2(doc, "22.3 Long-Term (18+ Months)")
    ptable(doc,
           ["Initiative", "Architectural Impact"],
           [
               ["Predictive SLA Management",  "ML breach risk prediction model"],
               ["Incident Pattern Clustering","Automated grouping of incidents into ServiceNow Problems"],
               ["Multi-Tenant Architecture",  "Isolated data and AI contexts for subsidiaries"],
           ],
           col_widths_cm=[6.0, 12.0])

    # ── CH 23: CONCLUSION ─────────────────────────────────────────────────────
    h1(doc, "Conclusion", num=23)
    body(doc, "The Bridgestone IT AI Assistant establishes a production-credible architecture combining AI reasoning with deterministic enterprise controls, minimal operational complexity, and complete compliance auditability.")

    # ── CH 24: APPENDIX ───────────────────────────────────────────────────────
    h1(doc, "Appendix", num=24)
    h2(doc, "24.1 ServiceNow Field Mapping Reference")
    ptable(doc,
           ["Platform Concept", "ServiceNow Field", "Resolution Method"],
           [
               ["Category",         "category",        "AI → FieldMappingService → MetadataValidator"],
               ["Subcategory",      "subcategory",     "AI → subcategory_map in incident_config.json"],
               ["Assignment Group", "assignment_group","assignment_group_map in incident_config.json"],
               ["CMDB CI",          "cmdb_ci",         "ci_map in incident_config.json"],
               ["Impact",           "impact",          "category_impact rules in incident_config.json"],
               ["Urgency",          "urgency",         "category_urgency rules in incident_config.json"],
               ["Priority",         "priority",        "Priority matrix derived from impact × urgency"],
               ["Contact Type",     "contact_type",    "Static: 'Virtual Agent'"],
               ["Caller",           "caller_id",       "Authenticated username from JWT"],
           ],
           col_widths_cm=[4.5, 4.5, 9.0],
           caption_text="ServiceNow Field Mapping Reference")

    h2(doc, "24.2 Environment Variables Reference")
    ptable(doc,
           ["Variable", "Default", "Description"],
           [
               ["SECRET_KEY",                             "dev default",              "JWT signing secret"],
               ["DATABASE_URL",                           "sqlite:///./bridgestone.db","SQLAlchemy connection string"],
               ["REDIS_URL",                              "redis://redis:6379/0",      "Redis connection (prod)"],
               ["GEMINI_API_KEY",                         "—",                         "Google Gemini API key"],
               ["ANTHROPIC_API_KEY",                      "—",                         "Anthropic Claude API key"],
               ["SERVICENOW_INSTANCE_URL",                "—",                         "ServiceNow instance base URL"],
               ["SERVICENOW_USERNAME",                    "—",                         "ServiceNow API username"],
               ["SERVICENOW_CLIENT_ID",                   "—",                         "OAuth2 client ID"],
               ["SERVICENOW_CLIENT_SECRET",               "—",                         "OAuth2 client secret"],
               ["SERVICENOW_AUTH_TYPE",                   "basic",                     "Auth mode: basic or oauth2"],
               ["SERVICENOW_METADATA_CACHE_TTL_SECONDS", "3600",                      "Metadata cache TTL"],
               ["USE_MOCK_SERVICENOW",                    "true",                      "Disable live ServiceNow calls"],
               ["USE_MOCK_GRAPH",                         "true",                      "Disable live MS Graph calls"],
               ["USE_MOCK_AD",                            "true",                      "Disable live Active Directory calls"],
               ["RATE_LIMIT_CHAT",                        "30",                        "Max chat requests per window"],
               ["RATE_LIMIT_CHAT_WINDOW",                 "60",                        "Chat rate limit window in seconds"],
               ["RATE_LIMIT_LOGIN",                        "10",                        "Max login attempts per window"],
               ["RATE_LIMIT_ENABLED",                     "true",                      "Enable rate limiting"],
               ["HSTS_ENABLED",                           "false",                     "Enable HSTS headers"],
               ["MAX_REQUEST_SIZE_KB",                    "512",                       "Max request body size in KB"],
           ],
           col_widths_cm=[6.0, 3.5, 8.5],
           caption_text="Environment Variables Reference")

    h2(doc, "24.3 LangGraph Node Inventory — All 23 Nodes")
    ptable(doc,
           ["#", "Node", "Source File", "Responsibility"],
           [
               ["1",  "router",              "router_node.py",              "Classify message as CHAT or TROUBLESHOOT"],
               ["2",  "conversation",        "conversation_node.py",        "Handle general conversational messages; end immediately"],
               ["3",  "memory",              "memory_node.py",              "Load conversation history and active context into state"],
               ["4",  "context_router",      "context_router_node.py",      "Route to appropriate pipeline based on conversation context"],
               ["5",  "intent",              "intent_node.py",              "Classify IT issue into a diagnostic category"],
               ["6",  "diagnostic_interview","diagnostic_interview_node.py","Conduct structured diagnostic questioning; short-circuit if questions pending"],
               ["7",  "planner",             "planner_node.py",             "Generate ordered tool execution plan"],
               ["8",  "knowledge",           "knowledge_node.py",           "Retrieve relevant KB articles and resolution precedents"],
               ["9",  "tool",                "tool_node.py",                "Execute selected enterprise tool (VPN, AD, network, printer)"],
               ["10", "multi_step",          "multi_step_node.py",          "Evaluate tool results; decide whether to loop or proceed to root cause"],
               ["11", "root_cause",          "root_cause_node.py",          "Synthesise root cause from tool chain results"],
               ["12", "reflection",          "reflection_node.py",          "Evaluate reasoning quality and flag low-confidence decisions"],
               ["13", "decision",            "decision_node.py",            "Choose terminal action: CREATE_TICKET, EXECUTE_ACTION, or ASK_MORE_INFO"],
               ["14", "approval",            "approval_node.py",            "Evaluate approval requirement; set approval_status"],
               ["15", "action",              "action_node.py",              "Execute approved enterprise action"],
               ["16", "ticket",              "ticket_node.py",              "Classify, enrich, validate, create ServiceNow incident"],
               ["17", "ticket_lifecycle",    "ticket_lifecycle_node.py",    "Drive ticket state machine transitions (shared path)"],
               ["18", "ticket_status",       "ticket_status_node.py",       "Return current ticket status to employee"],
               ["19", "service_request",     "service_request_node.py",     "Handle service catalogue requests"],
               ["20", "assignment",          "assignment_node.py",          "Assign ticket to appropriate team based on category"],
               ["21", "notification",        "notification_node.py",        "Dispatch notifications to assigned recipients"],
               ["22", "sla",                 "sla_node.py",                 "Initialise or update SLA tracking state"],
               ["23", "context_router",      "context_router_node.py",      "Shared entry into ticket_lifecycle from standalone context path"],
           ],
           col_widths_cm=[1.0, 3.8, 5.2, 8.0],
           caption_text="LangGraph Node Inventory — All 23 Nodes")

    h2(doc, "24.4 Database Model Inventory — All 19 Models")
    ptable(doc,
           ["#", "Model", "Table", "Domain"],
           [
               ["1",  "User",                "users",                  "Identity"],
               ["2",  "Session",             "sessions",               "Identity"],
               ["3",  "Ticket",              "tickets",                "ITSM Workflow"],
               ["4",  "ApprovalHistory",     "approval_history",       "ITSM Workflow"],
               ["5",  "ActionHistory",       "action_history",         "ITSM Workflow"],
               ["6",  "ServiceRequest",      "service_requests",       "ITSM Workflow"],
               ["7",  "ServiceCatalog",      "service_catalog",        "ITSM Workflow"],
               ["8",  "Conversation",        "conversations",          "AI Pipeline"],
               ["9",  "ConversationEvent",   "conversation_events",    "AI Pipeline"],
               ["10", "AgentTrace",          "agent_traces",           "AI Pipeline"],
               ["11", "AuditLog",            "audit_logs",             "Compliance"],
               ["12", "RbacAuditLog",        "rbac_audit_logs",        "Compliance"],
               ["13", "SecurityEvent",       "security_events",        "Compliance"],
               ["14", "SlaAuditEvent",       "sla_audit_events",       "SLA"],
               ["15", "SlaEscalationHistory","sla_escalation_history", "SLA"],
               ["16", "Notification",        "notifications",          "Operations"],
               ["17", "ScheduledJob",        "scheduled_jobs",         "Operations"],
               ["18", "KnowledgeDraft",      "knowledge_drafts",       "Knowledge"],
               ["19", "IncidentCluster",     "incident_clusters",      "Analytics"],
           ],
           col_widths_cm=[1.0, 4.5, 5.5, 3.5],
           caption_text="Database Model Inventory — All 19 Models")

    # ── END MATTER ────────────────────────────────────────────────────────────
    hr(doc)
    end1 = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=8, space_after=2)
    _run(end1, "End of Document — BST-ESAD-2026-001 v1.0.0", italic=True, size=9, color=C_MID_GREY)

    end2 = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=2)
    _run(end2, "Bridgestone IT Engineering — Platform Engineering — AI & Automation", italic=True, size=9, color=C_MID_GREY)

    end3 = _new_para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=0)
    _run(end3, "This document is intended for internal engineering review. Distribution restricted to engineering leadership, principal engineers and enterprise architects.",
         italic=True, size=8.5, color="AAAAAA")

    apply_header_footer(doc)
    doc.save(DOCX_OUTPUT)
    print(f"\n[OK] Word document saved successfully: {DOCX_OUTPUT}")
    sz = os.path.getsize(DOCX_OUTPUT)
    print(f"   Size: {sz:,} bytes ({sz/1024:.1f} KB)")

    # Attempt PDF conversion using win32com
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc_obj = word.Documents.Open(os.path.abspath(DOCX_OUTPUT))
        doc_obj.SaveAs(os.path.abspath(PDF_OUTPUT), FileFormat=17)
        doc_obj.Close()
        word.Quit()
        print(f"[OK] PDF document saved successfully: {PDF_OUTPUT}")
        pdf_sz = os.path.getsize(PDF_OUTPUT)
        print(f"   Size: {pdf_sz:,} bytes ({pdf_sz/1024:.1f} KB)")
    except Exception as e:
        print(f"[INFO] PDF export via Word COM encountered: {e}")
        print("   Word document (.docx) is fully formatted and complete.")

if __name__ == "__main__":
    build_esad_doc()
