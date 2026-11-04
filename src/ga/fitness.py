"""Функции приспособленности для генетического алгоритма.

Главная — ``FuzzyFitness``: здесь и происходит гибридизация методов ИИ.
Для каждой особи каждого поколения ГА вызывает нечёткий вывод Мамдани,
и полученная оценка качества Q ∈ [0, 1] становится приспособленностью.

Для сравнения реализована ``WeightedSumFitness`` — та же схема, но вместо
нечёткого блока используется линейная взвешенная сумма тех же показателей.
"""
from __future__ import annotations

from src.baselines import nearest_neighbor
from src.fuzzy.mamdani import MamdaniInference, build_default_engine
from src.model import Instance, SolutionMetrics, evaluate_routes

# Штраф за перегруз: любое решение с перегрузом получает приспособленность
# не выше Q_max − 1 < 0, т.е. хуже любого допустимого решения (Q ≥ 0);
# слагаемое, пропорциональное величине перегруза, сохраняет «градиент»
# среди недопустимых решений, чтобы ГА мог выбираться из этой области.
OVERLOAD_BASE = 1.0
OVERLOAD_RATE = 1.0


def overload_penalty(m: SolutionMetrics, capacity: int) -> float:
    """Штраф за нарушение жёсткого ограничения вместимости."""
    if m.overload <= 0:
        return 0.0
    return OVERLOAD_BASE + OVERLOAD_RATE * m.overload / capacity


def fuzzy_inputs(m: SolutionMetrics, ref_distance: float) -> dict[str, float]:
    """Чёткие значения пяти входных лингвистических переменных."""
    return {
        "length": m.total_distance / ref_distance,
        "load": m.max_load_ratio,
        "timewin": m.lateness_index,
        "urgency": m.urgency_index,
        "balance": m.balance_cv,
    }


class FuzzyFitness:
    """Приспособленность = нечёткая оценка качества − штраф за перегруз.

    Эталонный пробег для нормировки «Протяжённости» — пробег жадного
    решения «ближайший сосед» на той же задаче (вычисляется один раз).
    Значения кэшируются: одинаковые особи (частые после элитизма и
    скрещивания похожих родителей) повторно не оцениваются.
    """

    name = "fuzzy"

    def __init__(self, inst: Instance, engine: MamdaniInference | None = None):
        self.inst = inst
        self.engine = engine or build_default_engine()
        self.ref_distance = evaluate_routes(nearest_neighbor(inst), inst).total_distance
        self.cache: dict[tuple, float] = {}
        self.evaluations = 0

    def quality(self, m: SolutionMetrics) -> float:
        """Нечёткая оценка Q (без штрафа) — вызов вывода Мамдани."""
        return self.engine.infer(fuzzy_inputs(m, self.ref_distance))

    def score(self, routes: list[list[int]]) -> float:
        """Приспособленность решения, заданного списком маршрутов."""
        m = evaluate_routes(routes, self.inst)
        return self.quality(m) - overload_penalty(m, self.inst.capacity)

    def __call__(self, chrom) -> float:
        from src.ga.encoding import decode
        key = tuple(chrom)
        val = self.cache.get(key)
        if val is None:                    # особь ещё не оценивалась
            self.evaluations += 1
            # хромосома → маршруты → метрики → нечёткий вывод Мамдани − штраф
            val = self.score(decode(chrom, self.inst.n_clients))
            self.cache[key] = val
        return val


class WeightedSumFitness(FuzzyFitness):
    """Альтернатива для сравнения: линейная свёртка тех же показателей.

    Q_ws = 1 − (w_L·s_L + w_T·s_T + w_U·s_U + w_B·s_B), где s — показатели,
    нормированные к [0, 1] по границам универсумов нечётких переменных.
    Перегруз штрафуется так же, как и в нечёткой схеме.
    """

    name = "weighted"
    WEIGHTS = {"length": 0.35, "timewin": 0.30, "urgency": 0.20, "balance": 0.15}

    def quality(self, m: SolutionMetrics) -> float:
        x = fuzzy_inputs(m, self.ref_distance)
        s = {}
        for k in self.WEIGHTS:
            lo, hi = self.engine.inputs[k].universe
            s[k] = (min(max(x[k], lo), hi) - lo) / (hi - lo)
        return 1.0 - sum(w * s[k] for k, w in self.WEIGHTS.items())
