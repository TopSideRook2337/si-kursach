"""Консольный запуск гибридной системы планирования маршрутов.

Примеры:
    python -m src.main --clients 30 --seed 1
    python -m src.main --instance experiments/instances/N30_K4_s1.json --plot routes.png
    python -m src.main --clients 20 --fitness weighted --generations 200
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):                       # запуск как файла: python src/main.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.baselines import nearest_neighbor  # noqa: E402
from src.generator import generate_instance  # noqa: E402
from src.ga.engine import GAConfig, run_ga  # noqa: E402
from src.ga.fitness import FuzzyFitness, WeightedSumFitness, fuzzy_inputs  # noqa: E402
from src.model import Instance, evaluate_routes  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="ГА + нечёткая логика для планирования маршрутов")
    g = p.add_argument_group("задача")
    g.add_argument("--instance", help="JSON-файл задачи (иначе задача генерируется)")
    g.add_argument("--clients", type=int, default=30, help="число клиентов N")
    g.add_argument("--vehicles", type=int, default=None, help="число машин K")
    g.add_argument("--seed", type=int, default=1, help="seed генератора задачи")
    g.add_argument("--save-instance", help="сохранить сгенерированную задачу в JSON")
    a = p.add_argument_group("генетический алгоритм")
    a.add_argument("--pop", type=int, default=100, help="размер популяции")
    a.add_argument("--generations", type=int, default=300, help="максимум поколений")
    a.add_argument("--pc", type=float, default=0.9, help="вероятность скрещивания")
    a.add_argument("--pm", type=float, default=0.2, help="вероятность мутации")
    a.add_argument("--selection", choices=["tournament", "roulette", "rank"],
                   default="tournament")
    a.add_argument("--elite", type=int, default=2, help="число элитных особей")
    a.add_argument("--stagnation", type=int, default=120, help="останов по стагнации")
    a.add_argument("--ga-seed", type=int, default=0, help="seed ГА")
    a.add_argument("--fitness", choices=["fuzzy", "weighted"], default="fuzzy",
                   help="нечёткая оценка (Мамдани) или взвешенная сумма")
    o = p.add_argument_group("вывод")
    o.add_argument("--plot", help="сохранить карту маршрутов и график сходимости в PNG")
    o.add_argument("--trace", action="store_true", help="показать протокол нечёткого вывода")
    return p.parse_args(argv)


def describe(name: str, routes, inst: Instance, ff: FuzzyFitness) -> str:
    m = evaluate_routes(routes, inst)
    return (f"{name:<22} пробег {m.total_distance:8.1f} км | опозданий {m.n_late:3d} "
            f"({m.total_lateness:7.1f} мин) | перегруз {m.overload:4.0f} | "
            f"Q = {ff.quality(m):.3f}")


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.instance:
        inst = Instance.load(args.instance)
    else:
        inst = generate_instance(args.clients, args.vehicles, args.seed)
        if args.save_instance:
            inst.save(args.save_instance)
    print(f"Задача {inst.name}: N = {inst.n_clients}, K = {inst.n_vehicles}, "
          f"вместимость {inst.capacity}, суммарный спрос {inst.total_demand}")

    fuzzy = FuzzyFitness(inst)
    fitness = fuzzy if args.fitness == "fuzzy" else WeightedSumFitness(inst)
    cfg = GAConfig(pop_size=args.pop, generations=args.generations, crossover_rate=args.pc,
                   mutation_rate=args.pm, selection=args.selection, elite=args.elite,
                   stagnation=args.stagnation, seed=args.ga_seed)

    def progress(gen, best, mean, _):
        if gen % 50 == 0:
            print(f"  поколение {gen:4d}: лучшая {best:.4f}, средняя {mean:.4f}")

    res = run_ga(inst, fitness, cfg, callback=progress)
    print(f"ГА завершён: {res.generations_run} поколений, {res.evaluations} оценок, "
          f"{res.elapsed:.1f} с, причина останова — {res.stop_reason}")
    print(describe("Жадный (ближ. сосед)", nearest_neighbor(inst), inst, fuzzy))
    print(describe(f"ГА ({args.fitness})", res.best_routes, inst, fuzzy))
    for k, r in enumerate(res.best_routes, 1):
        print(f"  Машина {k}: склад → {' → '.join(map(str, r)) or '(не используется)'} → склад")

    if args.trace:
        from src.fuzzy.rules import rule_to_text
        m = evaluate_routes(res.best_routes, inst)
        tr = fuzzy.engine.trace(fuzzy_inputs(m, fuzzy.ref_distance))
        print("\nПротокол нечёткого вывода:")
        for name, val in tr.inputs.items():
            var = fuzzy.engine.inputs[name]
            degs = ", ".join(f"{var.terms[t].label} {mu:.2f}"
                             for t, mu in tr.fuzzified[name].items() if mu > 0)
            print(f"  {var.title:<30} = {val:6.3f}  →  {degs}")
        for j, (c, d) in enumerate(zip(tr.strengths, tr.activations), 1):
            if d > 0:
                print(f"  П{j:<2} c = {c:.3f}, d = {d:.3f}: "
                      f"{rule_to_text(fuzzy.engine.rules[j - 1], fuzzy.engine.inputs, fuzzy.engine.output)}")
        print(f"  Дефаззификация (центр тяжести): Q = {tr.output:.4f}")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from src.visualize import plot_convergence, plot_routes
        fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
        plot_routes(inst, res.best_routes, axes[0], title="Решение ГА")
        plot_convergence(res.history_best, res.history_mean, axes[1])
        fig.tight_layout()
        fig.savefig(args.plot)
        print(f"Рисунок сохранён: {args.plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
