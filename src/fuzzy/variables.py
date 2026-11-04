"""Лингвистические переменные нечёткой модели оценки качества маршрутов.

Лингвистическая переменная — это переменная, значениями которой являются
слова (термы), например «короткая», «средняя», «длинная». Каждый терм —
нечёткое множество на универсуме (числовой области определения) с
собственной функцией принадлежности.

Пять входных переменных описывают решение задачи маршрутизации целиком,
одна выходная — его итоговое качество.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.fuzzy.membership import TrapezoidalMF, TriangularMF


@dataclass
class Term:
    """Терм лингвистической переменной: имя, подпись и функция принадлежности."""
    name: str
    label: str
    mf: TrapezoidalMF


@dataclass
class LinguisticVariable:
    """Лингвистическая переменная.

    Атрибуты:
        name: идентификатор в программе (латиница).
        title: название для человека («Протяжённость»).
        universe: границы универсума (min, max).
        terms: термы переменной в порядке «от хорошего к плохому» или по возрастанию.
        description: как вычисляется чёткое значение.
    """
    name: str
    title: str
    universe: tuple[float, float]
    terms: dict[str, Term] = field(default_factory=dict)
    description: str = ""

    def add(self, name: str, label: str, mf: TrapezoidalMF) -> "LinguisticVariable":
        self.terms[name] = Term(name, label, mf)
        return self

    def clip(self, x: float) -> float:
        """Приведение чёткого значения к границам универсума."""
        lo, hi = self.universe
        return min(max(x, lo), hi)

    def fuzzify(self, x: float) -> dict[str, float]:
        """Фаззификация: степени принадлежности x ко всем термам переменной."""
        x = self.clip(x)
        return {t.name: float(t.mf(x)) for t in self.terms.values()}


def make_input_variables() -> dict[str, LinguisticVariable]:
    """Создаёт пять входных лингвистических переменных.

    Параметры функций принадлежности подобраны по диапазонам значений,
    наблюдаемым на сгенерированных задачах (от случайных решений до
    решений без опозданий). Соседние термы образуют разбиение Руспини:
    склоны соседних термов пересекаются на уровне 0,5, сумма степеней
    принадлежности равна 1. Поэтому почти любое значение принадлежит
    сразу двум термам, и оценка качества меняется плавно — у ГА нет
    «плато», на которых приспособленность не реагирует на улучшения.
    """
    length = LinguisticVariable(
        "length", "Протяжённость", (0.6, 2.6),
        description="суммарный пробег, делённый на пробег жадного решения "
                    "«ближайший сосед» (1,0 — как у жадного алгоритма)")
    length.add("short", "короткая", TrapezoidalMF(0.6, 0.6, 0.8, 1.1))
    length.add("medium", "средняя", TriangularMF(0.8, 1.1, 1.6))
    length.add("long", "длинная", TrapezoidalMF(1.1, 1.6, 2.6, 2.6))

    load = LinguisticVariable(
        "load", "Загрузка транспорта", (0.0, 2.0),
        description="максимальная загрузка машины в долях от вместимости")
    load.add("low", "низкая", TrapezoidalMF(0.0, 0.0, 0.5, 0.8))
    load.add("normal", "нормальная", TrapezoidalMF(0.5, 0.8, 1.0, 1.1))
    load.add("over", "перегрузка", TrapezoidalMF(1.0, 1.1, 2.0, 2.0))

    tw = LinguisticVariable(
        "timewin", "Соблюдение временных окон", (0.0, 1.0),
        description="средняя по клиентам величина min(1, опоздание / 60 мин)")
    tw.add("good", "хорошее", TriangularMF(0.0, 0.0, 0.12))
    tw.add("fair", "удовлетворительное", TriangularMF(0.0, 0.12, 0.45))
    tw.add("poor", "плохое", TrapezoidalMF(0.12, 0.45, 1.0, 1.0))

    urg = LinguisticVariable(
        "urgency", "Обслуживание срочных заказов", (0.0, 1.0),
        description="средневзвешенное по срочности время начала обслуживания "
                    "срочных клиентов, делённое на длительность смены")
    urg.add("good", "хорошее", TrapezoidalMF(0.0, 0.0, 0.05, 0.25))
    urg.add("medium", "среднее", TriangularMF(0.05, 0.25, 0.5))
    urg.add("poor", "плохое", TrapezoidalMF(0.25, 0.5, 1.0, 1.0))

    bal = LinguisticVariable(
        "balance", "Сбалансированность", (0.0, 1.5),
        description="коэффициент вариации длительностей маршрутов машин")
    bal.add("even", "равномерная", TrapezoidalMF(0.0, 0.0, 0.05, 0.4))
    bal.add("uneven", "неравномерная", TrapezoidalMF(0.05, 0.4, 1.5, 1.5))

    return {v.name: v for v in (length, load, tw, urg, bal)}


def make_output_variable() -> LinguisticVariable:
    """Выходная переменная «Качество решения» на универсуме [0, 1]."""
    q = LinguisticVariable("quality", "Качество решения", (0.0, 1.0),
                           description="интегральная оценка плана маршрутов")
    q.add("very_low", "очень низкое", TriangularMF(0.0, 0.0, 0.25))
    q.add("low", "низкое", TriangularMF(0.0, 0.25, 0.5))
    q.add("medium", "среднее", TriangularMF(0.25, 0.5, 0.75))
    q.add("high", "высокое", TriangularMF(0.5, 0.75, 1.0))
    q.add("very_high", "очень высокое", TriangularMF(0.75, 1.0, 1.0))
    return q
