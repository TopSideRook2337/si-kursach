"""Эксперименты для раздела 4 пояснительной записки.

Запуск (из корня репозитория):
    python experiments/run_experiments.py            # все эксперименты
    python experiments/run_experiments.py --quick    # укороченный прогон для проверки

Результаты: experiments/results/*.png, *.csv, summary.json;
задачи — experiments/instances/*.json.

Эксперименты:
    1. сравнение ГА+нечёткая оценка с случайным решением, жадным алгоритмом
       и ГА со взвешенной суммой на N = 10, 20, 30, 50;
    2. сравнение с полным перебором для N ≤ 8;
    3. графики сходимости;
    4. влияние параметров (размер популяции, вероятность мутации, тип отбора);
    5. карты маршрутов (начальное поколение и итоговое решение);
    6. функции принадлежности всех лингвистических переменных;
    7. полный протокол нечёткого вывода Мамдани для одного решения.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.baselines import brute_force, nearest_neighbor, random_solution  # noqa: E402
from src.fuzzy.rules import rule_to_text  # noqa: E402
from src.generator import generate_instance  # noqa: E402
from src.ga.engine import GAConfig, run_ga  # noqa: E402
from src.ga.fitness import FuzzyFitness, WeightedSumFitness, fuzzy_inputs  # noqa: E402
from src.model import Instance, evaluate_routes, solution_space_size  # noqa: E402
from src.visualize import (PALETTE, plot_all_memberships, plot_convergence,  # noqa: E402
                           plot_inference, plot_membership, plot_routes)

RES = ROOT / "experiments" / "results"
INST = ROOT / "experiments" / "instances"
QUICK = False

METHOD_LABELS = {"random": "Случайное", "greedy": "Ближайший сосед",
                 "ga_weighted": "ГА + взвеш. сумма", "ga_fuzzy": "ГА + нечёткая оценка"}


def gens_for(n: int) -> int:
    if QUICK:
        return 60
    return 500 if n >= 50 else 300


def write_csv(path: Path, rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def metrics_row(routes, inst: Instance, ff: FuzzyFitness) -> dict:
    m = evaluate_routes(routes, inst)
    return {"distance": m.total_distance, "n_late": m.n_late, "lateness": m.total_lateness,
            "overload": m.overload, "urgency": m.urgency_index, "balance": m.balance_cv,
            "quality": ff.quality(m), "fitness": ff.score(routes)}


# =========================================================== 1. сравнение методов
def job_compare(args):
    n, seed, method = args
    inst = Instance.load(INST / f"N{n}_s{seed}.json")
    ff = FuzzyFitness(inst)
    t0 = time.perf_counter()
    if method == "random":
        rng = np.random.default_rng(seed)
        rows = [metrics_row(random_solution(inst, rng), inst, ff) for _ in range(20)]
        row = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
    elif method == "greedy":
        row = metrics_row(nearest_neighbor(inst), inst, ff)
    else:
        fit = ff if method == "ga_fuzzy" else WeightedSumFitness(inst)
        res = run_ga(inst, fit, GAConfig(generations=gens_for(n), stagnation=150, seed=seed))
        row = metrics_row(res.best_routes, inst, ff)
    row["time"] = time.perf_counter() - t0
    return {"N": n, "seed": seed, "method": method, **row}


def exp_compare(pool, sizes, seeds):
    for n in sizes:
        for s in seeds:
            generate_instance(n, seed=s, name=f"N{n}_s{s}").save(INST / f"N{n}_s{s}.json")
    jobs = [(n, s, m) for n in sizes for s in seeds for m in METHOD_LABELS]
    raw = pool.map(job_compare, jobs)
    write_csv(RES / "exp1_compare_raw.csv", raw)
    agg = []
    for n in sizes:
        for m in METHOD_LABELS:
            rs = [r for r in raw if r["N"] == n and r["method"] == m]
            row = {"N": n, "method": METHOD_LABELS[m]}
            for k in ["distance", "n_late", "lateness", "overload", "urgency", "balance",
                      "quality", "time"]:
                v = np.array([r[k] for r in rs])
                row[k + "_mean"] = round(float(v.mean()), 4)
                row[k + "_std"] = round(float(v.std()), 4)
            agg.append(row)
    write_csv(RES / "exp1_compare.csv", agg)

    # графики: пробег, опоздания, нечёткая оценка
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    width = 0.2
    x = np.arange(len(sizes))
    for ax, (key, title) in zip(axes, [("distance", "Суммарный пробег, км"),
                                        ("n_late", "Число опозданий"),
                                        ("quality", "Нечёткая оценка качества Q")]):
        for i, m in enumerate(METHOD_LABELS):
            vals = [np.mean([r[key] for r in raw if r["N"] == n and r["method"] == m])
                    for n in sizes]
            errs = [np.std([r[key] for r in raw if r["N"] == n and r["method"] == m])
                    for n in sizes]
            ax.bar(x + (i - 1.5) * width, vals, width * 0.92, yerr=errs, capsize=2,
                   color=PALETTE[i], label=METHOD_LABELS[m], error_kw={"lw": 0.8})
        ax.set_xticks(x, [f"N = {n}" for n in sizes])
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RES / "exp1_compare.png")
    plt.close(fig)
    return agg


# ========================================================= 2. полный перебор (N ≤ 8)
def job_brute(n):
    inst = generate_instance(n, 2, seed=100 + n, name=f"N{n}_K2_brute")
    inst.save(INST / f"N{n}_brute.json")
    ff = FuzzyFitness(inst)
    t0 = time.perf_counter()
    best, best_val, count = brute_force(inst, ff.score)
    t_brute = time.perf_counter() - t0
    ga_vals, ga_times, ga_evals = [], [], []
    for s in range(10):
        f = FuzzyFitness(inst)
        res = run_ga(inst, f, GAConfig(generations=300, stagnation=150, seed=s))
        ga_vals.append(res.best_fitness)
        ga_times.append(res.elapsed)
        ga_evals.append(res.evaluations)
    ga_vals = np.array(ga_vals)
    return {"N": n, "K": 2, "solutions": count, "space_chromosomes": int(solution_space_size(n, 2)),
            "opt_fitness": round(best_val, 4), "brute_time": round(t_brute, 2),
            "ga_mean": round(float(ga_vals.mean()), 4), "ga_min": round(float(ga_vals.min()), 4),
            "ga_hit_rate": float(np.mean(np.abs(ga_vals - best_val) < 1e-9)),
            "ga_within_2pct": float(np.mean(ga_vals >= best_val * 0.98)),
            "ga_gap_pct": round(float((best_val - ga_vals.mean()) / best_val * 100), 3),
            "ga_time": round(float(np.mean(ga_times)), 3),
            "ga_evals": int(np.mean(ga_evals))}


def exp_brute(pool, sizes):
    rows = pool.map(job_brute, sizes)
    write_csv(RES / "exp2_bruteforce.csv", rows)
    return rows


# ======================================================== 3–5. сходимость и карты
def exp_convergence_and_maps(n=30, seed=1):
    inst = Instance.load(INST / f"N{n}_s{seed}.json")
    ff = FuzzyFitness(inst)
    res = run_ga(inst, ff, GAConfig(generations=gens_for(n), stagnation=10 ** 9, seed=seed))

    fig, ax = plt.subplots(figsize=(7, 4))
    plot_convergence(res.history_best, res.history_mean, ax,
                     title=f"Сходимость ГА (N = {n}, популяция 100)")
    ax.set_ylim(-1.0, 1.0)
    fig.savefig(RES / "exp3_convergence.png")
    plt.close(fig)

    # несколько запусков ГА с разными seed — разброс кривых лучшей приспособленности
    fig, ax = plt.subplots(figsize=(7, 4))
    for s in range(5):
        r = run_ga(inst, FuzzyFitness(inst),
                   GAConfig(generations=gens_for(n), stagnation=10 ** 9, seed=s))
        ax.plot(r.history_best, color=PALETTE[s], lw=1.4, label=f"seed ГА = {s}")
    ax.set_xlabel("Поколение")
    ax.set_ylabel("Лучшая приспособленность")
    ax.set_title(f"Лучшая приспособленность в 5 запусках ГА (N = {n})")
    ax.legend(fontsize=8)
    fig.savefig(RES / "exp3_convergence_seeds.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(19, 6))
    plot_routes(inst, res.initial_best_routes, axes[0], title="Лучшая особь начального поколения")
    plot_routes(inst, nearest_neighbor(inst), axes[1], title="Жадный алгоритм «ближайший сосед»")
    plot_routes(inst, res.best_routes, axes[2], title="Итоговое решение ГА + нечёткая оценка")
    fig.tight_layout()
    fig.savefig(RES / "exp5_routes.png")
    plt.close(fig)
    for name, routes, title in [("initial", res.initial_best_routes, "Начальное поколение"),
                                ("final", res.best_routes, "Итоговое решение ГА")]:
        fig, ax = plt.subplots(figsize=(8.5, 6))
        plot_routes(inst, routes, ax, title=title)
        fig.savefig(RES / f"exp5_routes_{name}.png")
        plt.close(fig)
    with open(RES / "exp5_solution.json", "w", encoding="utf-8") as f:
        json.dump({"instance": inst.name, "routes": res.best_routes,
                   "fitness": res.best_fitness}, f, ensure_ascii=False, indent=1)
    return inst, ff, res


# ================================================= 4. влияние параметров ГА
PARAM_GRID = {
    "pop_size": [20, 50, 100, 200],
    "mutation_rate": [0.01, 0.05, 0.1, 0.2, 0.3],
    "selection": ["tournament", "roulette", "rank"],
}
PARAM_TITLES = {"pop_size": "Размер популяции", "mutation_rate": "Вероятность мутации",
                "selection": "Тип отбора"}
SEL_LABELS = {"tournament": "турнирный", "roulette": "рулетка", "rank": "ранговый"}


def job_param(args):
    param, value, seed = args
    inst = Instance.load(INST / f"N30_s{seed}.json")
    ff = FuzzyFitness(inst)
    cfg = GAConfig(generations=gens_for(30), stagnation=10 ** 9, seed=seed, **{param: value})
    res = run_ga(inst, ff, cfg)
    return {"param": param, "value": value, "seed": seed, "fitness": res.best_fitness,
            "time": res.elapsed, "evaluations": res.evaluations,
            "history": res.history_best}


def exp_params(pool, seeds):
    for s in seeds:
        path = INST / f"N30_s{s}.json"
        if not path.exists():
            generate_instance(30, seed=s, name=f"N30_s{s}").save(path)
    jobs = [(p, v, s) for p, vals in PARAM_GRID.items() for v in vals for s in seeds]
    raw = pool.map(job_param, jobs)
    rows = []
    for p, vals in PARAM_GRID.items():
        for v in vals:
            rs = [r for r in raw if r["param"] == p and r["value"] == v]
            f = np.array([r["fitness"] for r in rs])
            rows.append({"param": PARAM_TITLES[p], "value": SEL_LABELS.get(v, v),
                         "fitness_mean": round(float(f.mean()), 4),
                         "fitness_std": round(float(f.std()), 4),
                         "fitness_min": round(float(f.min()), 4),
                         "fitness_max": round(float(f.max()), 4),
                         "time_mean": round(float(np.mean([r["time"] for r in rs])), 2),
                         "evals_mean": int(np.mean([r["evaluations"] for r in rs]))})
    write_csv(RES / "exp4_params.csv", rows)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for col, (p, vals) in enumerate(PARAM_GRID.items()):
        ax = axes[0, col]
        data = [[r["fitness"] for r in raw if r["param"] == p and r["value"] == v] for v in vals]
        means = [np.mean(d) for d in data]
        stds = [np.std(d) for d in data]
        xs = np.arange(len(vals))
        ax.bar(xs, means, 0.6, yerr=stds, capsize=4, color=PALETTE[0])
        for i, d in enumerate(data):
            ax.scatter(np.full(len(d), i) + np.linspace(-0.15, 0.15, len(d)), d, s=12,
                       color="#0b0b0b", zorder=3)
        ax.set_xticks(xs, [str(SEL_LABELS.get(v, v)) for v in vals])
        ax.set_title(PARAM_TITLES[p])
        ax.set_ylabel("Итоговая приспособленность")
        lo = min(min(d) for d in data)
        ax.set_ylim(max(0.0, lo - 0.1), None)
        ax.grid(axis="x", visible=False)
        ax2 = axes[1, col]
        for i, v in enumerate(vals):
            hs = np.array([r["history"] for r in raw if r["param"] == p and r["value"] == v])
            ax2.plot(hs.mean(axis=0), color=PALETTE[i], lw=1.6, label=str(SEL_LABELS.get(v, v)))
        ax2.set_xlabel("Поколение")
        ax2.set_ylabel("Средняя лучшая приспособленность")
        ax2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RES / "exp4_params.png")
    plt.close(fig)
    return rows


# ================================================= 6. функции принадлежности
def exp_membership(engine):
    plot_all_memberships(engine, RES / "exp6_membership_all.png")
    for v in list(engine.inputs.values()) + [engine.output]:
        fig, ax = plt.subplots(figsize=(6.4, 2.8))
        plot_membership(v, ax)
        ax.set_xlabel(v.description if len(v.description) < 70 else "")
        fig.savefig(RES / f"exp6_mf_{v.name}.png")
        plt.close(fig)


# ================================================= 7. протокол нечёткого вывода
def exp_trace(inst, ff, routes):
    m = evaluate_routes(routes, inst)
    eng = ff.engine
    tr = eng.trace(fuzzy_inputs(m, ff.ref_distance))
    fz = []
    for name, val in tr.inputs.items():
        var = eng.inputs[name]
        row = {"variable": var.title, "value": round(val, 4)}
        for t, mu in tr.fuzzified[name].items():
            row[var.terms[t].label] = round(mu, 3)
        fz.append(row)
    with open(RES / "exp7_fuzzification.json", "w", encoding="utf-8") as f:
        json.dump(fz, f, ensure_ascii=False, indent=1)
    rules = []
    for j, (c, d) in enumerate(zip(tr.strengths, tr.activations), 1):
        r = eng.rules[j - 1]
        rules.append({"rule": j, "text": rule_to_text(r, eng.inputs, eng.output),
                      "conditions": "; ".join(
                          f"{eng.inputs[v].title}={eng.inputs[v].terms[t].label}: "
                          f"{tr.fuzzified[v][t]:.3f}" for v, t in r.conditions),
                      "conclusion": eng.output.terms[r.conclusion].label,
                      "F": r.weight, "c": round(c, 4), "d": round(d, 4)})
    write_csv(RES / "exp7_rules_fired.csv", rules)
    # уровни отсечения по термам выхода после аккумуляции
    levels = {}
    for r, d in zip(eng.rules, tr.activations):
        lab = eng.output.terms[r.conclusion].label
        levels[lab] = max(levels.get(lab, 0.0), d)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    plot_inference(tr, eng, ax)
    fig.savefig(RES / "exp7_inference.png")
    plt.close(fig)
    out = {"inputs": tr.inputs, "fuzzified": tr.fuzzified, "levels": levels,
           "output": tr.output, "metrics": {"distance": m.total_distance, "n_late": m.n_late,
                                             "lateness": m.total_lateness,
                                             "ref_distance": ff.ref_distance}}
    with open(RES / "exp7_trace.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def export_rule_base(engine):
    rows = []
    for j, r in enumerate(engine.rules, 1):
        rows.append({"rule": j, "text": rule_to_text(r, engine.inputs, engine.output),
                     "F": r.weight, "explanation": r.explanation})
    write_csv(RES / "rule_base.csv", rows)


def main():
    global QUICK
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="укороченный прогон")
    args = ap.parse_args()
    QUICK = args.quick
    RES.mkdir(parents=True, exist_ok=True)
    INST.mkdir(parents=True, exist_ok=True)
    t_all = time.perf_counter()
    summary = {}
    sizes = [10, 20, 30, 50]
    seeds = [1, 2, 3] if QUICK else [1, 2, 3, 4, 5]
    with Pool(initializer=_init_worker, initargs=(QUICK,)) as pool:
        print("1. Сравнение методов…", flush=True)
        summary["compare"] = exp_compare(pool, sizes, seeds)
        print("2. Полный перебор…", flush=True)
        summary["brute"] = exp_brute(pool, [5, 6, 7] if QUICK else [5, 6, 7, 8])
        print("4. Влияние параметров…", flush=True)
        summary["params"] = exp_params(pool, seeds if QUICK else list(range(1, 9)))
    print("3, 5. Сходимость и карты маршрутов…", flush=True)
    inst, ff, res = exp_convergence_and_maps()
    summary["convergence"] = {"generations": res.generations_run, "best": res.best_fitness,
                              "initial_best": res.history_best[0],
                              "evaluations": res.evaluations, "time": res.elapsed,
                              "best_at_50": res.history_best[min(50, len(res.history_best) - 1)],
                              "best_at_100": res.history_best[min(100, len(res.history_best) - 1)]}
    print("6. Функции принадлежности…", flush=True)
    exp_membership(ff.engine)
    export_rule_base(ff.engine)
    print("7. Протокол нечёткого вывода…", flush=True)
    summary["trace"] = exp_trace(inst, ff, res.best_routes)
    summary["total_time"] = time.perf_counter() - t_all
    with open(RES / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=float)
    print(f"Готово за {summary['total_time']:.0f} с. Результаты: {RES}")


def _init_worker(quick):
    global QUICK
    QUICK = quick


if __name__ == "__main__":
    main()
