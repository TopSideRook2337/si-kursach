"""Схемы для пояснительной записки (рисуются средствами matplotlib).

    python docs/make_diagrams.py

Создаёт в docs/figures: архитектуру системы, диаграмму классов, блок-схемы
ГА и нечёткого вывода (символы по ГОСТ 19.701-90), иллюстрацию кодирования
хромосомы и оператора OX, схему конфликта критериев, график роста
пространства решений.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle  # noqa: E402

from src.visualize import PALETTE  # noqa: E402

OUT = ROOT / "docs" / "figures"
FS = 1.35           # общий множитель шрифтов (читаемость при печати)
INK = "#0b0b0b"
FILL_A = "#e8f1fc"   # голубая заливка (ГА)
FILL_B = "#fdeee6"   # оранжевая заливка (нечёткий блок)
FILL_C = "#f3f3f1"   # нейтральная


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fill=FILL_C, fs=9, bold=False, rounded=False, lw=1.2):
    """Прямоугольник с центром (x, y)."""
    style = "round,pad=0,rounding_size=0.12" if rounded else "square,pad=0"
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle=style, fc=fill,
                                ec=INK, lw=lw))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs * FS,
            fontweight="bold" if bold else "normal", wrap=True)


def terminator(ax, x, y, w, h, text, fs=9):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle=f"round,pad=0,rounding_size={h / 2}", fc="white",
                                ec=INK, lw=1.2))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs * FS)


def decision(ax, x, y, w, h, text, fs=8.5):
    ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)],
                         closed=True, fc="white", ec=INK, lw=1.2))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs * FS)


def io(ax, x, y, w, h, text, fs=9):
    s = 0.25
    ax.add_patch(Polygon([(x - w / 2 + s, y + h / 2), (x + w / 2 + s, y + h / 2),
                          (x + w / 2 - s, y - h / 2), (x - w / 2 - s, y - h / 2)],
                         closed=True, fc="white", ec=INK, lw=1.2))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs * FS)


def arrow(ax, x1, y1, x2, y2, text=None, color=INK, lw=1.1, ls="-", tx=0.1, ty=0.0):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls,
                                shrinkA=0, shrinkB=0, mutation_scale=11))
    if text:
        ax.text((x1 + x2) / 2 + tx, (y1 + y2) / 2 + ty, text, fontsize=8 * FS, ha="left",
                va="center")


def line(ax, pts, color=INK, lw=1.1, arrow_end=True):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1], ys[:-1], color=color, lw=lw) if arrow_end else ax.plot(xs, ys, color=color,
                                                                            lw=lw)
    if arrow_end:
        ax.plot(xs[-2:], ys[-2:], color=color, lw=lw)
        arrow(ax, xs[-2], ys[-2], xs[-1], ys[-1], color=color, lw=lw)


def save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ============================================================ архитектура
def architecture():
    fig, ax = canvas(13, 8.4)
    # интерфейс
    box(ax, 6.5, 7.8, 12.4, 0.7, "Интерфейс: gui.py (tkinter), main.py (командная строка)", FILL_C, fs=10, bold=True)
    # данные
    box(ax, 1.9, 6.3, 3.4, 1.4, "generator.py\nгенерация задач\n(seed) ↔ JSON", FILL_C)
    box(ax, 1.9, 4.3, 3.4, 1.8, "model.py\nClient, Instance,\nSolution;\nмоделирование\nмаршрута, метрики",
        FILL_C)
    box(ax, 1.9, 1.9, 3.4, 1.6, "baselines.py\nслучайное решение,\n«ближайший сосед»,\nполный перебор",
        FILL_C)
    # ГА
    ax.add_patch(Rectangle((4.2, 0.6), 4.0, 6.5, fc=FILL_A, ec=INK, lw=1.4))
    ax.text(6.2, 6.8, "Генетический алгоритм", ha="center", fontsize=10 * FS, fontweight="bold")
    steps = ["encoding.py: перестановка\n+ разделители",
             "engine.py: популяция",
             "оценка приспособленности\nкаждой особи",
             "operators.py: турнир,\nскрещивание OX",
             "мутации: обмен, инверсия,\nперенос клиента",
             "элитизм, останов"]
    ys = [6.05, 5.15, 4.25, 3.25, 2.25, 1.25]
    for t, y in zip(steps, ys):
        box(ax, 6.2, y, 3.5, 0.72 if "\n" in t else 0.5, t, "white", fs=8.5)
    for y1, y2 in zip(ys[:-1], ys[1:]):
        arrow(ax, 6.2, y1 - 0.36, 6.2, y2 + 0.36)
    line(ax, [(4.45, 1.25), (4.3, 1.25), (4.3, 4.25), (4.45, 4.25)])
    ax.text(4.25, 2.7, "следующее\nпоколение", rotation=90, fontsize=7.5 * FS, ha="right",
            va="center")
    # приспособленность
    box(ax, 10.6, 5.7, 3.8, 1.2, "fitness.py: FuzzyFitness\nQ = вывод Мамдани(метрики)\n"
        "− штраф за перегруз", "white", fs=8.5)
    # нечёткий блок
    ax.add_patch(Rectangle((8.7, 0.6), 3.8, 4.3, fc=FILL_B, ec=INK, lw=1.4))
    ax.text(10.6, 4.6, "Вывод Мамдани (fuzzy/)", ha="center", fontsize=10 * FS,
            fontweight="bold")
    fsteps = ["1. база из 26 правил", "2. фаззификация", "3. агрегирование (min)",
              "4. активизация (min)", "5. аккумуляция (max)", "6. дефаззификация"]
    for i, t in enumerate(fsteps):
        box(ax, 10.6, 4.05 - i * 0.55, 3.4, 0.42, t, "white", fs=8.2)
    # связи
    line(ax, [(7.95, 4.35), (8.3, 4.35), (8.3, 5.85), (8.7, 5.85)])
    line(ax, [(8.7, 5.45), (8.45, 5.45), (8.45, 4.15), (7.95, 4.15)])
    ax.text(8.25, 6.35, "хромосома →\n← Q", fontsize=7.5 * FS, ha="center", va="center")
    arrow(ax, 10.2, 5.1, 10.2, 4.9)
    arrow(ax, 11.0, 4.9, 11.0, 5.1)
    ax.text(9.0, 5.0, "входы", fontsize=7.5 * FS, va="center")
    ax.text(11.1, 5.0, "Q", fontsize=7.5 * FS, va="center")
    arrow(ax, 3.6, 4.3, 4.2, 4.3)
    arrow(ax, 1.9, 5.6, 1.9, 5.2)
    arrow(ax, 1.9, 2.7, 1.9, 3.4)
    arrow(ax, 6.5, 7.45, 6.5, 7.1)
    arrow(ax, 1.9, 7.45, 1.9, 7.0)
    box(ax, 10.6, 7.05, 3.8, 0.5, "visualize.py: карты, графики", FILL_C, fs=8.5)
    save(fig, "architecture.png")


# ============================================================ диаграмма классов
def uml(ax, x, y, w, name, attrs, methods, fill="white", fs=7.6):
    lh = 0.26
    h_name = 0.36
    h_attr = max(1, len(attrs)) * lh + 0.08
    h_meth = max(1, len(methods)) * lh + 0.08
    top = y
    ax.add_patch(Rectangle((x, top - h_name), w, h_name, fc=fill, ec=INK, lw=1))
    ax.text(x + w / 2, top - h_name / 2, name, ha="center", va="center", fontsize=fs * FS + 0.6,
            fontweight="bold")
    ax.add_patch(Rectangle((x, top - h_name - h_attr), w, h_attr, fc="white", ec=INK, lw=1))
    for i, a in enumerate(attrs):
        ax.text(x + 0.08, top - h_name - 0.05 - (i + 0.5) * lh, a, fontsize=fs * FS, va="center",
                family="DejaVu Sans Mono")
    ax.add_patch(Rectangle((x, top - h_name - h_attr - h_meth), w, h_meth, fc="white", ec=INK,
                           lw=1))
    for i, m in enumerate(methods):
        ax.text(x + 0.08, top - h_name - h_attr - 0.05 - (i + 0.5) * lh, m, fontsize=fs * FS,
                va="center", family="DejaVu Sans Mono")
    return (x, top, w, h_name + h_attr + h_meth)


def classes():
    fig, ax = canvas(14, 10.2)
    c = {}
    c["Instance"] = uml(ax, 0.2, 8.1, 3.3, "Instance",
                        ["depot, clients", "n_vehicles, capacity", "speed, horizon"],
                        ["dist", "save(), load()"], FILL_C)
    c["Client"] = uml(ax, 0.2, 10.0, 3.3, "Client",
                      ["id, x, y, demand", "urgency", "tw_start, tw_end"], [""], FILL_C)
    c["Metrics"] = uml(ax, 0.2, 5.3, 3.3, "SolutionMetrics",
                       ["total_distance", "lateness_index", "urgency_index", "balance_cv",
                        "max_load_ratio, overload"], ["evaluate_routes()"], FILL_C)
    c["MF"] = uml(ax, 4.0, 10.0, 3.0, "TrapezoidalMF",
                  ["a, b, c, d"], ["__call__(x) → μ"], FILL_B)
    c["Tri"] = uml(ax, 4.0, 8.4, 3.0, "TriangularMF", ["a, b, c"], ["__call__(x) → μ"], FILL_B)
    c["Var"] = uml(ax, 7.6, 8.25, 3.2, "LinguisticVariable",
                   ["name, title", "universe", "terms: {имя: Term}"], ["fuzzify(x)"], FILL_B)
    c["Term"] = uml(ax, 7.6, 10.0, 3.2, "Term", ["name, label", "mf"], [""], FILL_B)
    c["Rule"] = uml(ax, 11.0, 10.0, 2.8, "Rule",
                    ["conditions", "conclusion", "weight F", "explanation"], [""], FILL_B)
    c["Mamdani"] = uml(ax, 7.4, 6.2, 3.6, "MamdaniInference",
                       ["inputs, output", "rules", "grid"],
                       ["fuzzify()", "aggregate()", "activate()", "accumulate()",
                        "defuzzify()", "infer(), trace()"], FILL_B)
    c["Fitness"] = uml(ax, 4.0, 5.9, 3.0, "FuzzyFitness",
                       ["inst, engine", "ref_distance", "cache"],
                       ["quality(m)", "score(routes)", "__call__(chrom)"], FILL_A)
    c["WS"] = uml(ax, 4.0, 2.2, 3.0, "WeightedSumFitness", ["WEIGHTS"], ["quality(m)"], FILL_A)
    c["Cfg"] = uml(ax, 11.4, 6.4, 2.5, "GAConfig",
                   ["pop_size", "generations", "crossover_rate", "mutation_rate", "selection",
                    "elite, stagnation"], [""], FILL_A)
    c["Res"] = uml(ax, 11.4, 3.4, 2.5, "GAResult",
                   ["best_routes", "best_fitness", "history_best", "history_mean"], [""],
                   FILL_A)
    c["run"] = uml(ax, 7.6, 2.4, 3.2, "run_ga() [engine.py]", ["популяция, fits"],
        ["отбор, OX, мутации", "элитизм, останов"], FILL_A)

    def link(a, b, kind="assoc", label=None):
        ax_, ay, aw, ah = c[a] if isinstance(a, str) else a
        bx, by, bw, bh = c[b] if isinstance(b, str) else b
        p1 = (ax_ + aw / 2, ay - ah / 2)
        p2 = (bx + bw / 2, by - bh / 2)
        # точки на границах прямоугольников (упрощённо: по ближайшей стороне)
        def edge(x, y, w, h, tx, ty):
            cx, cy = x + w / 2, y - h / 2
            dx, dy = tx - cx, ty - cy
            if abs(dx) * h > abs(dy) * w:
                return (x + w if dx > 0 else x, cy + dy * (w / 2) / max(abs(dx), 1e-9))
            return (cx + dx * (h / 2) / max(abs(dy), 1e-9), y if dy > 0 else y - h)
        s = edge(ax_, ay, aw, ah, *p2)
        e = edge(bx, by, bw, bh, *p1)
        if kind == "inherit":
            ax.annotate("", xy=e, xytext=s, arrowprops=dict(arrowstyle="-|>", fc="white",
                                                            ec=INK, lw=1, mutation_scale=14))
        elif kind == "compose":
            ax.annotate("", xy=s, xytext=e, arrowprops=dict(arrowstyle="-", ec=INK, lw=1))
            ax.plot(*s, marker="D", ms=6, mfc=INK, mec=INK)
        else:
            ax.annotate("", xy=e, xytext=s, arrowprops=dict(arrowstyle="->", ec=INK, lw=1,
                                                            ls="--"))
        if label:
            ax.text((s[0] + e[0]) / 2 + 0.08, (s[1] + e[1]) / 2 + 0.05, label, fontsize=7 * FS,
                    ha="left", va="bottom", bbox=dict(fc="white", ec="none", pad=0.5))

    link("Instance", "Client", "compose", "1..N")
    link("Metrics", "Instance", "assoc")
    link("Tri", "MF", "inherit")
    link("Var", "Term", "compose")
    link("Term", "MF", "assoc")
    link("Mamdani", "Var", "compose", "5 вх. + 1 вых.")
    link("Mamdani", "Rule", "compose", "26")
    link("Fitness", "Mamdani", "assoc")
    link("Fitness", "Metrics", "assoc")
    link("run", "Fitness", "assoc", "оценивает")
    link("run", "Cfg", "assoc")
    link("run", "Res", "assoc")
    link("WS", "Fitness", "inherit")
    save(fig, "classes.png")


# ============================================================ блок-схема ГА
def ga_flow():
    fig, ax = canvas(10.3, 13.2)
    X = 3.6
    terminator(ax, X, 12.8, 2.6, 0.55, "Начало")
    io(ax, X, 11.95, 4.4, 0.7, "Ввод задачи и параметров ГА\n(P, G, pc, pm, отбор, элита)")
    box(ax, X, 11.0, 4.6, 0.7, "Начальная популяция\n(10 % эвристика, 90 % случайные)")
    box(ax, X, 10.0, 4.6, 0.7, "Оценка особей:\nметрики → вывод Мамдани", FILL_B)
    box(ax, X, 9.05, 4.6, 0.55, "g := 1; запись журнала сходимости")
    box(ax, X, 8.15, 4.6, 0.55, "Перенос e лучших особей (элитизм)")
    decision(ax, X, 7.1, 3.8, 1.05, "Новое поколение\nзаполнено?")
    box(ax, X, 5.85, 4.6, 0.55, "Отбор двух родителей (турнир, k = 3)")
    box(ax, X, 5.0, 4.6, 0.55, "Скрещивание OX (вероятность pc)")
    box(ax, X, 4.15, 4.6, 0.7, "Мутация потомка (вероятность pm):\nобмен / инверсия / перенос")
    box(ax, X, 3.2, 4.6, 0.55, "Потомки → новое поколение")
    RX = 7.7
    box(ax, RX, 7.1, 2.6, 1.0, "Оценка нового\nпоколения\n(Мамдани)", FILL_B, fs=8.5)
    decision(ax, RX, 5.2, 2.8, 1.6, "g = G или\nстагнация\nили время?", fs=8)
    io(ax, RX, 3.4, 2.5, 0.7, "Вывод лучшего\nрешения", fs=8.5)
    terminator(ax, RX, 2.3, 2.2, 0.55, "Конец")
    ax.set_ylim(1.8, 13.2)
    for y1, y2 in [(12.525, 12.3), (11.6, 11.35), (10.65, 10.35), (9.65, 9.325),
                   (8.775, 8.425), (7.875, 7.625), (6.575, 6.125), (5.575, 5.275),
                   (4.725, 4.5), (3.8, 3.475)]:
        arrow(ax, X, y1, X, y2)
    ax.text(X + 0.1, 6.35, "нет", fontsize=8 * FS)
    # петля: после добавления потомков — снова к проверке заполненности
    line(ax, [(X - 2.3, 3.2), (0.6, 3.2), (0.6, 7.1), (X - 1.9, 7.1)])
    # да → оценка нового поколения
    arrow(ax, X + 1.9, 7.1, RX - 1.3, 7.1)
    ax.text(X + 2.0, 7.25, "да", fontsize=8 * FS)
    arrow(ax, RX, 6.6, RX, 6.0)
    # нет → g := g + 1 → к элитизму
    line(ax, [(RX + 1.4, 5.2), (9.7, 5.2), (9.7, 8.15), (X + 2.3, 8.15)])
    ax.text(9.15, 5.35, "нет", fontsize=8 * FS)
    ax.text(9.8, 6.7, "g := g + 1", fontsize=8.5 * FS, rotation=90, va="center")
    # да → вывод результата
    arrow(ax, RX, 4.4, RX, 3.75)
    ax.text(RX + 0.1, 4.1, "да", fontsize=8 * FS)
    arrow(ax, RX, 3.05, RX, 2.575)
    save(fig, "ga_flow.png")


# ============================================================ блок-схема Мамдани
def mamdani_flow():
    fig, ax = canvas(10, 9.6)
    X = 3.3
    terminator(ax, X, 9.2, 2.4, 0.5, "Начало")
    io(ax, X, 8.4, 5.2, 0.65, "Метрики решения → чёткие входы\na = (L, З, T, U, B)")
    blocks = [
        ("1. Формирование базы правил:\n26 правил «ЕСЛИ–ТО» с весами Fj", 7.45),
        ("2. Фаззификация: bi = μ(ai)\nдля всех термов входных переменных", 6.45),
        ("3. Агрегирование подусловий:\ncj = min{bi} (нечёткое «И»)", 5.45),
        ("4. Активизация: dj = cj·Fj;\nμ'j(x) = min{dj, μj(x)}", 4.45),
        ("5. Аккумуляция: μE(x) = max μ'j(x)", 3.5),
        ("6. Дефаззификация (центр тяжести):\nQ = Σ x·μE(x) / Σ μE(x)", 2.55),
    ]
    for t, y in blocks:
        box(ax, X, y, 5.2, 0.7 if "\n" in t else 0.5, t, FILL_B if y < 7 else FILL_C, fs=8.8)
    io(ax, X, 1.55, 4.4, 0.6, "Q ∈ [0, 1] → приспособленность ГА")
    terminator(ax, X, 0.7, 2.4, 0.5, "Конец")
    ys = [9.2 - 0.25, 8.4 + 0.325, 8.4 - 0.325, 7.45 + 0.35, 7.45 - 0.35, 6.45 + 0.35,
          6.45 - 0.35, 5.45 + 0.35, 5.45 - 0.35, 4.45 + 0.35, 4.45 - 0.35, 3.5 + 0.25,
          3.5 - 0.25, 2.55 + 0.35, 2.55 - 0.35, 1.55 + 0.3, 1.55 - 0.3, 0.7 + 0.25]
    for a, b in zip(ys[0::2], ys[1::2]):
        arrow(ax, X, a, X, b)
    # пояснения справа
    notes = [(6.45, "b — степени истинности\nподусловий (k значений)"),
             (5.45, "c — степени истинности\nусловий правил (n значений)"),
             (4.45, "D_j — «срезанные» множества\nзаключений"),
             (3.5, "E — объединение для выходной\nпеременной «Качество»"),
             (2.55, "интегралы заменены суммами\nпо сетке из 201 точки")]
    for y, t in notes:
        ax.text(6.2, y, t, fontsize=8 * FS, va="center", color="#52514e")
        ax.plot([5.95, 6.15], [y, y], color="#52514e", lw=0.8, ls=":")
    save(fig, "mamdani_flow.png")


# ============================================================ кодирование и OX
def genes_row(ax, x, y, genes, n, title=None, w=0.62, highlight=None):
    for i, g in enumerate(genes):
        sep = g > n
        fc = "#52514e" if sep else "white"
        if highlight and i in highlight:
            fc = FILL_A
        ax.add_patch(Rectangle((x + i * w, y), w, w, fc=fc, ec=INK, lw=1))
        ax.text(x + i * w + w / 2, y + w / 2, "|" if sep else str(g), ha="center", va="center",
                fontsize=10 * FS, color="white" if sep else INK, fontweight="bold")
    if title:
        ax.text(x - 0.15, y + w / 2, title, ha="right", va="center", fontsize=9 * FS)


def encoding():
    fig, ax = canvas(13.2, 6.0)
    n = 8
    ch = [3, 1, 9, 6, 2, 8, 10, 5, 4, 7]
    genes_row(ax, 3.0, 5.0, ch, n, "Хромосома:")
    for i, g in enumerate(ch):
        ax.text(3.0 + i * 0.62 + 0.31, 5.75, str(i + 1), ha="center", fontsize=7 * FS, color="#52514e")
    ax.text(3.0, 4.45, "гены 1..8 — клиенты, гены 9 и 10 (тёмные) — разделители маршрутов",
            fontsize=8.5 * FS, color="#52514e")
    routes = ["Машина 1:  склад → 3 → 1 → склад", "Машина 2:  склад → 6 → 2 → 8 → склад",
              "Машина 3:  склад → 5 → 4 → 7 → склад"]
    for i, r in enumerate(routes):
        ax.text(10.0, 5.6 - i * 0.45, r, fontsize=9 * FS, color=PALETTE[i], fontweight="bold")
    ax.annotate("", xy=(9.9, 5.15), xytext=(9.3, 5.3),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1))
    # OX
    ax.text(0.2, 3.65, "Упорядоченное скрещивание (OX), отрезок позиций 4–6:", fontsize=10 * FS,
            fontweight="bold")
    p1 = [3, 1, 9, 6, 2, 8, 10, 5, 4, 7]
    p2 = [7, 5, 2, 10, 1, 3, 9, 4, 8, 6]
    genes_row(ax, 3.0, 2.6, p1, n, "Родитель 1:", highlight={3, 4, 5})
    genes_row(ax, 3.0, 1.65, p2, n, "Родитель 2:")
    child = [10, 1, 3, 6, 2, 8, 9, 4, 7, 5]
    genes_row(ax, 3.0, 0.4, child, n, "Потомок:", highlight={3, 4, 5})
    ax.text(9.5, 2.0, "1) отрезок 6, 2, 8 копируется из родителя 1\n"
            "   на те же позиции;\n"
            "2) остальные гены берутся из родителя 2\n"
            "   по порядку, начиная с позиции 7:\n"
            "   9, 4, (8), (6), 7, 5, (2), 10, 1, 3\n"
            "   и заполняют позиции 7–10, затем 1–3.",
            fontsize=8.5 * FS, va="center")
    save(fig, "encoding.png")


# ============================================================ конфликт критериев
def criteria():
    fig, ax = canvas(11, 5.2)
    pos = {"Пробег\n(затраты топлива)": (2.0, 4.2), "Соблюдение\nвременных окон": (9.0, 4.2),
           "Срочные заказы\nв начале смены": (9.0, 1.0), "Равномерная\nнагрузка водителей": (2.0, 1.0),
           "Загрузка\nкузова ≤ Q": (5.5, 2.6)}
    for t, (x, y) in pos.items():
        box(ax, x, y, 2.9, 0.95, t, FILL_A if "Загрузка" not in t else FILL_B, fs=9.5,
            rounded=True)
    pairs = [((2.0, 4.2), (9.0, 4.2), "ожидание окна и объезды\nувеличивают пробег"),
             ((9.0, 4.2), (9.0, 1.0), "срочные первыми →\nобычные позже окна"),
             ((2.0, 4.2), (2.0, 1.0), "выравнивание\nудлиняет\nмаршруты"),
             ((2.0, 1.0), (9.0, 1.0), "")]
    for (x1, y1), (x2, y2), t in pairs:
        if x1 == x2:
            ax.annotate("", xy=(x2, y2 + 0.5), xytext=(x1, y1 - 0.5),
                        arrowprops=dict(arrowstyle="<->", color="#e34948", lw=1.4))
            ax.text(x1 + 0.15, (y1 + y2) / 2, t, fontsize=8 * FS, va="center")
        else:
            ax.annotate("", xy=(x2 - 1.45, y2), xytext=(x1 + 1.45, y1),
                        arrowprops=dict(arrowstyle="<->", color="#e34948", lw=1.4))
            ax.text((x1 + x2) / 2, y1 + 0.18, t, fontsize=8 * FS, ha="center")
    for p in [(2.0, 4.2), (9.0, 4.2), (2.0, 1.0), (9.0, 1.0)]:
        ax.plot([p[0] + (1.45 if p[0] < 5 else -1.45), 5.5 + (-1.45 if p[0] < 5 else 1.45)],
                [p[1], 2.6], color="#52514e", lw=0.9, ls="--")
    ax.text(5.5, 1.85, "жёсткое ограничение", fontsize=8 * FS, ha="center", color="#52514e")
    save(fig, "criteria.png")


# ============================================================ рост пространства решений
def space_growth():
    ns = list(range(2, 51))
    fig, ax = plt.subplots(figsize=(7, 3.6))
    for i, k in enumerate([1, 3, 7]):
        vals = [math.lgamma(n + k) / math.log(10) - math.lgamma(k) / math.log(10) for n in ns]
        ax.plot(ns, vals, color=PALETTE[i], lw=2, label=f"K = {k}" if k > 1 else "K = 1 (задача коммивояжёра)")
    ax.axhline(math.log10(3.15e7 * 1e9), color="#52514e", ls="--", lw=1)
    ax.text(3, math.log10(3.15e7 * 1e9) + 1.5,
            "≈ число решений, перебираемых за год при 10⁹ решений/с", fontsize=8 * FS,
            color="#52514e")
    ax.set_xlabel("Число клиентов N")
    ax.set_ylabel("lg (число решений)")
    ax.set_title("Рост числа вариантов (N + K − 1)! / (K − 1)!")
    ax.legend(fontsize=8 * FS)
    fig.savefig(OUT / "space_growth.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def flows_combined():
    """Две блок-схемы на одном рисунке: а) ГА, б) вывод Мамдани."""
    from PIL import Image
    a = Image.open(OUT / "ga_flow.png")
    b = Image.open(OUT / "mamdani_flow.png")
    h = max(a.height, b.height)
    b = b.resize((int(b.width * a.height / b.height * 0.92), int(a.height * 0.92)))
    pad = 60
    canvas_ = Image.new("RGB", (a.width + b.width + pad, h + 110), "white")
    canvas_.paste(a, (0, 0))
    canvas_.paste(b, (a.width + pad, int((h - b.height) / 2)))
    fig, ax = plt.subplots(figsize=(canvas_.width / 200, canvas_.height / 200), dpi=200)
    ax.imshow(canvas_)
    ax.axis("off")
    ax.text(a.width / 2, h + 70, "а) генетический алгоритм", ha="center", fontsize=11 * FS)
    ax.text(a.width + pad + b.width / 2, h + 70, "б) нечёткий вывод Мамдани", ha="center",
            fontsize=11 * FS)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(OUT / "flows.png", dpi=200)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    architecture()
    classes()
    ga_flow()
    mamdani_flow()
    encoding()
    criteria()
    space_growth()
    flows_combined()
    print("Схемы сохранены в", OUT)


if __name__ == "__main__":
    main()
