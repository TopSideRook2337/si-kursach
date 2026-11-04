"""Базовые (неинтеллектуальные) методы для сравнения с гибридным ГА.

* ``random_solution`` — случайное решение (случайная хромосома);
* ``nearest_neighbor`` — жадная эвристика «ближайший сосед» с учётом вместимости;
* ``brute_force`` — полный перебор всех решений для малых N (N ≤ 8),
  даёт точный оптимум функции приспособленности для проверки ГА.
"""
from __future__ import annotations

import itertools
from typing import Callable

import numpy as np

from src.model import Instance


def random_solution(inst: Instance, rng: np.random.Generator) -> list[list[int]]:
    """Случайное решение: случайный порядок клиентов, случайно разрезанный на K маршрутов."""
    from src.ga.encoding import random_chromosome, decode
    return decode(random_chromosome(inst.n_clients, inst.n_vehicles, rng), inst.n_clients)


def nearest_neighbor(inst: Instance) -> list[list[int]]:
    """Жадный алгоритм «ближайший сосед».

    Машина выезжает со склада и каждый раз едет к ближайшему непосещённому
    клиенту, чей заказ ещё помещается в кузов. Когда таких нет — машина
    возвращается, и выезжает следующая. Если машины закончились, оставшиеся
    клиенты добавляются к наименее загруженной машине (возможен перегруз).
    Временные окна и срочность жадный алгоритм не учитывает — это
    классический ориентир по пробегу.
    """
    d = inst.dist
    unvisited = set(range(1, inst.n_clients + 1))
    routes: list[list[int]] = []
    for _ in range(inst.n_vehicles):
        route: list[int] = []
        load = 0
        cur = 0
        while True:
            cand = [c for c in unvisited if load + inst.clients[c - 1].demand <= inst.capacity]
            if not cand:
                break
            nxt = min(cand, key=lambda c: d[cur, c])
            route.append(nxt)
            load += inst.clients[nxt - 1].demand
            unvisited.remove(nxt)
            cur = nxt
        routes.append(route)
        if not unvisited:
            break
    while len(routes) < inst.n_vehicles:
        routes.append([])
    for c in sorted(unvisited):   # «хвост», не поместившийся в парк
        loads = [sum(inst.clients[x - 1].demand for x in r) for r in routes]
        routes[int(np.argmin(loads))].append(c)
    return routes


def randomized_nearest_neighbor(inst: Instance, rng: np.random.Generator,
                                rcl: int = 3) -> list[list[int]]:
    """Рандомизированный «ближайший сосед» (используется для «засева»
    части начальной популяции ГА): следующий клиент выбирается случайно
    среди ``rcl`` ближайших подходящих по вместимости. Даёт разнообразные
    решения приемлемого качества."""
    d = inst.dist
    unvisited = set(range(1, inst.n_clients + 1))
    routes: list[list[int]] = []
    for _ in range(inst.n_vehicles):
        route, load, cur = [], 0, 0
        while True:
            cand = [c for c in unvisited if load + inst.clients[c - 1].demand <= inst.capacity]
            if not cand:
                break
            cand.sort(key=lambda c: d[cur, c])
            nxt = cand[int(rng.integers(min(rcl, len(cand))))]
            route.append(nxt)
            load += inst.clients[nxt - 1].demand
            unvisited.remove(nxt)
            cur = nxt
        routes.append(route)
    for c in sorted(unvisited):
        loads = [sum(inst.clients[x - 1].demand for x in r) for r in routes]
        routes[int(np.argmin(loads))].append(c)
    return routes


def _canonical(routes: list[list[int]]) -> bool:
    """Проверка канонической формы: непустые маршруты упорядочены по первому
    клиенту, пустые — в конце. Машины одинаковы, поэтому перестановки
    маршрутов между машинами дают то же решение и отбрасываются."""
    seen_empty = False
    last_first = 0
    for r in routes:
        if not r:
            seen_empty = True
            continue
        if seen_empty or r[0] < last_first:
            return False
        last_first = r[0]
    return True


def iter_all_solutions(n_clients: int, n_vehicles: int):
    """Перечисляет все различные решения (с точностью до перенумерации машин)."""
    clients = list(range(1, n_clients + 1))
    for perm in itertools.permutations(clients):
        # точки разреза перестановки на K отрезков (отрезки могут быть пустыми)
        for cuts in itertools.combinations_with_replacement(range(n_clients + 1),
                                                            n_vehicles - 1):
            bounds = (0,) + cuts + (n_clients,)
            routes = [list(perm[bounds[i]:bounds[i + 1]]) for i in range(n_vehicles)]
            if _canonical(routes):
                yield routes


def brute_force(inst: Instance, fitness: Callable[[list[list[int]]], float]):
    """Полный перебор: возвращает (лучшие маршруты, лучшее значение, число решений).

    Пригоден только для N ≤ 8: число решений растёт как (N+K−1)!/K!.
    """
    best, best_val, count = None, -np.inf, 0
    for routes in iter_all_solutions(inst.n_clients, inst.n_vehicles):
        v = fitness(routes)
        count += 1
        if v > best_val:
            best, best_val = routes, v
    return best, best_val, count
