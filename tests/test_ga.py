"""Тесты генетического алгоритма: кодирование, операторы, интеграция с
нечёткой оценкой, сравнение с полным перебором."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.baselines import brute_force, iter_all_solutions, nearest_neighbor  # noqa: E402
from src.generator import generate_instance  # noqa: E402
from src.ga.encoding import decode, encode, is_valid, random_chromosome  # noqa: E402
from src.ga.engine import GAConfig, run_ga  # noqa: E402
from src.ga.fitness import FuzzyFitness, WeightedSumFitness  # noqa: E402
from src.ga.operators import (inversion_mutation, order_crossover, rank_selection,  # noqa: E402
                              roulette_selection, swap_mutation, tournament_selection,
                              transfer_mutation)
from src.model import Instance, evaluate_routes, solution_space_size  # noqa: E402

N, K = 8, 3


@pytest.fixture
def rng():
    return np.random.default_rng(42)


# ------------------------------------------------------------------ кодирование
def test_decode_example():
    # N = 6, K = 3: разделители 7 и 8
    assert decode([3, 1, 7, 6, 2, 8, 5, 4], 6) == [[3, 1], [6, 2], [5, 4]]
    assert decode([7, 1, 2, 3, 8, 4, 5, 6], 6) == [[], [1, 2, 3], [4, 5, 6]]


def test_encode_decode_roundtrip(rng):
    for _ in range(50):
        ch = random_chromosome(N, K, rng)
        routes = decode(ch, N)
        assert len(routes) == K
        assert decode(encode(routes, N), N) == routes
        assert sorted(sum(routes, [])) == list(range(1, N + 1))


# -------------------------------------------------------------------- скрещивание
def test_ox_valid_and_keeps_segment(rng):
    for _ in range(200):
        p1, p2 = random_chromosome(N, K, rng), random_chromosome(N, K, rng)
        child = order_crossover(p1, p2, rng)
        assert is_valid(child, N, K)


def test_ox_manual_example():
    """Классический пример OX: отрезок [3, 6) берётся из p1, остальные гены —
    из p2 в порядке, начиная с позиции 6."""
    class FixedRng:
        def choice(self, n, size, replace):
            return np.array([3, 6])
    p1 = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    p2 = [9, 3, 7, 8, 2, 6, 5, 1, 4]
    child = order_crossover(p1, p2, FixedRng())
    # из p2, начиная с позиции 6: 5,1,4,9,3,7,8,2,6 → без 4,5,6: 1,9,3,7,8,2;
    # они заполняют позиции 6,7,8,0,1,2
    assert child == [7, 8, 2, 4, 5, 6, 1, 9, 3]


# ------------------------------------------------------------------------- мутации
@pytest.mark.parametrize("op", [swap_mutation, inversion_mutation, transfer_mutation])
def test_mutations_valid(op, rng):
    for _ in range(200):
        ch = random_chromosome(N, K, rng)
        m = op(ch, rng, N)
        assert is_valid(m, N, K)
        assert m != ch or op is inversion_mutation  # инверсия отрезка длины 1 не меняет


def test_transfer_moves_client_to_other_route(rng):
    ch = encode([[1, 2, 3], [4, 5], [6, 7, 8]], N)
    for _ in range(100):
        before = {c: i for i, r in enumerate(decode(ch, N)) for c in r}
        after_routes = decode(transfer_mutation(ch, rng, N), N)
        after = {c: i for i, r in enumerate(after_routes) for c in r}
        moved = [c for c in before if before[c] != after[c]]
        assert len(moved) == 1


# ---------------------------------------------------------------------------- отбор
def test_tournament_full_picks_best(rng):
    fits = np.array([0.1, 0.9, 0.3, -1.0])
    # турнир из большого числа участников почти наверняка содержит лучшую
    assert tournament_selection(fits, rng, k=50) == 1


@pytest.mark.parametrize("sel", [roulette_selection, rank_selection])
def test_proportional_selection_prefers_better(sel, rng):
    fits = np.array([-2.0, 0.1, 0.5, 0.9])
    counts = np.bincount([sel(fits, rng) for _ in range(4000)], minlength=4)
    assert counts[3] > counts[1] > counts[0]


# ------------------------------------------------------- приспособленность и ГА
@pytest.fixture(scope="module")
def small():
    return generate_instance(N, 2, seed=5)


def test_overload_penalty_dominates(small):
    f = FuzzyFitness(small)
    feasible = nearest_neighbor(small)
    assert evaluate_routes(feasible, small).overload == 0
    overloaded = [sum(feasible, []), []]          # все клиенты в одной машине
    assert evaluate_routes(overloaded, small).overload > 0
    assert f.score(overloaded) < 0 <= f.score(feasible)


def test_fitness_cache(small, rng):
    f = FuzzyFitness(small)
    ch = random_chromosome(small.n_clients, small.n_vehicles, rng)
    v1 = f(ch)
    v2 = f(list(ch))
    assert v1 == v2 and f.evaluations == 1


def test_ga_returns_valid_and_improves(small):
    f = FuzzyFitness(small)
    res = run_ga(small, f, GAConfig(pop_size=40, generations=60, seed=1))
    assert is_valid(encode(res.best_routes, small.n_clients), small.n_clients, small.n_vehicles)
    # элитизм: лучшая приспособленность поколения не убывает
    assert all(b2 >= b1 - 1e-12 for b1, b2 in zip(res.history_best, res.history_best[1:]))
    assert res.best_fitness >= res.history_best[0]
    assert res.best_fitness == pytest.approx(f.score(res.best_routes))


def test_weighted_sum_fitness_runs(small):
    f = WeightedSumFitness(small)
    res = run_ga(small, f, GAConfig(pop_size=30, generations=30, seed=2))
    assert res.best_fitness <= 1.0


def test_brute_force_counts():
    # N = 3, K = 2: решения с точностью до перестановки машин
    sols = list(iter_all_solutions(3, 2))
    # 3! (все в одной машине) + 6 разбиений {1|2} с порядками: 3·2!·1! = 6
    assert len(sols) == 6 + 6
    assert solution_space_size(3, 2) == 24


def test_ga_reaches_brute_force_optimum():
    inst = generate_instance(6, 2, seed=3)
    f = FuzzyFitness(inst)
    _, best_val, _ = brute_force(inst, f.score)
    res = run_ga(inst, FuzzyFitness(inst), GAConfig(pop_size=60, generations=150, seed=0))
    assert res.best_fitness == pytest.approx(best_val, abs=1e-9)


def test_instance_json_roundtrip(tmp_path, small):
    p = tmp_path / "inst.json"
    small.save(p)
    loaded = Instance.load(p)
    assert loaded.to_dict() == small.to_dict()
    assert np.allclose(loaded.dist, small.dist)
