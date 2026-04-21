# -*- coding: utf-8 -*-
"""Generate HABITUS_MANUAL_EN.pdf from HABITUS_MANUAL_EN.md using reportlab."""

import re, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Preformatted, HRFlowable, PageBreak)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

SRC  = "D:/claude_project/habitus/HABITUS_MANUAL_EN.md"
DEST = "D:/claude_project/habitus/HABITUS_MANUAL_EN.pdf"

src = open(SRC, encoding="utf-8").read()

doc = SimpleDocTemplate(
    DEST, pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm,
    topMargin=2.5*cm, bottomMargin=2.5*cm,
    title="HABITUS v1.0.0 — Developer & User Manual",
    author="Anonymous",
)

ss = getSampleStyleSheet()

S = dict(
    h1=ParagraphStyle('h1', fontSize=17, textColor=colors.HexColor('#1d5235'),
                      spaceAfter=6, spaceBefore=14, leading=20, fontName='Helvetica-Bold'),
    h2=ParagraphStyle('h2', fontSize=12, textColor=colors.HexColor('#1d5235'),
                      spaceAfter=4, spaceBefore=10, leading=15, fontName='Helvetica-Bold'),
    h3=ParagraphStyle('h3', fontSize=10.5, textColor=colors.HexColor('#2a6a48'),
                      spaceAfter=3, spaceBefore=7, fontName='Helvetica-Bold'),
    h4=ParagraphStyle('h4', fontSize=9.5, textColor=colors.HexColor('#1c3328'),
                      spaceAfter=2, spaceBefore=5, fontName='Helvetica-Bold'),
    body=ParagraphStyle('body', fontSize=9, leading=13, spaceAfter=3,
                        textColor=colors.HexColor('#1c3328')),
    bullet=ParagraphStyle('bullet', fontSize=9, leading=13, leftIndent=14,
                           spaceAfter=2, textColor=colors.HexColor('#1c3328')),
    bq=ParagraphStyle('bq', fontSize=8.5, leading=12, leftIndent=12,
                       textColor=colors.HexColor('#2a5c40'),
                       backColor=colors.HexColor('#eef7f2'), spaceAfter=4),
    code=ParagraphStyle('code', fontName='Courier', fontSize=7.5, leading=10,
                         backColor=colors.HexColor('#e8f5ed'),
                         textColor=colors.HexColor('#1a3d2a'),
                         leftIndent=8, rightIndent=8, spaceBefore=4, spaceAfter=4),
    tc=ParagraphStyle('tc', fontSize=8, leading=10, textColor=colors.HexColor('#1c3328')),
    tc_hdr=ParagraphStyle('tc_hdr', fontSize=8, leading=10,
                           textColor=colors.HexColor('#1d5235'), fontName='Helvetica-Bold'),
    cover_title=ParagraphStyle('ct', fontSize=28, textColor=colors.HexColor('#1d5235'),
                                alignment=TA_CENTER, spaceAfter=6, leading=32,
                                fontName='Helvetica-Bold'),
    cover_sub=ParagraphStyle('cs', fontSize=11, textColor=colors.HexColor('#3a8c60'),
                              alignment=TA_CENTER, spaceAfter=4, leading=14),
    cover_meta=ParagraphStyle('cm', fontSize=9, textColor=colors.HexColor('#4a6858'),
                               alignment=TA_CENTER, spaceAfter=3),
    doi=ParagraphStyle('doi', fontSize=8, textColor=colors.HexColor('#4a6858'),
                        alignment=TA_CENTER),
)

def clean(t):
    # escape first
    t = t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # bold / italic / code
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', t)
    t = re.sub(r'`(.+?)`',
               r'<font name="Courier" size="8" color="#1a3d2a">\1</font>', t)
    # links → text only
    t = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', t)
    return t

story = []

# ── Cover ──────────────────────────────────────────────────────────────────
story.append(Spacer(1, 3*cm))
story.append(Paragraph("HABITUS", S['cover_title']))
story.append(Paragraph("v1.0.0",
    ParagraphStyle('ver', fontSize=16, textColor=colors.HexColor('#3a8c60'),
                   alignment=TA_CENTER, spaceAfter=10)))
story.append(Paragraph(
    "Habitat Analysis and Biodiversity Integrated Toolkit<br/>"
    "for Unified Species Distribution Modelling", S['cover_sub']))
story.append(Spacer(1, 0.8*cm))
story.append(HRFlowable(width="80%", thickness=1.5,
                         color=colors.HexColor('#b8d4c4'), hAlign='CENTER'))
story.append(Spacer(1, 0.8*cm))
story.append(Paragraph("Developer &amp; User Manual", S['cover_meta']))
story.append(Spacer(1, 0.4*cm))
story.append(Paragraph("[Authors removed for peer review]", S['cover_meta']))
story.append(Paragraph("[Institution removed for peer review]", S['cover_meta']))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph("April 2026", S['cover_meta']))
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph("[DOI removed for peer review]", S['doi']))
story.append(PageBreak())

# ── Parse markdown ─────────────────────────────────────────────────────────
lines = src.split('\n')
i = 0
in_code = False
code_buf = []
table_rows = []

def flush_table():
    if not table_rows:
        return
    col_count = max(len(r) for r in table_rows)
    padded = []
    for ri, row in enumerate(table_rows):
        while len(row) < col_count:
            row.append('')
        sty = S['tc_hdr'] if ri == 0 else S['tc']
        padded.append([Paragraph(clean(c), sty) for c in row])
    col_w = (A4[0] - 4*cm) / col_count
    t = Table(padded, colWidths=[col_w]*col_count, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#d4ead9')),
        ('GRID', (0,0), (-1,-1), 0.4, colors.HexColor('#b8d4c4')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1),
         [colors.white, colors.HexColor('#eef7f2')]),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 5))
    table_rows.clear()

while i < len(lines):
    line = lines[i]

    # code block toggle
    if line.startswith('```'):
        if not in_code:
            in_code = True
            code_buf = []
        else:
            in_code = False
            story.append(Preformatted('\n'.join(code_buf), S['code']))
        i += 1
        continue
    if in_code:
        code_buf.append(line)
        i += 1
        continue

    # table row
    if line.startswith('|'):
        cells = [c.strip() for c in line.strip('|').split('|')]
        if all(re.match(r'^[-: ]+$', c) for c in cells if c):
            i += 1
            continue
        table_rows.append(cells)
        i += 1
        if i >= len(lines) or not lines[i].startswith('|'):
            flush_table()
        continue
    else:
        flush_table()

    stripped = line.strip()

    if not stripped:
        story.append(Spacer(1, 3))
    elif line.startswith('# ') and not line.startswith('## '):
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=1,
                                 color=colors.HexColor('#b8d4c4')))
        story.append(Paragraph(clean(line[2:]), S['h1']))
    elif line.startswith('## '):
        story.append(Paragraph(clean(line[3:]), S['h2']))
        story.append(HRFlowable(width="100%", thickness=0.4,
                                 color=colors.HexColor('#d4ead9')))
    elif line.startswith('### '):
        story.append(Paragraph(clean(line[4:]), S['h3']))
    elif line.startswith('#### '):
        story.append(Paragraph(clean(line[5:]), S['h4']))
    elif stripped.startswith('---'):
        story.append(HRFlowable(width="100%", thickness=0.5,
                                 color=colors.HexColor('#c4ddd0')))
        story.append(Spacer(1, 2))
    elif line.startswith('- ') or line.startswith('* '):
        story.append(Paragraph('• ' + clean(line[2:]), S['bullet']))
    elif re.match(r'^\d+\. ', line):
        m = re.match(r'^(\d+)\. (.*)', line)
        story.append(Paragraph(m.group(1) + '. ' + clean(m.group(2)), S['bullet']))
    elif stripped.startswith('> '):
        story.append(Paragraph(clean(stripped[2:]), S['bq']))
    else:
        story.append(Paragraph(clean(stripped), S['body']))

    i += 1

flush_table()

doc.build(story)
size = os.path.getsize(DEST)
print(f"PDF saved: {DEST}")
print(f"Size: {size/1024/1024:.1f} MB")
