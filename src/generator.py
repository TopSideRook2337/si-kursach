"""Генератор тестовых задач маршрутизации с фиксированным seed.

Задачи генерируются программно (никаких внешних датасетов), а результат
сохраняется в JSON — это делает эксперименты воспроизводимыми.
"""
from __future__ import annotations

import math

import numpy as np

from src.model import Client, Instance

AREA = 40.0          # сторона квадратной области обслуживания, км
SPEED = 0.5          # скорость, км/мин (30 км/ч — городской режим)
HORIZON = 480.0      # смена 8 часов, мин
SERVICE = 10.0       # время разгрузки у клиента, мин
FILL = 0.85          # целевая доля использования суммарной вместимости парка


def default_vehicles(n_clients: int) -> int:
    """Число машин по умолчанию: примерно одна машина на 7 клиентов, не меньше 2."""
    return max(2, round(n_clients / 7))


def _reference_routes(pts, demands, urgency, depot, k):
    """Строит «скрытое» опорное решение методом заметания (sweep).

    Клиенты сортируются по полярному углу относительно склада и режутся на
    K секторов с примерно равным суммарным объёмом. Внутри сектора сначала
    объезжаются срочные клиенты, затем остальные — по ближайшему соседу.
    По времени прибытия в этом решении строятся временные окна, поэтому
    задача заведомо имеет решение без опозданий (но найти его непросто).
    """
    n = len(pts)
    ang = np.arctan2(pts[:, 1] - depot[1], pts[:, 0] - depot[0])
    order = np.argsort(ang)
    cum = np.cumsum(demands[order])
    total = cum[-1]
    groups = [[] for _ in range(k)]
    for idx, cs in zip(order, cum):
        g = min(k - 1, int((cs - 1e-9) / total * k))
        groups[g].append(int(idx))
    routes = []
    for g in groups:
        route, cur = [], np.asarray(depot)
        for prio in (True, False):
            rest = [i for i in g if (urgency[i] == 3) == prio]
            while rest:
                nxt = min(rest, key=lambda i: np.hypot(*(pts[i] - cur)))
                route.append(nxt)
                rest.remove(nxt)
                cur = pts[nxt]
        routes.append(route)
    return routes


def generate_instance(n_clients: int, n_vehicles: int | None = None, seed: int = 0,
                      name: str | None = None) -> Instance:
    """Генерирует экземпляр задачи CVRPTW.

    Аргументы:
        n_clients: число клиентов N.
        n_vehicles: число машин K (по умолчанию round(N/7), но не меньше 2).
        seed: зерно генератора случайных чисел.

    Правила генерации:
        * склад — в центре области, клиенты — равномерно в квадрате AREA×AREA;
        * объём заказа — целое 1..10;
        * срочность: 1 — обычный (60 %), 2 — повышенный (25 %), 3 — срочный (15 %);
        * временные окна строятся вокруг времени прибытия в скрытом опорном
          решении (см. ``_reference_routes``): у срочных окно открыто с начала
          смены и закрывается вскоре после опорного прибытия, у остальных окно
          охватывает опорное прибытие с запасом;
        * вместимость машины подобрана так, чтобы парк был загружен на ~85 %.
    """
    if n_vehicles is None:
        n_vehicles = default_vehicles(n_clients)
    rng = np.random.default_rng(seed)
    depot = (AREA / 2, AREA / 2)
    pts = rng.uniform(0, AREA, size=(n_clients, 2))
    demands = rng.integers(1, 11, size=n_clients)
    urgency = rng.choice([1, 2, 3], size=n_clients, p=[0.60, 0.25, 0.15])

    # время начала обслуживания каждого клиента в опорном решении
    ref_time = np.zeros(n_clients)
    for route in _reference_routes(pts, demands, urgency, depot, n_vehicles):
        t, cur = 0.0, np.asarray(depot)
        for i in route:
            t += float(np.hypot(*(pts[i] - cur))) / SPEED
            ref_time[i] = t
            t += SERVICE
            cur = pts[i]

    clients = []
    for i in range(n_clients):
        a = ref_time[i]
        if urgency[i] == 3:
            start, end = 0.0, a + rng.uniform(15, 45)
        elif urgency[i] == 2:
            start, end = max(0.0, a - rng.uniform(60, 120)), a + rng.uniform(20, 60)
        else:
            start, end = max(0.0, a - rng.uniform(60, 150)), a + rng.uniform(30, 90)
        clients.append(Client(i + 1, round(float(pts[i, 0]), 2), round(float(pts[i, 1]), 2),
                              int(demands[i]), int(urgency[i]),
                              round(float(start), 1), round(float(end), 1), SERVICE))
    total = int(demands.sum())
    capacity = max(int(demands.max()), math.ceil(total / (n_vehicles * FILL)))
    return Instance(depot=depot, clients=clients, n_vehicles=n_vehicles, capacity=capacity,
                    speed=SPEED, horizon=HORIZON,
                    name=name or f"N{n_clients}_K{n_vehicles}_s{seed}")
