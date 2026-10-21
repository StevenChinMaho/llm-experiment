#!/usr/bin/env python3
"""把 report/midterm/*.md 轉成期中計畫書 Word 檔（docs/report-spec.md 的規格）。

- 中文標楷體、英文與符號 Times New Roman（東亞字型用 w:eastAsia 設定）；邊界上下左右 1.2 cm
- 封面 → 目錄（TOC 欄位，由 scripts/count_pages.ps1 用 Word 更新）→ 正文；頁尾頁碼
- 「二、」「二、2.」「三、」前強制換頁，讓研究方法的頁數可以精確計算
- 支援的 Markdown：# ## ### 標題、段落、**粗體**、*斜體*、`程式碼`、> 引用、- 與 1. 清單、表格、![圖說](路徑)、HTML 註解（略過）

用法：python scripts/build_midterm_docx.py [--out report/midterm/build/midterm.docx] [--size 12] [--spacing 1.15]
       [--name 姓名] [--sid 學號] [--course 課程] [--teacher 老師]
"""
import argparse
import os
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MD_DIR = os.path.join(ROOT, "report", "midterm")
FILES = ["01-background.md", "02-literature.md", "03a-methods-setup.md", "03b-methods-memory-speed.md",
         "03c-methods-quality-tasks.md", "04-difficulties.md", "05-outcomes.md"]
EA_FONT, LATIN_FONT = "標楷體", "Times New Roman"


def set_font(run, size=None, bold=None, italic=None, mono=False):
    run.font.name = "Consolas" if mono else LATIN_FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts"); rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), EA_FONT)
    rfonts.set(qn("w:ascii"), "Consolas" if mono else LATIN_FONT)
    rfonts.set(qn("w:hAnsi"), "Consolas" if mono else LATIN_FONT)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)


def add_inline(par, text, size, bold=False):
    """處理 **粗體**、*斜體*、`程式碼`。"""
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**"):
            set_font(par.add_run(tok[2:-2]), size, bold=True)
        elif tok.startswith("`"):
            set_font(par.add_run(tok[1:-1]), size * 0.9, bold=bold, mono=True)
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            set_font(par.add_run(tok[1:-1]), size, bold=bold, italic=True)
        else:
            set_font(par.add_run(tok), size, bold=bold)


def para_format(par, a, indent_first=True, space_after=3, align=None):
    pf = par.paragraph_format
    pf.line_spacing = a.spacing
    pf.space_before = Pt(0)
    pf.space_after = Pt(space_after)
    if indent_first:
        pf.first_line_indent = Pt(a.size * 2)
    if align is not None:
        par.alignment = align


def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def add_field(par, instr, size):
    """插入 Word 欄位（目錄、頁碼）。"""
    run = par.add_run(); set_font(run, size)
    for tag, attr in (("w:fldChar", "begin"), ("w:instrText", instr), ("w:fldChar", "separate")):
        el = OxmlElement(tag)
        if tag == "w:fldChar":
            el.set(qn("w:fldCharType"), attr)
        else:
            el.set(qn("xml:space"), "preserve"); el.text = attr
        run._r.append(el)
    t = par.add_run("（請在 Word 中更新欄位）" if "TOC" in instr else "1"); set_font(t, size)
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    par.add_run()._r.append(end)


def heading(doc, text, level, a):
    sizes = {1: a.size + 4, 2: a.size + 2, 3: a.size + 0.5}
    par = doc.add_paragraph(style=f"Heading {level}")
    add_inline(par, text, sizes[level], bold=True)
    pf = par.paragraph_format
    pf.space_before = Pt(8 if level < 3 else 6); pf.space_after = Pt(4); pf.line_spacing = a.spacing
    pf.keep_with_next = True


def table(doc, rows, a):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    ncol = max(len(r) for r in cells)
    t = doc.add_table(rows=len(cells), cols=ncol)
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, r in enumerate(cells):
        for j in range(ncol):
            cell = t.cell(i, j)
            cell.paragraphs[0].text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.0; p.paragraph_format.space_after = Pt(0)
            add_inline(p, r[j] if j < len(r) else "", a.size - 1.5, bold=(i == 0))
            if i == 0:
                sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), "E7E6E3")
                cell._tc.get_or_add_tcPr().append(sh)
    for ri, row in enumerate(t.rows):
        trpr = row._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit"); trpr.append(cs)
        if ri < len(t.rows) - 1:
            for c in row.cells:
                c.paragraphs[0].paragraph_format.keep_with_next = True
    sp = doc.add_paragraph(); sp.paragraph_format.space_after = Pt(0); sp.paragraph_format.line_spacing = 0.8


def image(doc, caption, path, a):
    full = os.path.normpath(os.path.join(MD_DIR, path))
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True; p.paragraph_format.space_after = Pt(0)
    width = Cm(13.5) if "architecture" in path else Cm(17.5)
    p.add_run().add_picture(full, width=width)
    c = doc.add_paragraph(); add_inline(c, caption, a.size - 1, bold=True)
    para_format(c, a, indent_first=False, space_after=6, align=WD_ALIGN_PARAGRAPH.CENTER)


def convert(doc, md, a):
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1; continue
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i]); i += 1
            table(doc, block, a); continue
        m = re.match(r"^(#{1,3}) (.*)", line)
        if m:
            level, text = len(m.group(1)), m.group(2)
            if (level == 1 and text.startswith("二、")) or (level == 2 and text.startswith("2. 預計")):
                page_break(doc)
            heading(doc, text, level, a); i += 1; continue
        m = re.match(r"^!\[(.*)\]\((.*)\)$", line)
        if m:
            image(doc, m.group(1), m.group(2), a); i += 1; continue
        if re.fullmatch(r"\*\*(表|圖) [^*]+\*\*", line):          # 表格標題
            c = doc.add_paragraph(); add_inline(c, line, a.size - 1)
            para_format(c, a, indent_first=False, space_after=2, align=WD_ALIGN_PARAGRAPH.CENTER)
            c.paragraph_format.keep_with_next = True
            i += 1; continue
        if line.startswith("> "):
            p = doc.add_paragraph(); add_inline(p, line[2:], a.size)
            para_format(p, a, indent_first=False); p.paragraph_format.left_indent = Cm(1)
            i += 1; continue
        m = re.match(r"^(\s*)(- |\d+\. )(.*)", line)
        if m:
            p = doc.add_paragraph()
            prefix = "• " if m.group(2) == "- " else m.group(2)
            add_inline(p, prefix + m.group(3), a.size)
            para_format(p, a, indent_first=False, space_after=1)
            p.paragraph_format.left_indent = Cm(0.9 + 0.6 * (len(m.group(1)) // 2))
            p.paragraph_format.first_line_indent = Cm(-0.6)
            i += 1; continue
        if re.match(r"^\[\d+\] ", line):                          # 參考文獻條目：懸掛縮排
            p = doc.add_paragraph(); add_inline(p, line, a.size - 1)
            para_format(p, a, indent_first=False, space_after=1)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.left_indent = Cm(0.9); p.paragraph_format.first_line_indent = Cm(-0.9)
            i += 1; continue
        p = doc.add_paragraph(); add_inline(p, line, a.size)
        para_format(p, a, align=WD_ALIGN_PARAGRAPH.JUSTIFY)
        i += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(MD_DIR, "build", "midterm.docx"))
    ap.add_argument("--size", type=float, default=12)
    ap.add_argument("--spacing", type=float, default=1.5)
    ap.add_argument("--title", default="消費級 GPU 上本地大型語言模型之推論速度、記憶體與品質權衡分析")
    ap.add_argument("--name", default="姓名")
    ap.add_argument("--sid", default="學號")
    ap.add_argument("--course", default="人工智慧")
    ap.add_argument("--teacher", default="（授課教師）")
    ap.add_argument("--date", default="2026 年 11 月")
    a = ap.parse_args()

    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    for side in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(sec, side, Cm(1.2))
    sec.footer_distance = Cm(0.5); sec.header_distance = Cm(0.5)
    for name in ("Normal", "Heading 1", "Heading 2", "Heading 3"):
        st = doc.styles[name]
        st.font.name = LATIN_FONT; st.font.color.rgb = RGBColor(0, 0, 0)
        rpr = st.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts"); rpr.append(rf)
        for k in ("w:eastAsia",):
            rf.set(qn(k), EA_FONT)
        rf.set(qn("w:ascii"), LATIN_FONT); rf.set(qn("w:hAnsi"), LATIN_FONT)
    doc.styles["Normal"].font.size = Pt(a.size)

    # 封面
    for _ in range(8):
        doc.add_paragraph()
    p = doc.add_paragraph(); add_inline(p, "人工智慧　期中研究計畫書（Project Proposal）", a.size + 4, bold=True)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()
    p = doc.add_paragraph(); add_inline(p, a.title, a.size + 8, bold=True); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.3
    for _ in range(6):
        doc.add_paragraph()
    for label, val in (("課程", a.course), ("授課教師", a.teacher), ("學生", f"{a.name}　{a.sid}"), ("日期", a.date)):
        p = doc.add_paragraph(); add_inline(p, f"{label}：{val}", a.size + 2); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    page_break(doc)

    # 目錄
    p = doc.add_paragraph(); add_inline(p, "目錄", a.size + 4, bold=True); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(doc.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u', a.size)
    page_break(doc)

    for f in FILES:
        convert(doc, open(os.path.join(MD_DIR, f), encoding="utf-8").read(), a)

    # 頁尾頁碼（封面也算在 25 頁內，所以從 1 開始連續編號）
    fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(fp, "PAGE", a.size - 2)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    doc.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
