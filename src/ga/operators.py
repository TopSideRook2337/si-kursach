"""Генетические операторы: отбор, скрещивание, мутации.

Все операторы работают с хромосомой-перестановкой (см. encoding.py) и
сохраняют её корректность: каждый клиент и каждый разделитель после
операции встречается ровно один раз.
"""
from __future__ import annotations

import numpy as np


# ======================================================================= ОТБОР
def tournament_selection(fits: np.ndarray, rng: np.random.Generator, k: int = 3) -> int:
    """Турнирный отбор: из k случайных особей выбирается лучшая.

    Давление отбора регулируется размером турнира k; не зависит от масштаба
    значений приспособленности (важно, т.к. штраф делает их отрицательными).
    """
    idx = rng.integers(0, len(fits), size=k)
    return int(idx[np.argmax(fits[idx])])


def roulette_selection(fits: np.ndarray, rng: np.random.Generator, **_) -> int:
    """Пропорциональный (рулеточный) отбор.

    Вероятность выбора особи пропорциональна её приспособленности,
    предварительно сдвинутой так, чтобы минимум стал малым положительным
    числом (приспособленность со штрафом может быть отрицательной).
    """
    shifted = fits - fits.min() + 1e-6
    p = shifted / shifted.sum()
    return int(rng.choice(len(fits), p=p))


def rank_selection(fits: np.ndarray, rng: np.random.Generator, **_) -> int:
    """Ранговый отбор: вероятность пропорциональна рангу особи (1 — худшая,
    P — лучшая). Устраняет доминирование «сверхособей» на ранних поколениях."""
    ranks = np.empty(len(fits))
    ranks[np.argsort(fits)] = np.arange(1, len(fits) + 1)
    return int(rng.choice(len(fits), p=ranks / ranks.sum()))


SELECTION = {
    "tournament": tournament_selection,
    "roulette": roulette_selection,
    "rank": rank_selection,
}


# ================================================================== СКРЕЩИВАНИЕ
def order_crossover(p1: list[int], p2: list[int], rng: np.random.Generator) -> list[int]:
    """Упорядоченное скрещивание (Order Crossover, OX).

    1. Случайно выбирается отрезок [i, j) и копируется из первого родителя
       в потомка на те же позиции.
    2. Оставшиеся позиции, начиная с j и по кругу, заполняются генами второго
       родителя в порядке их следования (также начиная с позиции j),
       пропуская уже скопированные гены.
    Потомок наследует от первого родителя фрагмент маршрута, а от второго —
    относительный порядок остальных клиентов. Результат — всегда перестановка.
    """
    n = len(p1)
    i, j = sorted(rng.choice(n + 1, size=2, replace=False))
    child = [None] * n
    child[i:j] = p1[i:j]
    taken = set(p1[i:j])
    fill = [p2[(j + k) % n] for k in range(n) if p2[(j + k) % n] not in taken]
    pos = j % n
    for g in fill:
        while child[pos] is not None:
            pos = (pos + 1) % n
        child[pos] = g
        pos = (pos + 1) % n
    return child


# ===================================================================== МУТАЦИИ
def swap_mutation(chrom: list[int], rng: np.random.Generator, n_clients: int) -> list[int]:
    """Обмен двух случайных генов (в т.ч. клиентов разных маршрутов)."""
    c = list(chrom)
    i, j = rng.choice(len(c), size=2, replace=False)
    c[i], c[j] = c[j], c[i]
    return c


def inversion_mutation(chrom: list[int], rng: np.random.Generator, n_clients: int) -> list[int]:
    """Инверсия случайного отрезка: порядок генов на нём меняется на обратный.

    Если отрезок лежит внутри одного маршрута, это аналог хода 2-opt —
    устраняет самопересечения маршрута.
    """
    c = list(chrom)
    i, j = sorted(rng.choice(len(c) + 1, size=2, replace=False))
    c[i:j] = c[i:j][::-1]
    return c


def transfer_mutation(chrom: list[int], rng: np.random.Generator, n_clients: int) -> list[int]:
    """Перенос клиента в другой маршрут: случайный клиент удаляется из своего
    маршрута и вставляется в случайную позицию другого маршрута.

    Меняет распределение заказов по машинам, не затрагивая порядок
    остальных клиентов (важно для выравнивания загрузки).
    """
    c = list(chrom)
    client_pos = [p for p, g in enumerate(c) if g <= n_clients]
    p = int(rng.choice(client_pos))
    gene = c.pop(p)
    # номера маршрутов: маршрут r — между (r−1)-м и r-м разделителем
    seps = [q for q, g in enumerate(c) if g > n_clients]
    bounds = [-1] + seps + [len(c)]
    own = sum(1 for q in seps if q < p)         # маршрут, из которого удалён клиент
    others = [r for r in range(len(bounds) - 1) if r != own]
    if not others:                               # единственная машина
        c.insert(p, gene)
        return c
    r = int(rng.choice(others))
    lo, hi = bounds[r] + 1, bounds[r + 1]        # допустимые позиции вставки [lo, hi]
    c.insert(int(rng.integers(lo, hi + 1)), gene)
    return c


MUTATIONS = (swap_mutation, inversion_mutation, transfer_mutation)


def mutate(chrom: list[int], rng: np.random.Generator, n_clients: int) -> list[int]:
    """Применяет один из трёх операторов мутации, выбранный равновероятно."""
    op = MUTATIONS[int(rng.integers(len(MUTATIONS)))]
    return op(chrom, rng, n_clients)
