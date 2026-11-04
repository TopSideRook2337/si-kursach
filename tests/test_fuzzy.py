"""Тесты нечёткого блока: функции принадлежности и этапы вывода Мамдани
на ручном примере, который можно пересчитать на бумаге."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fuzzy.membership import TrapezoidalMF, TriangularMF  # noqa: E402
from src.fuzzy.variables import (LinguisticVariable, make_input_variables,  # noqa: E402
                                 make_output_variable)
from src.fuzzy.rules import RULES, Rule  # noqa: E402
from src.fuzzy.mamdani import MamdaniInference, build_default_engine  # noqa: E402


# ---------------------------------------------------------------- функции принадлежности
def test_triangular_points():
    mf = TriangularMF(0, 1, 2)
    assert mf(-1) == 0.0
    assert mf(0) == 0.0
    assert mf(0.5) == pytest.approx(0.5)
    assert mf(1) == 1.0
    assert mf(1.5) == pytest.approx(0.5)
    assert mf(2) == 0.0
    assert mf(3) == 0.0


def test_trapezoidal_points():
    mf = TrapezoidalMF(0, 1, 3, 4)
    assert mf(0.25) == pytest.approx(0.25)
    assert mf(1) == 1.0 and mf(2) == 1.0 and mf(3) == 1.0
    assert mf(3.5) == pytest.approx(0.5)
    assert mf(5) == 0.0


def test_shoulder_terms():
    left = TrapezoidalMF(0, 0, 1, 2)       # левое «плечо»
    right = TriangularMF(0.75, 1, 1)       # правое «плечо»
    assert left(0) == 1.0
    assert left(1.5) == pytest.approx(0.5)
    assert right(1.0) == 1.0
    assert right(0.875) == pytest.approx(0.5)


def test_vectorized_matches_scalar():
    mf = TrapezoidalMF(0.2, 0.4, 0.6, 0.9)
    xs = np.linspace(0, 1, 37)
    vec = mf(xs)
    assert np.allclose(vec, [mf(float(x)) for x in xs])


def test_bad_params():
    with pytest.raises(ValueError):
        TrapezoidalMF(1, 0, 2, 3)


def test_term_partitions_overlap():
    """Соседние термы каждой входной переменной перекрываются: в любой точке
    универсума хотя бы один терм имеет ненулевую принадлежность."""
    for var in make_input_variables().values():
        lo, hi = var.universe
        for x in np.linspace(lo, hi, 401):
            assert max(var.fuzzify(float(x)).values()) > 0, (var.name, x)


# ---------------------------------------------------------------- ручной пример Мамдани
@pytest.fixture
def toy():
    """Две входные переменные, одна выходная, два правила.

    x: «мало» = Trap(0,0,2,6), «много» = Trap(2,6,10,10)
    y: «плохо» = Tri(0,0,1),   «хорошо» = Tri(0,1,1)
    Выход q на [0,1]: «низкое» = Tri(0,0,1), «высокое» = Tri(0,1,1)

    П1: ЕСЛИ x=мало И y=хорошо ТО q=высокое (F=1.0)
    П2: ЕСЛИ x=много          ТО q=низкое  (F=0.8)
    """
    x = LinguisticVariable("x", "X", (0, 10))
    x.add("few", "мало", TrapezoidalMF(0, 0, 2, 6)).add("many", "много", TrapezoidalMF(2, 6, 10, 10))
    y = LinguisticVariable("y", "Y", (0, 1))
    y.add("bad", "плохо", TriangularMF(0, 0, 1)).add("good", "хорошо", TriangularMF(0, 1, 1))
    q = LinguisticVariable("q", "Q", (0, 1))
    q.add("low", "низкое", TriangularMF(0, 0, 1)).add("high", "высокое", TriangularMF(0, 1, 1))
    rules = [Rule((("x", "few"), ("y", "good")), "high", 1.0, ""),
             Rule((("x", "many"),), "low", 0.8, "")]
    return MamdaniInference({"x": x, "y": y}, q, rules, resolution=10001)


def test_toy_fuzzification(toy):
    # x = 3: мало = (6−3)/(6−2) = 0,75; много = (3−2)/(6−2) = 0,25
    # y = 0,6: плохо = 0,4; хорошо = 0,6
    b = toy.fuzzify({"x": 3.0, "y": 0.6})
    assert b["x"]["few"] == pytest.approx(0.75)
    assert b["x"]["many"] == pytest.approx(0.25)
    assert b["y"]["good"] == pytest.approx(0.6)
    assert b["y"]["bad"] == pytest.approx(0.4)


def test_toy_aggregation_and_activation(toy):
    b = toy.fuzzify({"x": 3.0, "y": 0.6})
    c = toy.aggregate(b)
    # c1 = min(0,75; 0,6) = 0,6;  c2 = 0,25
    assert c.tolist() == pytest.approx([0.6, 0.25])
    d, activated = toy.activate(c)
    # d1 = 0,6·1,0 = 0,6;  d2 = 0,25·0,8 = 0,2
    assert d.tolist() == pytest.approx([0.6, 0.2])
    # активизированное множество П1 срезано на уровне 0,6
    assert activated[0].max() == pytest.approx(0.6)
    assert activated[1].max() == pytest.approx(0.2)


def test_toy_accumulation_and_defuzzification(toy):
    trace = toy.trace({"x": 3.0, "y": 0.6})
    # аккумуляция: max двух срезанных треугольников
    g = trace.grid
    expected = np.maximum(np.minimum(0.6, g), np.minimum(0.2, 1 - g))
    assert np.allclose(trace.accumulated, expected)
    # аналитический центр тяжести полученной фигуры
    num = np.trapezoid(g * expected, g) if hasattr(np, "trapezoid") else np.trapz(g * expected, g)
    den = np.trapezoid(expected, g) if hasattr(np, "trapezoid") else np.trapz(expected, g)
    assert trace.output == pytest.approx(num / den, abs=1e-3)
    # перевес правила П1 («высокое», 0,6 против 0,2) смещает центр тяжести вправо
    assert trace.output > 0.5


def test_single_rule_centroid(toy):
    """Срабатывает только П2 («низкое», d = 1·0,8 = 0,8). Фигура μ(x) = min(0,8; 1−x):
    площадь S = 0,8·0,2 + 0,8²/2 = 0,48;
    момент M = 0,8·0,2²/2 + [x²/2 − x³/3] от 0,2 до 1 = 0,016 + 0,149333 = 0,165333;
    центр тяжести y = M/S ≈ 0,3444."""
    y = toy.infer({"x": 10.0, "y": 0.0})
    assert y == pytest.approx(0.165333 / 0.48, abs=1e-3)


def test_no_rule_fired_returns_zero(toy):
    # x = 10 (мало = 0) и правило П2 удалено: ничего не срабатывает
    toy.rules = toy.rules[:1]
    toy._concl_mf = toy._concl_mf[:1]
    toy._weights = toy._weights[:1]
    assert toy.infer({"x": 10.0, "y": 1.0}) == 0.0


# ---------------------------------------------------------------- модель по умолчанию
def test_rule_base_size_and_weights():
    assert 20 <= len(RULES) <= 30
    assert all(0 < r.weight <= 1 for r in RULES)
    assert all(r.explanation for r in RULES)


def test_rule_base_complete():
    """При любых входах срабатывает хотя бы одно правило (выход определён)."""
    eng = build_default_engine()
    rng = np.random.default_rng(1)
    for _ in range(500):
        vals = {n: float(rng.uniform(*v.universe)) for n, v in eng.inputs.items()}
        assert eng.aggregate(eng.fuzzify(vals)).max() > 0


def test_quality_monotonic_examples():
    eng = build_default_engine()
    ideal = {"length": 0.85, "load": 0.9, "timewin": 0.0, "urgency": 0.05, "balance": 0.1}
    bad = {"length": 2.2, "load": 0.9, "timewin": 0.6, "urgency": 0.7, "balance": 0.9}
    over = dict(ideal, load=1.6)
    q_ideal, q_bad, q_over = eng.infer(ideal), eng.infer(bad), eng.infer(over)
    assert q_ideal > 0.75
    assert q_bad < 0.25
    assert q_over < q_ideal
    # ухудшение одного показателя не повышает оценку
    assert eng.infer(dict(ideal, timewin=0.3)) < q_ideal
    assert eng.infer(dict(ideal, length=1.6)) < q_ideal


def test_output_variable_terms():
    q = make_output_variable()
    assert list(q.terms) == ["very_low", "low", "medium", "high", "very_high"]
