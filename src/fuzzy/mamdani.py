"""Механизм нечёткого логического вывода по алгоритму Мамдани.

Этапы (по методическим указаниям, раздел 3.3.2):
    1. Формирование базы правил       — конструктор MamdaniInference;
    2. Фаззификация входных переменных — fuzzify:     b_i = μ(a_i);
    3. Агрегирование подусловий         — aggregate:   c_j = min{b_i};
    4. Активизация подзаключений        — activate:    d_j = c_j·F_j,
                                                       μ'_j(x) = min{d_j, μ_j(x)};
    5. Аккумуляция заключений           — accumulate:  μ_E(x) = max_j μ'_j(x);
    6. Дефаззификация (центр тяжести)   — defuzzify:   y = ∫x·μ_E(x)dx / ∫μ_E(x)dx.

Универсум выходной переменной дискретизируется сеткой из ``resolution``
точек, интегралы центра тяжести заменяются суммами (метод прямоугольников).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.fuzzy.rules import Rule
from src.fuzzy.variables import LinguisticVariable


@dataclass
class InferenceTrace:
    """Полный протокол одного нечёткого вывода (для отчёта и GUI)."""
    inputs: dict[str, float]                       # чёткие входные значения a_i
    fuzzified: dict[str, dict[str, float]]         # b: переменная → терм → μ
    strengths: list[float]                          # c_j — степень истинности условий
    activations: list[float]                        # d_j = c_j · F_j
    grid: np.ndarray                                # сетка универсума выхода
    activated_sets: np.ndarray                      # μ'_j(x), матрица n_rules × len(grid)
    accumulated: np.ndarray                         # μ_E(x)
    output: float                                   # y — результат дефаззификации


class MamdaniInference:
    """Нечёткая система вывода Мамдани с одной выходной переменной."""

    def __init__(self, inputs: dict[str, LinguisticVariable], output: LinguisticVariable,
                 rules: list[Rule], resolution: int = 201):
        # Этап 1. Формирование базы правил: проверяем, что все переменные и
        # термы, упомянутые в правилах, существуют.
        for j, r in enumerate(rules, 1):
            for v, t in r.conditions:
                if v not in inputs or t not in inputs[v].terms:
                    raise ValueError(f"Правило {j}: неизвестный терм {v}={t}")
            if r.conclusion not in output.terms:
                raise ValueError(f"Правило {j}: неизвестный выходной терм {r.conclusion}")
        self.inputs = inputs
        self.output = output
        self.rules = rules
        lo, hi = output.universe
        self.grid = np.linspace(lo, hi, resolution)
        # Функции принадлежности термов-заключений, заранее вычисленные на
        # сетке: строка j — μ терма из заключения правила j.
        self._concl_mf = np.vstack([output.terms[r.conclusion].mf(self.grid) for r in rules])
        self._weights = np.array([r.weight for r in rules])

    # ------------------------------------------------------------------ этапы
    def fuzzify(self, values: dict[str, float]) -> dict[str, dict[str, float]]:
        """Этап 2. Фаззификация: для каждой входной переменной вычисляются
        степени принадлежности её чёткого значения ко всем термам."""
        return {name: var.fuzzify(values[name]) for name, var in self.inputs.items()}

    def aggregate(self, fuzz: dict[str, dict[str, float]]) -> np.ndarray:
        """Этап 3. Агрегирование подусловий: степень истинности условия
        правила равна минимуму степеней истинности его подусловий (нечёткое «И»)."""
        return np.array([min(fuzz[v][t] for v, t in r.conditions) for r in self.rules])

    def activate(self, c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Этап 4. Активизация: d_j = c_j·F_j; функция принадлежности
        заключения «срезается» на уровне d_j (min-активизация)."""
        d = c * self._weights
        activated = np.minimum(d[:, None], self._concl_mf)
        return d, activated

    @staticmethod
    def accumulate(activated: np.ndarray) -> np.ndarray:
        """Этап 5. Аккумуляция: объединение (max) всех активизированных множеств."""
        return activated.max(axis=0)

    def defuzzify(self, mu: np.ndarray) -> float:
        """Этап 6. Дефаззификация методом центра тяжести.

        Если ни одно правило не сработало (площадь равна нулю), возвращается
        0 — худшая оценка. При полной базе правил такого не происходит.
        """
        area = mu.sum()
        if area <= 1e-12:
            return 0.0
        return float((self.grid * mu).sum() / area)

    # ------------------------------------------------------------- вывод целиком
    def infer(self, values: dict[str, float]) -> float:
        """Чёткие входы → чёткая оценка качества (этапы 2–6)."""
        fuzz = self.fuzzify(values)
        c = self.aggregate(fuzz)
        _, activated = self.activate(c)
        return self.defuzzify(self.accumulate(activated))

    def trace(self, values: dict[str, float]) -> InferenceTrace:
        """То же, что infer, но с сохранением всех промежуточных результатов."""
        fuzz = self.fuzzify(values)
        c = self.aggregate(fuzz)
        d, activated = self.activate(c)
        acc = self.accumulate(activated)
        return InferenceTrace(dict(values), fuzz, c.tolist(), d.tolist(), self.grid,
                              activated, acc, self.defuzzify(acc))


def build_default_engine(resolution: int = 201) -> MamdaniInference:
    """Создаёт систему вывода с переменными и базой правил по умолчанию."""
    from src.fuzzy.rules import RULES
    from src.fuzzy.variables import make_input_variables, make_output_variable
    return MamdaniInference(make_input_variables(), make_output_variable(), RULES, resolution)
