"""Главный цикл генетического алгоритма.

Схема одного поколения:
    1. оценка приспособленности всех особей (нечёткий вывод Мамдани);
    2. элитизм — лучшие ``elite`` особей переходят в новое поколение без изменений;
    3. пока новое поколение не заполнено: отбор двух родителей →
       скрещивание OX с вероятностью pc → мутация каждого потомка с вероятностью pm;
    4. проверка критериев останова: лимит поколений, стагнация, лимит времени.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from src.baselines import randomized_nearest_neighbor
from src.ga.encoding import decode, encode, random_chromosome
from src.ga.operators import SELECTION, mutate, order_crossover
from src.model import Instance


@dataclass
class GAConfig:
    """Параметры генетического алгоритма (значения по умолчанию обоснованы
    экспериментами раздела 4 пояснительной записки)."""
    pop_size: int = 100
    generations: int = 300
    crossover_rate: float = 0.9
    mutation_rate: float = 0.2
    selection: str = "tournament"
    tournament_k: int = 3
    elite: int = 2
    seed_fraction: float = 0.1     # доля начальной популяции из рандомизированной эвристики
    stagnation: int = 120          # останов, если лучшая особь не улучшалась столько поколений
    time_limit: float | None = None
    seed: int = 0


@dataclass
class GAResult:
    """Результат работы ГА и журнал сходимости."""
    best_chrom: list[int]
    best_routes: list[list[int]]
    best_fitness: float
    history_best: list[float] = field(default_factory=list)
    history_mean: list[float] = field(default_factory=list)
    history_worst: list[float] = field(default_factory=list)
    initial_best_routes: list[list[int]] | None = None
    generations_run: int = 0
    evaluations: int = 0
    elapsed: float = 0.0
    stop_reason: str = ""


def run_ga(inst: Instance, fitness: Callable[[list[int]], float], cfg: GAConfig | None = None,
           callback: Callable[[int, float, float, list[int]], bool | None] | None = None
           ) -> GAResult:
    """Запускает ГА на задаче ``inst`` с функцией приспособленности ``fitness``.

    callback(поколение, лучшая, средняя, лучшая_хромосома) вызывается после
    каждого поколения (используется GUI); если он вернёт True — останов.
    """
    cfg = cfg or GAConfig()
    rng = np.random.default_rng(cfg.seed)
    n, k = inst.n_clients, inst.n_vehicles
    select = SELECTION[cfg.selection]
    t0 = time.perf_counter()

    # Начальная популяция: небольшая доля (seed_fraction) — решения
    # рандомизированного «ближайшего соседа», остальные — случайные
    # перестановки. «Засев» выводит часть особей в область, где нечёткая
    # оценка информативна, а случайные особи обеспечивают разнообразие.
    n_seed = int(round(cfg.seed_fraction * cfg.pop_size))
    pop = [encode(randomized_nearest_neighbor(inst, rng), n) for _ in range(n_seed)]
    pop += [random_chromosome(n, k, rng) for _ in range(cfg.pop_size - n_seed)]
    fits = np.array([fitness(c) for c in pop])

    best_i = int(np.argmax(fits))
    best_chrom, best_fit = list(pop[best_i]), float(fits[best_i])
    res = GAResult(best_chrom, decode(best_chrom, n), best_fit,
                   initial_best_routes=decode(best_chrom, n))
    last_improve = 0
    gen = 0
    res.stop_reason = "лимит поколений"
    for gen in range(1, cfg.generations + 1):
        # --- журнал сходимости (по текущему поколению)
        res.history_best.append(float(fits.max()))
        res.history_mean.append(float(fits.mean()))
        res.history_worst.append(float(fits.min()))

        # --- элитизм: лучшие особи копируются без изменений
        order = np.argsort(fits)[::-1]
        new_pop = [list(pop[i]) for i in order[:cfg.elite]]

        # --- отбор, скрещивание, мутация
        while len(new_pop) < cfg.pop_size:
            p1 = pop[select(fits, rng, k=cfg.tournament_k)]
            p2 = pop[select(fits, rng, k=cfg.tournament_k)]
            if rng.random() < cfg.crossover_rate:
                c1, c2 = order_crossover(p1, p2, rng), order_crossover(p2, p1, rng)
            else:
                c1, c2 = list(p1), list(p2)
            for child in (c1, c2):
                if rng.random() < cfg.mutation_rate:
                    child = mutate(child, rng, n)
                if len(new_pop) < cfg.pop_size:
                    new_pop.append(child)
        pop = new_pop
        fits = np.array([fitness(c) for c in pop])

        # --- обновление лучшего решения
        i = int(np.argmax(fits))
        if fits[i] > best_fit + 1e-12:
            best_fit, best_chrom = float(fits[i]), list(pop[i])
            last_improve = gen
        if callback is not None and callback(gen, best_fit, float(fits.mean()), best_chrom):
            res.stop_reason = "остановлено пользователем"
            break
        # --- критерии останова
        if gen - last_improve >= cfg.stagnation:
            res.stop_reason = f"стагнация {cfg.stagnation} поколений"
            break
        if cfg.time_limit is not None and time.perf_counter() - t0 > cfg.time_limit:
            res.stop_reason = "лимит времени"
            break

    res.history_best.append(float(fits.max()))
    res.history_mean.append(float(fits.mean()))
    res.history_worst.append(float(fits.min()))
    res.best_chrom, res.best_fitness = best_chrom, best_fit
    res.best_routes = decode(best_chrom, n)
    res.generations_run = gen
    res.evaluations = getattr(fitness, "evaluations", 0)
    res.elapsed = time.perf_counter() - t0
    return res
