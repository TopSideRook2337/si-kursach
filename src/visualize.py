"""Визуализация: карты маршрутов, графики сходимости, функции принадлежности,
результат нечёткого вывода. Используется в GUI, CLI и экспериментах."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from src.model import Instance, evaluate_routes

# Категориальная палитра (фиксированный порядок цветов машин)
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
           "#6250d6", "#e34948"]
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#d9d8d4"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": INK2,
    "axes.labelcolor": INK,
    "axes.titlesize": 11,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

URGENCY_MARKERS = {1: ("o", "обычный"), 2: ("D", "повышенный"), 3: ("*", "срочный")}


def plot_routes(inst: Instance, routes: list[list[int]], ax=None, title: str | None = None,
                annotate: bool = True):
    """Карта маршрутов: склад — чёрный квадрат, клиенты — маркер по срочности,
    маршрут каждой машины — свой цвет, опоздавшие клиенты обведены красным."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.4, 6.0))
    m = evaluate_routes(routes, inst)
    pts = inst.coords()
    late = set()
    for s in m.routes:
        for cid, t in zip(s.clients, s.arrivals):
            if t > inst.clients[cid - 1].tw_end:
                late.add(cid)
    for k, r in enumerate(routes):
        if not r:
            continue
        path = [0] + r + [0]
        color = PALETTE[k % len(PALETTE)]
        load = sum(inst.clients[c - 1].demand for c in r)
        ax.plot(pts[path, 0], pts[path, 1], "-", color=color, lw=1.6, alpha=0.9,
                label=f"Машина {k + 1}: {len(r)} кл., {load}/{inst.capacity}")
    for u, (mk, lab) in URGENCY_MARKERS.items():
        ids = [c.id for c in inst.clients if c.urgency == u]
        if ids:
            ax.scatter(pts[ids, 0], pts[ids, 1], marker=mk, s=70 if u == 3 else 32,
                       c="white", edgecolors=INK, linewidths=1.0, zorder=3)
    if late:
        ids = sorted(late)
        ax.scatter(pts[ids, 0], pts[ids, 1], s=170, facecolors="none", edgecolors="#e34948",
                   linewidths=1.6, zorder=4)
    ax.scatter([pts[0, 0]], [pts[0, 1]], marker="s", s=110, c=INK, zorder=5)
    if annotate and inst.n_clients <= 30:
        for c in inst.clients:
            ax.annotate(str(c.id), (c.x, c.y), xytext=(4, 4), textcoords="offset points",
                        fontsize=7, color=INK2)
    # легенда: маршруты + обозначения
    from matplotlib.lines import Line2D
    handles, labels = ax.get_legend_handles_labels()
    handles += [Line2D([], [], marker="s", ls="", color=INK, ms=8),
                Line2D([], [], marker="o", ls="", mfc="white", mec=INK, ms=6),
                Line2D([], [], marker="D", ls="", mfc="white", mec=INK, ms=5),
                Line2D([], [], marker="*", ls="", mfc="white", mec=INK, ms=10),
                Line2D([], [], marker="o", ls="", mfc="none", mec="#e34948", ms=11, mew=1.6)]
    labels += ["склад", "обычный заказ", "повышенная срочность", "срочный заказ",
               "опоздание"]
    ax.legend(handles, labels, fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x, км")
    ax.set_ylabel("y, км")
    sub = (f"пробег {m.total_distance:.0f} км, опозданий {m.n_late}, "
           f"перегруз {m.overload:.0f}")
    ax.set_title(f"{title}\n{sub}" if title else sub)
    return ax


def plot_convergence(history_best, history_mean, ax=None, title: str = "Сходимость ГА",
                     label_prefix: str = ""):
    """График сходимости: лучшая и средняя приспособленность по поколениям."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.4, 4.0))
    g = np.arange(len(history_best))
    ax.plot(g, history_best, color=PALETTE[0], lw=2, label=f"{label_prefix}лучшая")
    ax.plot(g, history_mean, color=PALETTE[1], lw=1.4, label=f"{label_prefix}средняя")
    ax.set_xlabel("Поколение")
    ax.set_ylabel("Приспособленность")
    ax.set_title(title)
    ax.legend()
    return ax


def plot_membership(var, ax=None, value: float | None = None):
    """Графики функций принадлежности всех термов лингвистической переменной."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.0, 3.0))
    lo, hi = var.universe
    x = np.linspace(lo, hi, 600)
    for i, t in enumerate(var.terms.values()):
        ax.plot(x, t.mf(x), color=PALETTE[i % len(PALETTE)], lw=2, label=t.label)
    if value is not None:
        ax.axvline(value, color=INK, ls="--", lw=1)
    ax.set_ylim(-0.03, 1.08)
    ax.set_xlim(lo, hi)
    ax.set_title(var.title)
    ax.set_ylabel("μ(x)")
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    return ax


def plot_all_memberships(engine, path=None):
    """Все входные и выходная переменные на одном рисунке (сетка 3×2)."""
    fig, axes = plt.subplots(3, 2, figsize=(12, 9))
    vars_ = list(engine.inputs.values()) + [engine.output]
    for ax, v in zip(axes.flat, vars_):
        plot_membership(v, ax)
    fig.tight_layout()
    if path:
        fig.savefig(path)
        plt.close(fig)
    return fig


def plot_inference(trace, engine, ax=None, top: int = 6):
    """Результат нечёткого вывода: активизированные множества сработавших
    правил, аккумулированное множество и центр тяжести."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.4, 3.6))
    grid = trace.grid
    for i, t in enumerate(engine.output.terms.values()):
        ax.plot(grid, t.mf(grid), color=GRID, lw=1, ls="--")
    order = np.argsort(trace.activations)[::-1][:top]
    for n, j in enumerate(order):
        if trace.activations[j] <= 0:
            continue
        ax.plot(grid, trace.activated_sets[j], color=PALETTE[n % len(PALETTE)], lw=1.2,
                label=f"П{j + 1}: d = {trace.activations[j]:.2f}")
    ax.fill_between(grid, trace.accumulated, color=PALETTE[0], alpha=0.18,
                    label="аккумуляция (max)")
    ax.axvline(trace.output, color=INK, lw=1.6, label=f"центр тяжести y = {trace.output:.3f}")
    ax.set_xlabel(engine.output.title)
    ax.set_ylabel("μ")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    ax.set_title("Нечёткий вывод Мамдани")
    return ax
