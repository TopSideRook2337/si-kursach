"""Кодирование решения в хромосому и обратно.

Хромосома — перестановка длины N+K−1 из чисел 1..N+K−1:
    * гены 1..N — номера клиентов (порядок объезда);
    * гены N+1..N+K−1 — разделители между маршрутами машин.

Пример (N=6, K=3, разделители 7 и 8):
    [3, 1, 7, 6, 2, 8, 5, 4]  →  машина 1: 3→1, машина 2: 6→2, машина 3: 5→4

Так одна хромосома одновременно задаёт и распределение заказов по машинам,
и порядок объезда внутри каждого маршрута.
"""
from __future__ import annotations

import numpy as np


def is_separator(gene: int, n_clients: int) -> bool:
    return gene > n_clients


def decode(chrom, n_clients: int) -> list[list[int]]:
    """Хромосома → список маршрутов (разрезание по разделителям)."""
    routes: list[list[int]] = [[]]
    for g in chrom:
        if g > n_clients:
            routes.append([])
        else:
            routes[-1].append(int(g))
    return routes


def encode(routes: list[list[int]], n_clients: int) -> list[int]:
    """Список маршрутов → хромосома (маршруты, склеенные через разделители)."""
    chrom: list[int] = []
    sep = n_clients + 1
    for i, r in enumerate(routes):
        if i > 0:
            chrom.append(sep)
            sep += 1
        chrom.extend(r)
    return chrom


def random_chromosome(n_clients: int, n_vehicles: int,
                      rng: np.random.Generator) -> list[int]:
    """Случайная хромосома: случайная перестановка клиентов и разделителей."""
    genes = np.arange(1, n_clients + n_vehicles)
    rng.shuffle(genes)
    return genes.tolist()


def is_valid(chrom, n_clients: int, n_vehicles: int) -> bool:
    """Проверка, что хромосома — перестановка 1..N+K−1 (каждый ген ровно один раз)."""
    return sorted(chrom) == list(range(1, n_clients + n_vehicles))
