"""Сборка пояснительной записки (.docx) по ГОСТ 2.105 и методическим указаниям.

    python docs/build_report.py            # сборка docx + pdf (нужен LibreOffice)
    python docs/build_report.py --no-pdf   # только docx (содержание без номеров страниц)

Текст разделов хранится в docs/sections/*.md в простой разметке:
    #* ЗАГОЛОВОК           — структурный элемент (по центру, с новой страницы)
    # 1 Заголовок          — раздел (с новой страницы); ## 1.1, ### 1.1.1 — подразделы
    #A А | обязательное | Название   — приложение
    - текст                — элемент перечисления (с тире)
    !fig id | путь | ширина_см | Название
    !table id | Название | gen:имя       — таблица из результатов экспериментов
    !table id | Название | ширины_см      — таблица из строк «| a | b |» ниже
    !listing id | Название | файл | def:имя / class:Имя.метод / lines:a-b
    !eq id | имя_формулы (docs/formulas.py)
    !placeholder текст     — заглушка (например, для скриншота)
    !pagebreak
В тексте: **жирный**, *курсив*, [@ключ] — ссылка на источник,
{fig:id} {tab:id} {lst:id} {eq:id} — номера рисунков, таблиц, листингов, формул,
{{имя}} — значение из результатов экспериментов.

Сборка двухпроходная: после первого прохода docx конвертируется в PDF,
по PDF определяются номера страниц заголовков и общее число страниц, затем
документ собирается повторно с заполненным содержанием и рефератом.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SECTIONS = DOCS / "sections"
RES = ROOT / "experiments" / "results"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(DOCS))

from docx import Document  # noqa: E402
from docx.enum.section import WD_SECTION  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_TAB_LEADER  # noqa: E402
from docx.oxml import OxmlElement, parse_xml  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

import formulas  # noqa: E402
from sources import SOURCES  # noqa: E402
import tables  # noqa: E402

FONT = "Times New Roman"
MONO = "Courier New"
TEXT_WIDTH_CM = 21.0 - 3.0 - 1.5
OUT_DOCX = DOCS / "Пояснительная_записка.docx"
OUT_PDF = DOCS / "Пояснительная_записка.pdf"
NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

SECTION_FILES = ["00_introduction.md", "01_normative.md", "02_terms.md", "1_analysis.md",
                 "2_methods.md", "3_system.md", "4_experiments.md", "9_conclusion.md"]
APPENDIX_FILE = "a_appendices.md"


# ============================================================== вспомогательное
def set_cell_margins(cell, top=40, bottom=40, left=80, right=80):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for k, v in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        el = OxmlElement(f"w:{k}")
        el.set(qn("w:w"), str(v))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def set_table_borders(table, size=4):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)


def set_col_widths(table, widths_cm):
    """Фиксированные ширины столбцов (tblGrid + ширина каждой ячейки + tblW),
    иначе LibreOffice сжимает таблицу."""
    tbl = table._tbl
    tblPr = tbl.tblPr
    total = sum(widths_cm)
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:w"), str(int(total * 567)))
    tblW.set(qn("w:type"), "dxa")
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    grid = tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths_cm):
        gc.set(qn("w:w"), str(int(w * 567)))
    for row in table.rows:
        for c, w in zip(row.cells, widths_cm):
            c.width = Cm(w)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def add_field(paragraph, instr: str, placeholder: str = ""):
    """Вставляет поле Word (PAGE, NUMPAGES и т.п.)."""
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    run._r.append(b)
    run = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    run._r.append(it)
    run = paragraph.add_run()
    s = OxmlElement("w:fldChar")
    s.set(qn("w:fldCharType"), "separate")
    run._r.append(s)
    paragraph.add_run(placeholder)
    run = paragraph.add_run()
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    run._r.append(e)


def fmt_num(x, nd=1):
    s = f"{x:.{nd}f}"
    return s.replace(".", ",")


# ================================================================ сборщик
class ReportBuilder:
    def __init__(self, toc_pages: dict | None = None, stats: dict | None = None):
        self.toc_pages = toc_pages or {}
        self.stats = stats or {}
        self.doc = Document()
        self.headings: list[tuple[int, str]] = []    # (уровень, текст) для содержания
        self.counters = {"fig": 0, "tab": 0, "lst": 0, "eq": 0}
        self.labels: dict[str, int] = {}
        self.cited: list[str] = []
        self.values = tables.load_values()
        self._setup()

    # ---------------------------------------------------------------- стили
    def _setup(self):
        d = self.doc
        sec = d.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin, sec.right_margin = Cm(3.0), Cm(1.5)
        sec.top_margin, sec.bottom_margin = Cm(1.5), Cm(2.5)
        sec.footer_distance = Cm(1.2)
        sec.different_first_page_header_footer = True
        p = sec.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        add_field(p, "PAGE", "1")

        st = d.styles["Normal"]
        st.font.name = FONT
        st.font.size = Pt(14)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        pf = st.paragraph_format
        pf.first_line_indent = Cm(1.25)
        pf.line_spacing = 1.5
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.widow_control = True
        for lvl, size in ((1, 14), (2, 14), (3, 14)):
            hs = d.styles[f"Heading {lvl}"]
            hs.font.name = FONT
            hs.font.size = Pt(size)
            hs.font.bold = True
            hs.font.italic = False
            hs.font.color.rgb = RGBColor(0, 0, 0)
            rpr = hs.element.get_or_add_rPr()
            rf = rpr.find(qn("w:rFonts"))
            if rf is None:
                rf = OxmlElement("w:rFonts")
                rpr.append(rf)
            for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                rf.set(qn(a), FONT)
            for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                if rf.get(qn(a)) is not None:
                    del rf.attrib[qn(a)]
            hpf = hs.paragraph_format
            hpf.first_line_indent = Cm(1.25)
            hpf.left_indent = Cm(0)
            hpf.line_spacing = 1.5
            hpf.space_before = Pt(0 if lvl == 1 else 12)
            hpf.space_after = Pt(12 if lvl == 1 else 6)
            hpf.keep_with_next = True
            hpf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        # обновление полей (содержания) при открытии в Word
        settings = d.settings.element
        uf = OxmlElement("w:updateFields")
        uf.set(qn("w:val"), "true")
        settings.append(uf)
        # язык документа — русский (переносы, проверка орфографии)
        lang = OxmlElement("w:lang")
        lang.set(qn("w:val"), "ru-RU")
        lang.set(qn("w:eastAsia"), "ru-RU")
        st.element.get_or_add_rPr().append(lang)

    # --------------------------------------------------------------- абзацы
    def para(self, text: str = "", align=None, indent: float | None = None, bold=False,
             size: float | None = None, spacing: float | None = None, keep_next=False,
             italic=False, space_after: float | None = None, space_before: float | None = None):
        p = self.doc.add_paragraph()
        if align is not None:
            p.alignment = align
        if indent is not None:
            p.paragraph_format.first_line_indent = Cm(indent)
        if spacing is not None:
            p.paragraph_format.line_spacing = spacing
        if space_after is not None:
            p.paragraph_format.space_after = Pt(space_after)
        if space_before is not None:
            p.paragraph_format.space_before = Pt(space_before)
        if keep_next:
            p.paragraph_format.keep_with_next = True
        if text:
            self.inline(p, text, bold=bold, size=size, italic=italic)
        return p

    def inline(self, p, text: str, bold=False, size=None, italic=False):
        """Добавляет текст с разметкой **жирный**, *курсив* и подстановками."""
        text = self.resolve(text)
        for part in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)", text):
            if not part:
                continue
            b, it = bold, italic
            if part.startswith("**"):
                part, b = part[2:-2], True
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                part, it = part[1:-1], True
            # нижние и верхние индексы: x_{ij}, x^{2}
            for piece in re.split(r"(_\{[^}]*\}|\^\{[^}]*\})", part):
                if not piece:
                    continue
                pos = None
                if piece.startswith("_{"):
                    piece, pos = piece[2:-1], "sub"
                elif piece.startswith("^{"):
                    piece, pos = piece[2:-1], "sup"
                run = p.add_run(piece)
                run.bold = b
                run.italic = it
                if pos == "sub":
                    run.font.subscript = True
                elif pos == "sup":
                    run.font.superscript = True
                if size:
                    run.font.size = Pt(size)
        return p

    def resolve(self, text: str) -> str:
        """Подстановка ссылок на источники, номеров объектов и значений."""
        def cite(m):
            keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
            nums = []
            for k in keys:
                page = ""
                if "," in k:
                    k, page = [x.strip() for x in k.split(",", 1)]
                if k not in SOURCES:
                    raise KeyError(f"Неизвестный источник: {k}")
                if k not in self.cited:
                    self.cited.append(k)
                nums.append(f"{self.cited.index(k) + 1}{', ' + page if page else ''}")
            return "[" + "; ".join(nums) + "]" if any("," in n for n in nums) else \
                "[" + ", ".join(nums) + "]"
        text = re.sub(r"\[(@[^\]]+)\]", cite, text)
        text = re.sub(r"\{\{(\w+)\}\}", lambda m: str(self.values[m.group(1)]), text)

        def ref(m):
            key = f"{m.group(1)}:{m.group(2)}"
            if key not in self.labels:
                raise KeyError(f"Неизвестная ссылка {key}")
            return str(self.labels[key])
        return re.sub(r"\{(fig|tab|lst|eq):([\w\-]+)\}", ref, text)

    # ------------------------------------------------------------ заголовки
    def page_break(self):
        p = self.doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0)
        p.add_run().add_break(WD_BREAK.PAGE)

    def heading(self, text: str, level: int, structural=False, toc=True, new_page=None):
        if new_page is None:
            new_page = level == 1
        h = self.doc.add_heading(level=level)
        h.paragraph_format.page_break_before = new_page
        if structural:
            h.alignment = WD_ALIGN_PARAGRAPH.CENTER
            h.paragraph_format.first_line_indent = Cm(0)
        h.add_run(text)
        if toc:
            self.headings.append((level, text))
        return h

    # --------------------------------------------------------------- объекты
    def number(self, kind: str, label: str) -> int:
        self.counters[kind] += 1
        self.labels[f"{kind}:{label}"] = self.counters[kind]
        return self.counters[kind]

    def figure(self, label, path, width_cm, caption):
        n = self.labels[f"fig:{label}"]
        p = self.para(align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, keep_next=True, spacing=1.0,
                      space_before=6)
        p.add_run().add_picture(str(ROOT / path), width=Cm(float(width_cm)))
        self.para(f"Рисунок {n} – {caption}", align=WD_ALIGN_PARAGRAPH.CENTER, indent=0,
                  space_after=6)

    def table(self, label, caption, header, rows, widths=None, font=12, align=None):
        n = self.labels[f"tab:{label}"]
        self.para(f"Таблица {n} – {caption}", align=WD_ALIGN_PARAGRAPH.LEFT, indent=0,
                  keep_next=True, space_before=6)
        ncol = len(header)
        tb = self.doc.add_table(rows=1, cols=ncol)
        tb.alignment = WD_TABLE_ALIGNMENT.CENTER
        tb.autofit = False
        set_table_borders(tb)
        if widths is None:
            widths = [TEXT_WIDTH_CM / ncol] * ncol
        scale = TEXT_WIDTH_CM / sum(widths)
        widths = [w * scale for w in widths]
        all_rows = [header] + rows
        for i, row in enumerate(all_rows):
            cells = tb.rows[0].cells if i == 0 else tb.add_row().cells
            for j, val in enumerate(row):
                c = cells[j]
                c.width = Cm(widths[j])
                set_cell_margins(c)
                p = c.paragraphs[0]
                p.paragraph_format.first_line_indent = Cm(0)
                p.paragraph_format.line_spacing = 1.0
                if i == 0:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    a = (align[j] if align else "l")
                    p.alignment = {"l": WD_ALIGN_PARAGRAPH.LEFT, "c": WD_ALIGN_PARAGRAPH.CENTER,
                                   "r": WD_ALIGN_PARAGRAPH.RIGHT}[a]
                self.inline(p, str(val), bold=(i == 0), size=font)
        repeat_header(tb.rows[0])
        set_col_widths(tb, widths)
        # пустой абзац после таблицы
        self.para("", spacing=1.0)

    def deflist(self, rows, widths):
        """Перечень терминов: два столбца без рамок и без подписи."""
        tb = self.doc.add_table(rows=0, cols=2)
        tb.autofit = False
        scale = TEXT_WIDTH_CM / sum(widths)
        for term, definition in rows:
            cells = tb.add_row().cells
            for j, val in enumerate((term, definition)):
                c = cells[j]
                c.width = Cm(widths[j] * scale)
                p = c.paragraphs[0]
                p.paragraph_format.first_line_indent = Cm(0)
                p.paragraph_format.line_spacing = 1.5
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.JUSTIFY
                self.inline(p, ("" if j == 0 else "– ") + val)
        set_col_widths(tb, [w * scale for w in widths])

    def listing(self, label, caption, code: str, size=10):
        n = self.labels[f"lst:{label}"]
        self.para(f"Листинг {n} – {caption}", align=WD_ALIGN_PARAGRAPH.LEFT, indent=0,
                  keep_next=True, space_before=6)
        self.code_block(code, size)
        self.para("", spacing=1.0)

    def code_block(self, code: str, size=10):
        tb = self.doc.add_table(rows=1, cols=1)
        set_table_borders(tb)
        cell = tb.rows[0].cells[0]
        cell.width = Cm(TEXT_WIDTH_CM)
        set_cell_margins(cell, 60, 60, 120, 60)
        lines = code.rstrip("\n").split("\n")
        first = True
        for line in lines:
            p = cell.paragraphs[0] if first else cell.add_paragraph()
            first = False
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf = p.paragraph_format
            pf.first_line_indent = Cm(0)
            pf.line_spacing = 1.0
            run = p.add_run(line if line else " ")
            run.font.name = MONO
            run.font.size = Pt(size)
            run._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), MONO)
        set_col_widths(tb, [TEXT_WIDTH_CM])

    def equation(self, label, name):
        n = self.labels[f"eq:{label}"]
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.first_line_indent = Cm(0)
        pf.space_before = Pt(6)
        pf.space_after = Pt(6)
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM / 2), WD_TAB_ALIGNMENT.CENTER)
        pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
        p.add_run("\t")
        xml = (f'<m:oMath xmlns:m="{NS_M}" xmlns:w="{NS_W}">'
               f'{formulas.FORMULAS[name]()}</m:oMath>')
        p._p.append(parse_xml(xml))
        p.add_run(f"\t({n})")

    def placeholder(self, text):
        p = self.para(align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, space_before=6, space_after=6)
        r = p.add_run(f"[{text}]")
        r.bold = True
        r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    # ----------------------------------------------------------- разметка
    def prescan(self, files):
        """Первый просмотр: нумерация рисунков, таблиц, листингов, формул."""
        for f in files:
            for line in (SECTIONS / f).read_text(encoding="utf-8").splitlines():
                m = re.match(r"!(fig|table|listing|eq)\s+([\w\-]+)", line)
                if m:
                    kind = {"fig": "fig", "table": "tab", "listing": "lst", "eq": "eq"}[m.group(1)]
                    self.number(kind, m.group(2))

    def render_file(self, name):
        lines = (SECTIONS / name).read_text(encoding="utf-8").splitlines()
        i = 0
        buf: list[str] = []

        def flush():
            if buf:
                self.para(" ".join(s.strip() for s in buf))
                buf.clear()

        while i < len(lines):
            line = lines[i].rstrip()
            i += 1
            if line.startswith("<!--"):
                while "-->" not in line and i < len(lines):
                    line = lines[i]
                    i += 1
                continue
            if not line.strip():
                flush()
                continue
            if line.startswith("#"):
                flush()
                self.render_heading(line)
                continue
            if line.startswith("- ") or re.match(r"^\d+\) ", line) or re.match(r"^[а-я]\) ", line):
                flush()
                item = line[2:] if line.startswith("- ") else line
                # продолжение элемента на следующих строках с отступом
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                self.para(("– " + item) if line.startswith("- ") else item)
                continue
            if line.startswith("!"):
                flush()
                if (line.startswith("!table") and "gen:" not in line) or line.startswith("!deflist"):
                    rows = []
                    while i < len(lines) and lines[i].startswith("|"):
                        rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                        i += 1
                    self.render_directive(line, rows)
                else:
                    self.render_directive(line)
                continue
            buf.append(line)
        flush()

    def render_heading(self, line):
        if line.startswith("#*"):
            self.heading(line[2:].strip(), 1, structural=True)
        elif line.startswith("#A"):
            letter, kind, title = [x.strip() for x in line[2:].split("|")]
            h = self.heading(f"ПРИЛОЖЕНИЕ {letter}", 1, structural=True, toc=False)
            h.paragraph_format.space_after = Pt(0)
            self.headings.append((1, f"Приложение {letter} {title}"))
            self.para(f"({kind})", align=WD_ALIGN_PARAGRAPH.CENTER, indent=0)
            self.para(title, align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, bold=True, space_after=12)
        else:
            level = len(line) - len(line.lstrip("#"))
            self.heading(line[level:].strip(), level)

    def render_directive(self, line, rows=None):
        cmd, _, rest = line[1:].partition(" ")
        args = [a.strip() for a in rest.split("|")]
        if cmd == "fig":
            self.figure(args[0], args[1], args[2], self.resolve(args[3]))
        elif cmd == "table":
            label, caption = args[0], args[1]
            if len(args) > 2 and args[2].startswith("gen:"):
                spec = tables.GENERATORS[args[2][4:]](self)
                self.table(label, caption, spec["header"], spec["rows"], spec.get("widths"),
                           spec.get("font", 12), spec.get("align"))
            else:
                widths = [float(w) for w in args[2].split(",")] if len(args) > 2 and args[2] else None
                align = args[3] if len(args) > 3 else None
                self.table(label, caption, rows[0], rows[1:], widths, 12, align)
        elif cmd == "deflist":
            widths = [float(w) for w in args[0].split(",")]
            self.deflist(rows, widths)
        elif cmd == "listing":
            self.listing(args[0], args[1], extract_code(args[2], args[3]))
        elif cmd == "eq":
            self.equation(args[0], args[1])
        elif cmd == "placeholder":
            self.placeholder(rest.strip())
        elif cmd == "pagebreak":
            self.page_break()
        elif cmd == "code":
            size = float(args[1]) if len(args) > 1 else 9
            self.code_block((ROOT / args[0]).read_text(encoding="utf-8"), size)
        elif cmd == "applisting":
            num, caption, path = args[0], args[1], args[2]
            self.para(f"Листинг {num} – {caption}", align=WD_ALIGN_PARAGRAPH.LEFT, indent=0,
                      keep_next=True, space_before=6)
            self.code_block(tables.appendix_code(path), 9)
            self.para("", spacing=1.0)
        elif cmd == "include":
            spec = tables.GENERATORS[args[0]](self)
            self.code_block(spec, 9)
        else:
            raise ValueError(f"Неизвестная директива: {line}")

    # ----------------------------------------------- титул, задание, реферат
    def title_page(self):
        c = WD_ALIGN_PARAGRAPH.CENTER
        L = WD_ALIGN_PARAGRAPH.LEFT
        P = dict(indent=0, spacing=1.0)
        self.para("Министерство науки и высшего образования Российской Федерации", c, **P)
        self.para("ФГБОУ ВО «Кубанский государственный технологический университет»", c, **P)
        self.para("(ФГБОУ ВО «КубГТУ»)", c, **P, space_after=18)
        self.para("Институт [наименование института]", L, **P, space_after=4)
        self.para("Кафедра информационных систем и программирования", L, **P, space_after=4)
        self.para("Направление подготовки 09.03.04 Программная инженерия", L, **P, space_after=4)
        self.para("Профиль [наименование профиля]", L, **P, space_after=40)
        self.para("КУРСОВАЯ РАБОТА", c, **P, bold=True, size=16, space_after=18)
        self.para("по дисциплине «Системы искусственного интеллекта»", c, **P, space_after=12)
        self.para("на тему: «Разработка гибридной интеллектуальной системы планирования "
                  "маршрутов доставки на основе генетического алгоритма и нечёткой логики»",
                  c, **P, bold=True, space_after=30)
        self.para("Выполнил(-а) студент(-ка) [курс] курса [группа] группы", L, **P, space_after=2)
        self.para("[Фамилия Имя Отчество]", L, **P, space_after=16)
        self.para("Допущен к защите ____________________________", L, **P, space_after=16)
        self.para("Руководитель (нормоконтролёр) работы", L, **P, space_after=2)
        self.para("[должность] ______________________ [Фамилия И.О.]", L, **P, space_after=16)
        self.para("Защищен ___________________   Оценка ___________________", L, **P,
                  space_after=16)
        self.para("Члены комиссии ____________________________________________", L, **P,
                  space_after=6)
        for _ in range(2):
            self.para("                           ____________________________________________",
                      L, **P, space_after=6)
        self.para("(подпись, дата, расшифровка подписи)", c, **P, size=11, space_after=30)
        self.para("Краснодар", c, **P)
        self.para("2026 г.", c, **P)

    def task_page(self):
        c = WD_ALIGN_PARAGRAPH.CENTER
        L = WD_ALIGN_PARAGRAPH.LEFT
        R = WD_ALIGN_PARAGRAPH.RIGHT
        P = dict(indent=0, spacing=1.0, size=13)
        self.page_break()
        self.para("ФГБОУ ВО «Кубанский государственный технологический университет»", c, **P)
        self.para("(ФГБОУ ВО «КубГТУ»)", c, **P, space_after=6)
        self.para("Институт [наименование института]", L, **P)
        self.para("Кафедра информационных систем и программирования", L, **P)
        self.para("Направление подготовки 09.03.04 Программная инженерия", L, **P)
        self.para("Профиль [наименование профиля]", L, **P, space_after=6)
        self.para("УТВЕРЖДАЮ", R, **P)
        self.para("Зав. кафедрой ________________", R, **P)
        self.para("«___» ____________ 20__ г.", R, **P, space_after=6)
        self.para("ЗАДАНИЕ", c, **P, bold=True)
        self.para("на курсовую работу", c, **P, space_after=6)
        self.para("Студенту(-ке) [Фамилия И.О.] [курс] курса группы [группа]", L, **P)
        self.para("Тема работы: «Разработка гибридной интеллектуальной системы планирования "
                  "маршрутов доставки на основе генетического алгоритма и нечёткой логики»",
                  WD_ALIGN_PARAGRAPH.JUSTIFY, **P)
        self.para("(утверждена указанием директора института № ___ от ________ 20__ г.)",
                  L, indent=0, spacing=1.0, size=11, space_after=4)
        self.para("План работы:", L, **P)
        plan = ["1. Анализ проблем предметной области: задача маршрутизации транспорта с "
                "ограничениями вместимости и временными окнами, критерии качества плана доставки.",
                "2. Выбор и обоснование интеллектуальных методов: генетический алгоритм и "
                "нечёткий логический вывод Мамдани; гибридная схема их взаимодействия.",
                "3. Разработка интеллектуальной системы (программная реализация на Python) и "
                "экспериментальный анализ её работы."]
        for s in plan:
            self.para(s, WD_ALIGN_PARAGRAPH.JUSTIFY, **P)
        pages = self.stats.get("body_pages", "__")
        self.para("Объём работы:", L, **P, space_before=4)
        self.para(f"а) пояснительная записка {pages} с.;", L, **P)
        self.para("б) иллюстративная часть ______ лист(-ов).", L, **P, space_after=4)
        self.para("Рекомендуемая литература:", L, **P)
        for k in ("jones", "rutkovskaya", "gladkov"):
            self.para(f"{('jones', 'rutkovskaya', 'gladkov').index(k) + 1}. "
                      f"{SOURCES[k]}", WD_ALIGN_PARAGRAPH.JUSTIFY, indent=0, spacing=1.0,
                      size=12)
        self.para("Срок выполнения работы: с «___» ________ по «___» ________ 20__ г.", L, **P,
                  space_before=4)
        self.para("Срок защиты: «___» ____________ 20__ г.", L, **P)
        self.para("Дата выдачи задания: «___» ____________ 20__ г.", L, **P)
        self.para("Дата сдачи работы на кафедру: «___» ____________ 20__ г.", L, **P,
                  space_after=8)
        self.para("Руководитель работы ____________________ [Фамилия И.О.]", L, **P)
        self.para("(должность, подпись)", L, indent=0, spacing=1.0, size=11, space_after=6)
        self.para("Задание принял студент ____________________ [Фамилия И.О.]", L, **P)
        self.para("(подпись)", L, indent=0, spacing=1.0, size=11)

    def abstract(self):
        s = self.stats
        self.heading("РЕФЕРАТ", 1, structural=True, toc=False)
        self.para(f"Курсовая работа: {s.get('pages', '__')} с., {s.get('figs', '__')} рис., "
                  f"{s.get('tables', '__')} табл., {s.get('sources', '__')} источников, "
                  f"{s.get('apps', '__')} приложения.")
        self.para("ИНТЕЛЛЕКТУАЛЬНАЯ СИСТЕМА, ГЕНЕТИЧЕСКИЙ АЛГОРИТМ, НЕЧЁТКАЯ ЛОГИКА, "
                  "АЛГОРИТМ МАМДАНИ, ЛИНГВИСТИЧЕСКАЯ ПЕРЕМЕННАЯ, БАЗА ПРАВИЛ, ГИБРИДНАЯ "
                  "СИСТЕМА, ЗАДАЧА МАРШРУТИЗАЦИИ ТРАНСПОРТА, ВРЕМЕННЫЕ ОКНА, ЛОГИСТИКА")
        for t in tables.ABSTRACT_TEXT:
            self.para(self.resolve(t))

    def toc(self):
        """Содержание: поле TOC с заранее заполненным результатом."""
        self.heading("СОДЕРЖАНИЕ", 1, structural=True, toc=False)
        entries = self.toc_entries or [(1, "Содержание будет заполнено при обновлении поля")]
        first = True
        for idx, (level, text) in enumerate(entries):
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.first_line_indent = Cm(0)
            pf.left_indent = Cm(0.5 * (level - 1))
            pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            pf.line_spacing = 1.5
            pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT,
                                      WD_TAB_LEADER.DOTS)
            if first:
                for kind, txt in (("begin", None), ("instr", 'TOC \\o "1-3" \\h \\z \\u'),
                                  ("separate", None)):
                    run = p.add_run()
                    if kind == "instr":
                        el = OxmlElement("w:instrText")
                        el.set(qn("xml:space"), "preserve")
                        el.text = f" {txt} "
                    else:
                        el = OxmlElement("w:fldChar")
                        el.set(qn("w:fldCharType"), kind)
                    run._r.append(el)
                first = False
            page = self.toc_pages.get((level, text), "")
            p.add_run(f"{text}\t{page}")
            if idx == len(entries) - 1:
                run = p.add_run()
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), "end")
                run._r.append(el)

    def sources(self):
        self.heading("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", 1, structural=True)
        for i, k in enumerate(self.cited, 1):
            p = self.para(f"{i}. {SOURCES[k]}")
            p.paragraph_format.first_line_indent = Cm(1.25)
        unused = [k for k in SOURCES if k not in self.cited]
        if unused:
            print("ВНИМАНИЕ: источники без ссылок в тексте:", unused)

    # ------------------------------------------------------------- сборка
    def build(self, toc_entries=None):
        self.toc_entries = toc_entries
        self.prescan(SECTION_FILES + [APPENDIX_FILE])
        self.title_page()
        self.task_page()
        self.abstract()
        self.toc()
        for f in SECTION_FILES:
            self.render_file(f)
        self.sources()
        self.render_file(APPENDIX_FILE)
        return self.doc


# ================================================================ извлечение кода
def extract_code(path: str, spec: str, nodoc: bool | None = None) -> str:
    """Фрагмент исходного кода для листинга: функция, метод или диапазон строк.
    Суффикс «!nodoc» в спецификации убирает строки документации."""
    if nodoc is None:
        nodoc = spec.endswith("!nodoc")
        spec = spec.removesuffix("!nodoc")
    src = (ROOT / path).read_text(encoding="utf-8")
    lines = src.splitlines()
    if spec.startswith("defs:"):
        return "\n\n".join(extract_code(path, "def:" + name, nodoc)
                             for name in spec[5:].split(","))
    if spec.startswith("lines:"):
        a, b = map(int, spec[6:].split("-"))
        chunk = lines[a - 1:b]
    else:
        kind, name = spec.split(":", 1)
        tree = ast.parse(src)
        node = None
        parts = name.split(".")
        scope = tree.body
        for i, part in enumerate(parts):
            for n in scope:
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == part:
                    node = n
                    scope = n.body
                    break
            else:
                raise KeyError(f"{name} не найден в {path}")
        start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno)
        chunk = lines[start - 1:node.end_lineno]
        if nodoc and node.body and isinstance(node.body[0], ast.Expr) and \
                isinstance(getattr(node.body[0], "value", None), ast.Constant) and \
                isinstance(node.body[0].value.value, str):
            ds = node.body[0]
            chunk = lines[start - 1:ds.lineno - 1] + lines[ds.end_lineno:node.end_lineno]
    # убрать общий отступ
    ind = min((len(s) - len(s.lstrip()) for s in chunk if s.strip()), default=0)
    return "\n".join(s[ind:] for s in chunk)


# ================================================================ PDF и страницы
def to_pdf(docx: Path, outdir: Path) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice не найден")
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(outdir),
                    str(docx)], check=True, capture_output=True, timeout=300)
    return outdir / (docx.stem + ".pdf")


def pdf_pages_text(pdf: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True,
                         check=True).stdout.decode("utf-8")
    return out.split("\f")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("ё", "е").replace("Ё", "Е")).strip().lower()


def find_heading_pages(pages: list[str], headings: list[tuple[int, str]]) -> dict:
    """Номера страниц заголовков: последовательный поиск по тексту PDF."""
    result = {}
    texts = [norm(p) for p in pages]
    # поиск начинается после страницы с содержанием
    start = next(i for i, t in enumerate(texts) if "содержание" in t[:200]) + 1
    while start < len(texts) and "введение" not in texts[start][:400]:
        start += 1
    cur = start
    for level, h in headings:
        key = norm(h)[:45]
        if h.startswith("Приложение"):
            key = norm("приложение " + h.split()[1])
        for p in range(cur, len(texts)):
            if key in texts[p]:
                result[(level, h)] = p + 1
                cur = p
                break
        else:
            print("Не найден заголовок в PDF:", h)
    return result


def count_stats(builder: ReportBuilder, pages: list[str], toc_pages: dict) -> dict:
    n_pages = len([p for p in pages if p.strip()])
    app_pages = [v for (lvl, h), v in toc_pages.items() if h.startswith("Приложение")]
    body = (min(app_pages) - 1) if app_pages else n_pages
    n_apps = sum(1 for _, h in builder.headings if h.startswith("Приложение"))
    return {"pages": n_pages, "body_pages": body, "figs": builder.counters["fig"],
            "tables": builder.counters["tab"], "sources": len(builder.cited),
            "apps": n_apps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    b = ReportBuilder()
    b.build()
    if args.no_pdf:
        b.doc.save(OUT_DOCX)
        print("Сохранено:", OUT_DOCX)
        return
    tmp = Path(tempfile.mkdtemp())
    entries = list(b.headings)
    # проход 1 — с заполнителем содержания, чтобы узнать страницы
    b1 = ReportBuilder(toc_pages={e: 0 for e in entries}, stats={"pages": 99, "body_pages": 99,
                                                                  "figs": 99, "tables": 99,
                                                                  "sources": 99, "apps": 9})
    b1.build(entries)
    p1 = tmp / "pass1.docx"
    b1.doc.save(p1)
    pages = pdf_pages_text(to_pdf(p1, tmp))
    toc_pages = find_heading_pages(pages, entries)
    stats = count_stats(b1, pages, toc_pages)
    # проход 2 — окончательный
    b2 = ReportBuilder(toc_pages=toc_pages, stats=stats)
    b2.build(entries)
    b2.doc.save(OUT_DOCX)
    pdf = to_pdf(OUT_DOCX, tmp)
    pages2 = pdf_pages_text(pdf)
    toc2 = find_heading_pages(pages2, entries)
    if toc2 != toc_pages:
        print("Номера страниц изменились после второго прохода — третий проход")
        stats = count_stats(b2, pages2, toc2)
        b3 = ReportBuilder(toc_pages=toc2, stats=stats)
        b3.build(entries)
        b3.doc.save(OUT_DOCX)
        pdf = to_pdf(OUT_DOCX, tmp)
    shutil.copy(pdf, OUT_PDF)
    print(f"Сохранено: {OUT_DOCX}\n           {OUT_PDF}")
    print(f"Страниц всего: {stats['pages']}, до приложений: {stats['body_pages']}, "
          f"рисунков: {stats['figs']}, таблиц: {stats['tables']}, "
          f"источников: {stats['sources']}, приложений: {stats['apps']}")


if __name__ == "__main__":
    main()
