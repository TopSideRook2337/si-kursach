"""Функции принадлежности нечётких множеств.

Реализованы треугольная и трапециевидная функции — самые распространённые
в нечётких системах: они задаются несколькими числами, легко
интерпретируются экспертом и быстро вычисляются.
Обе функции принимают как число, так и массив numpy.
"""
from __future__ import annotations

import numpy as np


class TrapezoidalMF:
    """Трапециевидная функция принадлежности с параметрами a ≤ b ≤ c ≤ d.

            0,               x ≤ a или x ≥ d
            (x − a)/(b − a), a < x < b      (левый склон)
    μ(x) =  1,               b ≤ x ≤ c      (ядро)
            (d − x)/(d − c), c < x < d      (правый склон)

    Если a = b (или c = d), левый (правый) склон вертикальный — так задаются
    «плечевые» термы на границах универсума (например, «короткая»).
    """

    def __init__(self, a: float, b: float, c: float, d: float):
        if not a <= b <= c <= d:
            raise ValueError(f"Нарушен порядок параметров: {a}, {b}, {c}, {d}")
        self.a, self.b, self.c, self.d = float(a), float(b), float(c), float(d)

    @property
    def params(self) -> tuple[float, ...]:
        return (self.a, self.b, self.c, self.d)

    def __call__(self, x):
        a, b, c, d = self.a, self.b, self.c, self.d
        if isinstance(x, (int, float)):           # быстрый путь для одного числа
            x = float(x)
            if x < a or x > d:
                return 0.0
            if x < b:
                return (x - a) / (b - a)
            if x <= c:
                return 1.0
            return (d - x) / (d - c)
        x = np.asarray(x, dtype=float)
        # левый склон (линейный рост); при a == b склон вертикальный
        left = (x - a) / (b - a) if b > a else np.where(x >= a, 1.0, 0.0)
        # правый склон (линейный спад); при c == d склон вертикальный
        right = (d - x) / (d - c) if d > c else np.where(x <= d, 1.0, 0.0)
        # в ядре оба склона ≥ 1, вне носителя один из них < 0 — обрезаем до [0, 1]
        mu = np.clip(np.minimum(left, right), 0.0, 1.0)
        return float(mu) if mu.ndim == 0 else mu

    def __repr__(self) -> str:
        return f"Trap({self.a:g}, {self.b:g}, {self.c:g}, {self.d:g})"


class TriangularMF(TrapezoidalMF):
    """Треугольная функция принадлежности с параметрами a ≤ b ≤ c.

    Частный случай трапеции с вырожденным ядром (b = c):
    μ(x) = max(0, min((x − a)/(b − a), (c − x)/(c − b))).
    """

    def __init__(self, a: float, b: float, c: float):
        super().__init__(a, b, b, c)

    @property
    def params(self) -> tuple[float, ...]:
        return (self.a, self.b, self.d)

    def __repr__(self) -> str:
        return f"Tri({self.a:g}, {self.b:g}, {self.d:g})"
