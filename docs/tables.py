"""Данные для записки, вычисляемые из результатов экспериментов:
значения для подстановки в текст ({{имя}}), генераторы таблиц, текст реферата."""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"
sys.path.insert(0, str(ROOT))

METHODS = {"Случайное": "rnd", "Ближайший сосед": "nn", "ГА + взвеш. сумма": "ws",
           "ГА + нечёткая оценка": "fz"}


def f(x, nd=1):
    """Число с десятичной запятой."""
    return f"{float(x):.{nd}f}".replace(".", ",").replace("-", "−")


def read_csv(name):
    with open(RES / name, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_values() -> dict:
    v = {}
    cmp_rows = read_csv("exp1_compare.csv")
    for r in cmp_rows:
        key = f"c{r['N']}_{METHODS[r['method']]}"
        v[key + "_dist"] = f(r["distance_mean"], 0)
        v[key + "_late"] = f(r["n_late_mean"], 1)
        v[key + "_latemin"] = f(r["lateness_mean"], 0)
        v[key + "_q"] = f(r["quality_mean"], 3)
        v[key + "_time"] = f(r["time_mean"], 2)
        v[key + "_bal"] = f(r["balance_mean"], 2)
        v[key + "_urg"] = f(r["urgency_mean"], 2)
    by = {(r["N"], METHODS[r["method"]]): r for r in cmp_rows}
    for n in ("10", "20", "30", "50"):
        nn, fz, ws = by[(n, "nn")], by[(n, "fz")], by[(n, "ws")]
        v[f"red_latemin_{n}"] = f(100 * (1 - float(fz["lateness_mean"]) /
                                         float(nn["lateness_mean"])), 0)
        v[f"red_late_{n}"] = f(100 * (1 - float(fz["n_late_mean"]) / float(nn["n_late_mean"])), 0)
        v[f"dist_vs_nn_{n}"] = f(100 * (float(fz["distance_mean"]) / float(nn["distance_mean"])
                                        - 1), 1)
        v[f"wsdist_vs_nn_{n}"] = f(100 * (float(ws["distance_mean"]) /
                                          float(nn["distance_mean"]) - 1), 1)
        v[f"q_gain_{n}"] = f(float(fz["quality_mean"]) - float(nn["quality_mean"]), 2)
    br = read_csv("exp2_bruteforce.csv")
    for r in br:
        n = r["N"]
        v[f"b{n}_sol"] = f"{int(r['solutions']):,}".replace(",", " ")
        v[f"b{n}_bt"] = f(r["brute_time"], 2)
        v[f"b{n}_gt"] = f(r["ga_time"], 2)
        v[f"b{n}_hit"] = f(100 * float(r["ga_hit_rate"]), 0)
        v[f"b{n}_gap"] = f(r["ga_gap_pct"], 1)
        v[f"b{n}_ev"] = r["ga_evals"]
        v[f"b{n}_evpct"] = f(100 * int(r["ga_evals"]) / int(r["solutions"]), 1)
    pr = read_csv("exp4_params.csv")
    for r in pr:
        key = {"Размер популяции": "pop", "Вероятность мутации": "pm",
               "Тип отбора": "sel"}[r["param"]]
        val = r["value"].replace(".", "")
        val = {"турнирный": "t", "рулетка": "r", "ранговый": "k"}.get(val, val)
        v[f"p_{key}_{val}"] = f(r["fitness_mean"], 3)
        v[f"p_{key}_{val}_sd"] = f(r["fitness_std"], 3)
        v[f"p_{key}_{val}_t"] = f(r["time_mean"], 2)
    s = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
    c = s["convergence"]
    v["conv_init"] = f(c["initial_best"], 3)
    v["conv_best"] = f(c["best"], 3)
    v["conv_50"] = f(c["best_at_50"], 3)
    v["conv_100"] = f(c["best_at_100"], 3)
    v["conv_evals"] = c["evaluations"]
    v["conv_time"] = f(c["time"], 1)
    tr = json.loads((RES / "exp7_trace.json").read_text(encoding="utf-8"))
    v["tr_q"] = f(tr["output"], 3)
    v["tr_dist"] = f(tr["metrics"]["distance"], 1)
    v["tr_ref"] = f(tr["metrics"]["ref_distance"], 1)
    v["tr_late"] = tr["metrics"]["n_late"]
    v["tr_latemin"] = f(tr["metrics"]["lateness"], 1)
    for k, val in tr["inputs"].items():
        v[f"tr_{k}"] = f(val, 3)
    v["total_time"] = f(s["total_time"], 0)
    fz = tr["fuzzified"]
    v["tr_short"] = f(fz["length"]["short"], 3)
    v["tr_medium"] = f(fz["length"]["medium"], 3)
    v["tr_urg_medium"] = f(fz["urgency"]["medium"], 3)
    fired = sorted(read_csv("exp7_rules_fired.csv"), key=lambda r: -float(r["d"]))
    for i, r in enumerate(fired[:3], 1):
        v[f"top{i}"] = f"П{r['rule']}"
        v[f"top{i}_d"] = f(r["d"], 3)
    b8 = next(r for r in br if r["N"] == "8")
    v["b8_speed"] = f(float(b8["brute_time"]) / float(b8["ga_time"]), 0)
    from src.baselines import nearest_neighbor
    from src.model import Instance, evaluate_routes
    inst = Instance.load(ROOT / "experiments" / "instances" / "N30_s1.json")
    v["nn30_late"] = evaluate_routes(nearest_neighbor(inst), inst).n_late
    return v


# ============================================================== генераторы таблиц
def gen_compare(b):
    rows = []
    for r in read_csv("exp1_compare.csv"):
        rows.append([r["N"], r["method"], f(r["distance_mean"], 0) + " ± " + f(r["distance_std"], 0),
                     f(r["n_late_mean"], 1), f(r["lateness_mean"], 0),
                     f(r["overload_mean"], 1), f(r["balance_mean"], 2), f(r["urgency_mean"], 2),
                     f(r["quality_mean"], 3) + " ± " + f(r["quality_std"], 3),
                     f(r["time_mean"], 2)])
    return {"header": ["N", "Метод", "Пробег, км", "Число опозданий", "Опоздание, мин",
                       "Перегруз", "B", "U", "Оценка Q", "Время, с"],
            "rows": rows, "widths": [0.9, 3.1, 2.0, 1.6, 1.7, 1.4, 1.0, 1.0, 2.2, 1.3],
            "font": 10, "align": "clcccccccc"}


def gen_brute(b):
    rows = []
    for r in read_csv("exp2_bruteforce.csv"):
        rows.append([r["N"], f"{int(r['solutions']):,}".replace(",", " "), f(r["opt_fitness"], 4),
                     f(r["brute_time"], 2), f(r["ga_mean"], 4), f(r["ga_min"], 4),
                     f(100 * float(r["ga_hit_rate"]), 0), f(r["ga_gap_pct"], 1), r["ga_evals"],
                     f(r["ga_time"], 2)])
    return {"header": ["N", "Число решений", "Оптимум f*", "Время перебора, с",
                       "ГА: средняя f", "ГА: худшая f", "Найден оптимум, %",
                       "Отставание, %", "Уникальных оценок ГА", "Время ГА, с"],
            "rows": rows, "font": 10, "align": "cccccccccc",
            "widths": [0.8, 1.8, 1.6, 1.7, 1.6, 1.6, 1.7, 1.6, 1.9, 1.4]}


def gen_params(b):
    rows = []
    for r in read_csv("exp4_params.csv"):
        rows.append([r["param"], r["value"], f(r["fitness_mean"], 3), f(r["fitness_std"], 3),
                     f(r["fitness_min"], 3), f(r["fitness_max"], 3), f(r["time_mean"], 2),
                     r["evals_mean"]])
    return {"header": ["Параметр", "Значение", "Средняя f", "СКО", "Мин.", "Макс.",
                       "Время, с", "Уникальных оценок"],
            "rows": rows, "font": 11, "align": "lccccccc",
            "widths": [3.6, 2.2, 1.8, 1.4, 1.4, 1.4, 1.6, 2.2]}


def gen_fuzzification(b):
    data = json.loads((RES / "exp7_fuzzification.json").read_text(encoding="utf-8"))
    rows = []
    for d in data:
        terms = [f"«{k}» = {f(val, 3)}" for k, val in d.items() if k not in ("variable", "value")]
        rows.append([d["variable"], f(d["value"], 3), "; ".join(terms)])
    return {"header": ["Входная переменная", "Чёткое значение a", "Степени принадлежности b = μ(a)"],
            "rows": rows, "widths": [5.0, 2.6, 8.9], "font": 11, "align": "lcl"}


def gen_fired(b):
    rows = []
    for r in read_csv("exp7_rules_fired.csv"):
        if float(r["d"]) <= 0:
            continue
        conds = r["conditions"].replace("Протяжённость", "L").replace(
            "Загрузка транспорта", "З").replace("Соблюдение временных окон", "T").replace(
            "Обслуживание срочных заказов", "U").replace("Сбалансированность", "B")
        conds = conds.replace(".", ",")
        rows.append([f"П{r['rule']}", conds, f(r["c"], 3), f(r["F"], 1), f(r["d"], 3),
                     r["conclusion"]])
    return {"header": ["Правило", "Подусловия и их степени истинности b",
                       "c = min b", "F", "d = c·F", "Заключение (терм «Качества»)"],
            "rows": rows, "widths": [1.4, 7.0, 1.6, 1.0, 1.6, 3.0], "font": 10,
            "align": "clcccl"}


def gen_levels(b):
    tr = json.loads((RES / "exp7_trace.json").read_text(encoding="utf-8"))
    order = ["очень низкое", "низкое", "среднее", "высокое", "очень высокое"]
    rows = [[t, f(tr["levels"].get(t, 0.0), 3)] for t in order]
    rows.append(["Результат дефаззификации Q", f(tr["output"], 4)])
    return {"header": ["Терм выходной переменной", "Уровень среза max d_j"],
            "rows": rows, "widths": [9.0, 7.5], "font": 12, "align": "lc"}


def gen_rules(b):
    from src.fuzzy.mamdani import build_default_engine
    from src.fuzzy.rules import rule_to_text
    eng = build_default_engine()
    rows = []
    for j, r in enumerate(eng.rules, 1):
        text = rule_to_text(r, eng.inputs, eng.output)
        text = text.rsplit(" (F", 1)[0]
        rows.append([str(j), text, f(r.weight, 1), r.explanation])
    return {"header": ["№", "Правило", "F", "Пояснение"], "rows": rows,
            "widths": [0.8, 8.2, 0.9, 6.6], "font": 10, "align": "clcl"}


def gen_variables(b):
    from src.fuzzy.mamdani import build_default_engine
    eng = build_default_engine()
    sym = {"length": "L", "load": "З", "timewin": "T", "urgency": "U", "balance": "B",
           "quality": "Q"}
    rows = []
    for v in list(eng.inputs.values()) + [eng.output]:
        terms = []
        for t in v.terms.values():
            kind = "Tri" if len(t.mf.params) == 3 else "Trap"
            terms.append(f"«{t.label}» – {kind}({'; '.join(f(p, 2) for p in t.mf.params)})")
        lo, hi = v.universe
        rows.append([f"{v.title} ({sym[v.name]})", f"[{f(lo, 1)}; {f(hi, 1)}]", "; ".join(terms)])
    return {"header": ["Переменная", "Универсум", "Термы и параметры функций принадлежности"],
            "rows": rows, "widths": [4.2, 2.3, 10.0], "font": 11, "align": "lcl"}


def gen_space(b):
    import math
    rows = []
    for n, k in [(5, 2), (8, 2), (10, 2), (20, 3), (30, 4), (50, 7)]:
        s = math.factorial(n + k - 1) / math.factorial(k - 1)
        exp = int(math.floor(math.log10(s)))
        mant = s / 10 ** exp
        years = s / 1e9 / 3.15e7
        yrs = (f"{f(years, 1)}" if years >= 0.1 else "< 0,1") if years < 1e3 else \
            f"≈ 10^{int(math.log10(years))}"
        secs = s / 1e9
        rows.append([str(n), str(k), f"{f(mant, 2)}·10^{exp}",
                     (f(secs, 3) + " с" if secs < 60 else yrs + " лет")])
    return {"header": ["N", "K", "Число хромосом (N+K−1)!/(K−1)!",
                       "Время перебора при 10^9 решений/с"],
            "rows": rows, "widths": [1.5, 1.5, 6.5, 7.0], "font": 12, "align": "cccc"}


def gen_instance_json(b):
    d = json.loads((ROOT / "experiments" / "instances" / "N10_s1.json").read_text("utf-8"))
    lines = ["{",
             f'  "name": "{d["name"]}", "depot": {d["depot"]}, "n_vehicles": {d["n_vehicles"]},',
             f'  "capacity": {d["capacity"]}, "speed": {d["speed"]}, "horizon": {d["horizon"]},',
             '  "clients": [']
    for i, c in enumerate(d["clients"]):
        comma = "," if i < len(d["clients"]) - 1 else ""
        lines.append("    " + json.dumps(c, ensure_ascii=False) + comma)
    lines += ["  ]", "}"]
    return "\n".join(lines)


def gen_cli_output(b):
    out = subprocess.run([sys.executable, "-m", "src.main", "--clients", "20", "--seed", "2",
                          "--trace"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    # длинные строки правил переносим
    res = []
    for line in out.splitlines():
        while len(line) > 92:
            cut = line.rfind(" ", 0, 92)
            cut = cut if cut > 40 else 92
            res.append(line[:cut])
            line = "        " + line[cut:].lstrip()
        res.append(line)
    return "\n".join(res)


GENERATORS = {"compare": gen_compare, "brute": gen_brute, "params": gen_params,
              "fuzzification": gen_fuzzification, "fired": gen_fired, "levels": gen_levels,
              "rules": gen_rules, "variables": gen_variables, "space": gen_space,
              "instance_json": gen_instance_json, "cli_output": gen_cli_output}


def appendix_code(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


ABSTRACT_TEXT = [
    "Объект исследования – процесс планирования маршрутов доставки грузов парком "
    "транспортных средств с ограниченной грузоподъёмностью при наличии временных окон и "
    "приоритетов (срочности) заказов. Предмет исследования – гибридные методы искусственного "
    "интеллекта для поиска и оценки планов доставки.",
    "Цель работы – разработка интеллектуальной системы, в которой генетический алгоритм ищет "
    "распределение заказов по машинам и порядок их объезда, а система нечёткого вывода "
    "Мамдани с базой из 26 экспертных правил оценивает качество каждого плана и тем самым "
    "задаёт функцию приспособленности.",
    "Методы: генетический алгоритм с перестановочным кодированием, упорядоченным "
    "скрещиванием, тремя операторами мутации и элитизмом; нечёткая логика (лингвистические "
    "переменные, продукционная база правил с весовыми коэффициентами, алгоритм Мамдани с "
    "дефаззификацией по центру тяжести); вычислительный эксперимент.",
    "Результат: программная система на языке Python с графическим и консольным интерфейсом. "
    "На задачах с 50 клиентами система сокращает суммарное опоздание по сравнению с жадным "
    "алгоритмом «ближайший сосед» на {{red_latemin_50}} %, а на малых задачах находит "
    "точный оптимум, подтверждённый полным перебором.",
]
