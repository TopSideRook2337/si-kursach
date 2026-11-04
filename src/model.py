"""Модель задачи маршрутизации транспорта с временными окнами (CVRPTW).

Содержит классы предметной области (клиент, транспортное средство, задача,
решение), расчёт матрицы расстояний, моделирование движения машины по
маршруту и вычисление метрик решения, которые затем подаются на вход
нечёткого блока оценки качества.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np


@dataclass
class Client:
    """Клиент (точка доставки).

    Атрибуты:
        id: номер клиента (1..N; 0 зарезервирован за складом).
        x, y: координаты на плоскости, км.
        demand: объём заказа, условные единицы груза.
        urgency: срочность заказа: 1 — обычный, 2 — повышенный, 3 — срочный.
        tw_start, tw_end: временное окно обслуживания, мин от начала смены.
        service: длительность обслуживания (разгрузки), мин.
    """
    id: int
    x: float
    y: float
    demand: int
    urgency: int
    tw_start: float
    tw_end: float
    service: float = 10.0


@dataclass
class Vehicle:
    """Транспортное средство (все машины парка одинаковы)."""
    id: int
    capacity: int


@dataclass
class Instance:
    """Экземпляр задачи: склад, клиенты, парк машин и параметры смены.

    Атрибуты:
        depot: координаты склада (x, y).
        clients: список клиентов; clients[i-1] имеет id = i.
        n_vehicles: число машин K.
        capacity: грузоподъёмность одной машины.
        speed: скорость движения, км/мин (постоянная).
        horizon: длительность смены, мин (склад закрывается).
        name: имя задачи (для файлов и отчётов).
    """
    depot: tuple[float, float]
    clients: list[Client]
    n_vehicles: int
    capacity: int
    speed: float = 0.5
    horizon: float = 480.0
    name: str = "instance"
    _dist: np.ndarray | None = field(default=None, repr=False, compare=False)

    @property
    def n_clients(self) -> int:
        return len(self.clients)

    @property
    def vehicles(self) -> list[Vehicle]:
        return [Vehicle(k, self.capacity) for k in range(self.n_vehicles)]

    @property
    def total_demand(self) -> int:
        return sum(c.demand for c in self.clients)

    def coords(self) -> np.ndarray:
        """Массив координат: строка 0 — склад, строка i — клиент i."""
        pts = [self.depot] + [(c.x, c.y) for c in self.clients]
        return np.asarray(pts, dtype=float)

    @property
    def dist(self) -> np.ndarray:
        """Матрица евклидовых расстояний (N+1)×(N+1), вычисляется один раз."""
        if self._dist is None:
            p = self.coords()
            diff = p[:, None, :] - p[None, :, :]
            self._dist = np.sqrt((diff ** 2).sum(axis=2))
        return self._dist

    # ---------- сериализация в JSON (для воспроизводимости экспериментов) ----------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "depot": list(self.depot),
            "n_vehicles": self.n_vehicles,
            "capacity": self.capacity,
            "speed": self.speed,
            "horizon": self.horizon,
            "clients": [asdict(c) for c in self.clients],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Instance":
        return cls(
            depot=tuple(d["depot"]),
            clients=[Client(**c) for c in d["clients"]],
            n_vehicles=d["n_vehicles"],
            capacity=d["capacity"],
            speed=d.get("speed", 0.5),
            horizon=d.get("horizon", 480.0),
            name=d.get("name", "instance"),
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Instance":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class RouteStats:
    """Показатели одного маршрута (одной машины)."""
    clients: list[int]
    distance: float
    load: int
    duration: float          # время возврата на склад, мин
    lateness: float          # суммарное опоздание, мин
    n_late: int              # число клиентов, обслуженных с опозданием
    arrivals: list[float]    # время начала обслуживания каждого клиента


@dataclass
class SolutionMetrics:
    """Сводные метрики решения — «сырьё» для нечёткой оценки качества."""
    total_distance: float
    total_lateness: float
    n_late: int
    overload: float          # суммарное превышение вместимости по всем машинам
    max_load_ratio: float    # максимальная загрузка машины, доля вместимости
    lateness_index: float    # средняя относительная величина опоздания [0..1]
    urgency_index: float     # средневзвешенное нормированное время прибытия к срочным
    balance_cv: float        # коэффициент вариации длительностей маршрутов
    n_used: int              # число задействованных машин
    routes: list[RouteStats]


# Эталонная величина опоздания для нормировки: опоздание на 60 мин и более
# считается «полным» (вклад клиента в индекс опозданий = 1).
LATENESS_REF = 60.0


@dataclass
class Solution:
    """Решение задачи: список маршрутов, каждый — последовательность id клиентов.

    Склад (0) в маршрутах не хранится: каждый маршрут начинается и
    заканчивается на складе неявно.
    """
    routes: list[list[int]]

    def evaluate(self, inst: Instance) -> SolutionMetrics:
        return evaluate_routes(self.routes, inst)

    def to_dict(self) -> dict:
        return {"routes": self.routes}


def simulate_route(route: list[int], inst: Instance) -> RouteStats:
    """Моделирует движение машины по маршруту склад → клиенты → склад.

    Если машина приезжает раньше начала окна, она ждёт; если позже конца
    окна — фиксируется опоздание (окна мягкие).
    """
    d = inst.dist
    t = 0.0
    prev = 0
    dist = 0.0
    load = 0
    late = 0.0
    n_late = 0
    arrivals = []
    for cid in route:
        c = inst.clients[cid - 1]
        leg = float(d[prev, cid])
        dist += leg
        t += leg / inst.speed
        if t < c.tw_start:            # ожидание открытия окна
            t = c.tw_start
        arrivals.append(t)
        if t > c.tw_end:              # опоздание
            late += t - c.tw_end
            n_late += 1
        t += c.service
        load += c.demand
        prev = cid
    if route:
        leg = float(d[prev, 0])
        dist += leg
        t += leg / inst.speed
    return RouteStats(list(route), float(dist), load, t if route else 0.0, late, n_late,
                      arrivals)


def evaluate_routes(routes: list[list[int]], inst: Instance) -> SolutionMetrics:
    """Вычисляет все метрики решения, используемые нечёткой моделью."""
    stats = [simulate_route(r, inst) for r in routes]
    cap = inst.capacity
    total_dist = sum(s.distance for s in stats)
    total_late = sum(s.lateness for s in stats)
    n_late = sum(s.n_late for s in stats)
    overload = sum(max(0, s.load - cap) for s in stats)
    max_load = max((s.load for s in stats), default=0) / cap

    # Индекс опозданий: среднее по клиентам min(1, опоздание / 60 мин).
    lat_sum = 0.0
    # Индекс срочности: средневзвешенное (вес = urgency − 1) время начала
    # обслуживания, нормированное к длительности смены.
    urg_num = 0.0
    urg_den = 0.0
    for s in stats:
        for cid, t in zip(s.clients, s.arrivals):
            c = inst.clients[cid - 1]
            if t > c.tw_end:
                lat_sum += min(1.0, (t - c.tw_end) / LATENESS_REF)
            w = c.urgency - 1
            if w > 0:
                urg_num += w * min(1.0, t / inst.horizon)
                urg_den += w
    n = max(1, inst.n_clients)
    lateness_index = lat_sum / n
    urgency_index = urg_num / urg_den if urg_den > 0 else 0.0

    # Сбалансированность: коэффициент вариации длительностей маршрутов
    # (по всем K машинам, неиспользуемая машина имеет длительность 0).
    durs = np.array([s.duration for s in stats], dtype=float)
    if len(durs) < inst.n_vehicles:
        durs = np.concatenate([durs, np.zeros(inst.n_vehicles - len(durs))])
    mean = durs.mean() if len(durs) else 0.0
    cv = float(durs.std() / mean) if mean > 0 else 0.0

    return SolutionMetrics(
        total_distance=float(total_dist),
        total_lateness=float(total_late),
        n_late=n_late,
        overload=float(overload),
        max_load_ratio=float(max_load),
        lateness_index=lateness_index,
        urgency_index=urgency_index,
        balance_cv=cv,
        n_used=sum(1 for r in routes if r),
        routes=stats,
    )


def solution_space_size(n_clients: int, n_vehicles: int) -> float:
    """Число различных хромосом (перестановка N клиентов и K−1 одинаковых
    разделителей): (N+K−1)! / (K−1)!. Возвращается как float из-за роста."""
    return math.factorial(n_clients + n_vehicles - 1) / math.factorial(n_vehicles - 1)
