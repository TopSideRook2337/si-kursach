"""Формулы пояснительной записки в формате Office Math (OMML).

Каждая формула — функция без аргументов, возвращающая XML содержимого
<m:oMath>. Формулы получаются настоящими редактируемыми уравнениями Word.
Небольшой набор конструкторов ниже покрывает всё, что нужно: дроби,
индексы, суммы, скобки, функции min/max.
"""
from __future__ import annotations

from xml.sax.saxutils import escape


# ------------------------------------------------------------------ конструкторы
def r(text: str, plain: bool = False) -> str:
    """Текстовый фрагмент формулы. plain=True — прямое начертание (имена функций, числа)."""
    sty = '<m:rPr><m:sty m:val="p"/></m:rPr>' if plain else ""
    text = text.replace(" ", "\u00a0")
    return (f'<m:r>{sty}<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/>'
            f'</w:rPr><m:t xml:space="preserve">{escape(text)}</m:t></m:r>')


def t(text: str) -> str:
    """Прямой (не курсивный) текст: числа, слова, знаки операций."""
    return r(text, plain=True)


def seq(*parts: str) -> str:
    return "".join(parts)


def frac(num: str, den: str) -> str:
    return f"<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>"


def sub(base: str, s: str) -> str:
    return f"<m:sSub><m:e>{base}</m:e><m:sub>{s}</m:sub></m:sSub>"


def sup(base: str, s: str) -> str:
    return f"<m:sSup><m:e>{base}</m:e><m:sup>{s}</m:sup></m:sSup>"


def subsup(base: str, s: str, p: str) -> str:
    return f"<m:sSubSup><m:e>{base}</m:e><m:sub>{s}</m:sub><m:sup>{p}</m:sup></m:sSubSup>"


def nary(char: str, lo: str, hi: str, body: str) -> str:
    """Сумма/интеграл/произведение с пределами."""
    hide = ""
    if not lo:
        hide += '<m:subHide m:val="1"/>'
    if not hi:
        hide += '<m:supHide m:val="1"/>'
    loc = "subSup" if char == "∫" else "undOvr"
    return (f'<m:nary><m:naryPr><m:chr m:val="{char}"/><m:limLoc m:val="{loc}"/>{hide}'
            f'</m:naryPr><m:sub>{lo}</m:sub><m:sup>{hi}</m:sup><m:e>{body}</m:e></m:nary>')


def br(content: str, beg: str = "(", end: str = ")") -> str:
    """Растягивающиеся скобки."""
    return (f'<m:d><m:dPr><m:begChr m:val="{escape(beg)}"/><m:endChr m:val="{escape(end)}"/>'
            f'</m:dPr><m:e>{content}</m:e></m:d>')


def lim_low(base: str, lim: str) -> str:
    """Функция с нижним индексом под ней (max по j и т.п.)."""
    return f"<m:limLow><m:e>{base}</m:e><m:lim>{lim}</m:lim></m:limLow>"


def func(name: str, arg: str, under: str | None = None) -> str:
    fname = t(name) if under is None else lim_low(t(name), under)
    return f"<m:func><m:fName>{fname}</m:fName><m:e>{arg}</m:e></m:func>"


def cases(*rows: str) -> str:
    """Система (фигурная скобка слева, строки — уравнения)."""
    eqs = "".join(f"<m:e>{row}</m:e>" for row in rows)
    return (f'<m:d><m:dPr><m:begChr m:val="{{"/><m:endChr m:val=""/></m:dPr>'
            f'<m:e><m:eqArr>{eqs}</m:eqArr></m:e></m:d>')


MU = r("μ")


def mu(arg: str, idx: str | None = None) -> str:
    base = MU if idx is None else sub(MU, idx)
    return seq(base, br(arg))


# ---------------------------------------------------------------------- формулы
def cvrp_objective():
    return seq(t("min "), nary("∑", seq(r("k"), t("=1")), r("K"),
                               nary("∑", seq(r("i"), t(",")), "", nary("∑", r("j"), "",
                                    seq(sub(r("d"), r("ij")), t("·"), sub(r("x"), r("ijk")))))))


def capacity():
    return seq(nary("∑", seq(r("i"), t("∈"), sub(r("R"), r("k"))), "", sub(r("q"), r("i"))),
               t(" ≤ "), r("Q"), t(",   "), r("k"), t(" = 1, …, "), r("K"))


def time_window():
    return seq(sub(r("s"), r("i")), t(" = "), func("max", br(seq(sub(r("e"), r("i")), t(", "),
                                                                   sub(r("t"), r("i"))))),
               t(",   "), sub(r("late"), r("i")), t(" = "),
               func("max", br(seq(t("0, "), sub(r("s"), r("i")), t(" − "), sub(r("l"), r("i"))))))


def space_size():
    return seq(r("S"), br(seq(r("N"), t(", "), r("K"))), t(" = "),
               frac(seq(br(seq(r("N"), t(" + "), r("K"), t(" − 1"))), t("!")),
                    seq(br(seq(r("K"), t(" − 1"))), t("!"))))


def roulette():
    return seq(sub(r("p"), r("i")), t(" = "),
               frac(sub(r("f"), r("i")), nary("∑", seq(r("j"), t("=1")), r("P"), sub(r("f"), r("j")))))


def mf_tri():
    return seq(mu(r("x")), t(" = "),
               func("max", br(seq(t("0, "), func("min", br(seq(
                   frac(seq(r("x"), t(" − "), r("a")), seq(r("b"), t(" − "), r("a"))), t(", "),
                   frac(seq(r("c"), t(" − "), r("x")), seq(r("c"), t(" − "), r("b"))))))))))


def mf_trap():
    return seq(mu(r("x")), t(" = "),
               func("max", br(seq(t("0, "), func("min", br(seq(
                   frac(seq(r("x"), t(" − "), r("a")), seq(r("b"), t(" − "), r("a"))), t(", 1, "),
                   frac(seq(r("d"), t(" − "), r("x")), seq(r("d"), t(" − "), r("c"))))))))))


def fuzzify():
    return seq(sub(r("b"), r("i")), t(" = "), mu(sub(r("a"), r("i")), r("i")),
               t(",   "), r("i"), t(" = 1, …, "), r("k"))


def aggregate():
    return seq(sub(r("c"), r("j")), t(" = "),
               func("min", br(sub(r("b"), r("i")), "{", "}"), seq(r("i"), t("∈"), sub(r("I"), r("j")))),
               t(",   "), r("j"), t(" = 1, …, "), r("n"))


def activate():
    return seq(sub(r("d"), r("j")), t(" = "), sub(r("c"), r("j")), t("·"), sub(r("F"), r("j")),
               t(",    "), sub(r("μ'"), r("j")), br(r("x")), t(" = "),
               func("min", br(seq(sub(r("d"), r("j")), t(", "), mu(r("x"), r("j"))), "{", "}")))


def accumulate():
    return seq(sub(MU, r("E")), br(r("x")), t(" = "),
               func("max", br(sub(r("μ'"), r("j")) + br(r("x")), "{", "}"),
                    seq(r("j"), t(" = 1, …, "), r("n"))))


def centroid():
    return seq(r("y"), t(" = "),
               frac(nary("∫", t("Min"), t("Max"), seq(r("x"), t("·"), sub(MU, r("E")), br(r("x")),
                                                       r("dx"))),
                    nary("∫", t("Min"), t("Max"), seq(sub(MU, r("E")), br(r("x")), r("dx")))))


def centroid_discrete():
    return seq(r("Q"), t(" ≈ "),
               frac(nary("∑", seq(r("g"), t("=1")), r("G"),
                         seq(sub(r("x"), r("g")), t("·"), sub(MU, r("E")), br(sub(r("x"), r("g"))))),
                    nary("∑", seq(r("g"), t("=1")), r("G"), seq(sub(MU, r("E")), br(sub(r("x"), r("g")))))))


def in_length():
    return seq(r("L"), t(" = "), frac(r("D"), sub(r("D"), t("ref"))))


def in_load():
    return seq(r("З"), t(" = "), func("max", frac(sub(r("W"), r("k")), r("Q")), r("k")))


def in_timewin():
    return seq(r("T"), t(" = "), frac(t("1"), r("N")),
               nary("∑", seq(r("i"), t("=1")), r("N"),
                    func("min", br(seq(t("1, "), frac(sub(r("late"), r("i")), t("60"))), "{", "}"))))


def in_urgency():
    w = br(seq(sub(r("u"), r("i")), t(" − 1")))
    return seq(r("U"), t(" = "),
               frac(nary("∑", r("i"), "", seq(w, t("·"), frac(sub(r("s"), r("i")), r("H")))),
                    nary("∑", r("i"), "", w)))


def in_balance():
    return seq(r("B"), t(" = "), frac(sub(r("σ"), r("τ")), sub(r("m"), r("τ"))))


def fitness():
    return seq(r("f"), br(r("x")), t(" = "), r("Q"), br(r("x")), t(" − "), r("P"), br(r("x")),
               t(",   "), r("P"), br(r("x")), t(" = "),
               cases(seq(t("0,"), t("  если перегруза нет;")),
                     seq(t("1 + "), frac(r("Δ"), r("Q")), t(",  если "), r("Δ"), t(" > 0,"))))


def weighted():
    return seq(sub(r("Q"), t("ws")), t(" = 1 − "),
               br(seq(t("0,35·"), sub(r("s"), r("L")), t(" + 0,30·"), sub(r("s"), r("T")),
                      t(" + 0,20·"), sub(r("s"), r("U")), t(" + 0,15·"), sub(r("s"), r("B")))))


FORMULAS = {name: fn for name, fn in globals().items()
            if callable(fn) and fn.__module__ == __name__ and not name.startswith("_")
            and name not in {"r", "t", "seq", "frac", "sub", "sup", "subsup", "nary", "br",
                             "lim_low", "func", "cases", "mu", "escape"}}
