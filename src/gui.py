"""Графический интерфейс (tkinter + matplotlib).

Окно содержит: параметры задачи и ГА слева; вкладки «Маршруты»,
«Сходимость», «Нечёткий вывод» справа; журнал работы снизу.
ГА выполняется в отдельном потоке, чтобы окно не «зависало».

Запуск:  python -m src.gui
"""
from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk  # noqa: E402
from tkinter import filedialog, messagebox, ttk  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from src.baselines import nearest_neighbor  # noqa: E402
from src.fuzzy.rules import rule_to_text  # noqa: E402
from src.generator import generate_instance  # noqa: E402
from src.ga.encoding import decode  # noqa: E402
from src.ga.engine import GAConfig, run_ga  # noqa: E402
from src.ga.fitness import FuzzyFitness, WeightedSumFitness, fuzzy_inputs  # noqa: E402
from src.model import Instance, evaluate_routes  # noqa: E402
from src.visualize import plot_convergence, plot_inference, plot_routes  # noqa: E402


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Гибридная система планирования маршрутов: ГА + нечёткая логика")
        self.geometry("1280x820")
        self.inst: Instance | None = None
        self.result = None
        self.stop_flag = threading.Event()
        self.msgs: queue.Queue = queue.Queue()
        self.hist_best: list[float] = []
        self.hist_mean: list[float] = []
        self._build()
        self.generate()
        self.after(100, self._poll)

    # ------------------------------------------------------------------ интерфейс
    def _build(self):
        left = ttk.Frame(self, padding=8)
        left.pack(side=tk.LEFT, fill=tk.Y)
        self.vars = {}

        def field(parent, label, key, default, row):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=str(default))
            ttk.Entry(parent, textvariable=v, width=8).grid(row=row, column=1, pady=2)
            self.vars[key] = v

        task = ttk.LabelFrame(left, text="Задача", padding=6)
        task.pack(fill=tk.X)
        field(task, "Число клиентов N", "n", 30, 0)
        field(task, "Число машин K (пусто — авто)", "k", "", 1)
        field(task, "Seed задачи", "seed", 1, 2)
        ttk.Button(task, text="Сгенерировать", command=self.generate).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        ttk.Button(task, text="Загрузить JSON…", command=self.load).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(task, text="Сохранить JSON…", command=self.save).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=2)

        ga = ttk.LabelFrame(left, text="Генетический алгоритм", padding=6)
        ga.pack(fill=tk.X, pady=8)
        field(ga, "Размер популяции", "pop", 100, 0)
        field(ga, "Макс. поколений", "gens", 300, 1)
        field(ga, "Вероятность скрещивания", "pc", 0.9, 2)
        field(ga, "Вероятность мутации", "pm", 0.2, 3)
        field(ga, "Элитных особей", "elite", 2, 4)
        field(ga, "Стагнация, поколений", "stag", 120, 5)
        field(ga, "Seed ГА", "gseed", 0, 6)
        ttk.Label(ga, text="Отбор").grid(row=7, column=0, sticky="w")
        self.selection = tk.StringVar(value="tournament")
        ttk.Combobox(ga, textvariable=self.selection, width=10, state="readonly",
                     values=["tournament", "roulette", "rank"]).grid(row=7, column=1)
        ttk.Label(ga, text="Оценка").grid(row=8, column=0, sticky="w")
        self.fitness_kind = tk.StringVar(value="fuzzy")
        ttk.Combobox(ga, textvariable=self.fitness_kind, width=10, state="readonly",
                     values=["fuzzy", "weighted"]).grid(row=8, column=1)

        self.btn_solve = ttk.Button(left, text="Решить", command=self.solve)
        self.btn_solve.pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Стоп", command=self.stop_flag.set).pack(fill=tk.X, pady=2)
        ttk.Button(left, text="Жадный алгоритм", command=self.show_greedy).pack(fill=tk.X, pady=2)
        self.status = tk.StringVar(value="Готово")
        ttk.Label(left, textvariable=self.status, wraplength=220).pack(fill=tk.X, pady=8)

        right = ttk.Frame(self, padding=4)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        nb = ttk.Notebook(right)
        nb.pack(fill=tk.BOTH, expand=True)
        self.figs, self.canvases = {}, {}
        for key, title in [("map", "Маршруты"), ("conv", "Сходимость"), ("fuzzy", "Нечёткий вывод")]:
            frame = ttk.Frame(nb)
            nb.add(frame, text=title)
            fig = Figure(figsize=(8, 5.5), dpi=100)
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.figs[key], self.canvases[key] = fig, canvas
        self.log = tk.Text(right, height=10, font=("Courier", 9))
        self.log.pack(fill=tk.X)

    def write(self, text: str):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def _int(self, key, default=None):
        s = self.vars[key].get().strip()
        return int(s) if s else default

    def _float(self, key):
        return float(self.vars[key].get().replace(",", "."))

    # ------------------------------------------------------------------- действия
    def generate(self):
        try:
            self.inst = generate_instance(self._int("n"), self._int("k"), self._int("seed"))
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))
            return
        self.result = None
        self.write(f"Сгенерирована задача {self.inst.name}: N={self.inst.n_clients}, "
                   f"K={self.inst.n_vehicles}, вместимость {self.inst.capacity}")
        self.draw_map(nearest_neighbor(self.inst), "Жадное решение (ближайший сосед)")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            self.inst = Instance.load(path)
            self.write(f"Загружена задача {self.inst.name} из {path}")
            self.draw_map(nearest_neighbor(self.inst), "Жадное решение (ближайший сосед)")

    def save(self):
        if self.inst is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile=f"{self.inst.name}.json")
        if path:
            self.inst.save(path)
            self.write(f"Задача сохранена: {path}")

    def show_greedy(self):
        if self.inst is not None:
            routes = nearest_neighbor(self.inst)
            self.draw_map(routes, "Жадное решение (ближайший сосед)")
            self.draw_fuzzy(routes)

    def solve(self):
        if self.inst is None:
            return
        try:
            cfg = GAConfig(pop_size=self._int("pop"), generations=self._int("gens"),
                           crossover_rate=self._float("pc"), mutation_rate=self._float("pm"),
                           selection=self.selection.get(), elite=self._int("elite"),
                           stagnation=self._int("stag"), seed=self._int("gseed"))
        except ValueError:
            messagebox.showerror("Ошибка", "Проверьте числовые параметры")
            return
        self.stop_flag.clear()
        self.btn_solve.state(["disabled"])
        self.hist_best, self.hist_mean = [], []
        kind = self.fitness_kind.get()
        self.write(f"Запуск ГА ({kind}): популяция {cfg.pop_size}, поколений {cfg.generations}, "
                   f"pc={cfg.crossover_rate}, pm={cfg.mutation_rate}, отбор {cfg.selection}")
        inst = self.inst

        def worker():
            fit = FuzzyFitness(inst) if kind == "fuzzy" else WeightedSumFitness(inst)

            def cb(gen, best, mean, chrom):
                self.msgs.put(("progress", gen, best, mean, chrom))
                return self.stop_flag.is_set()

            res = run_ga(inst, fit, cfg, callback=cb)
            self.msgs.put(("done", res))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        last = None
        try:
            while True:
                msg = self.msgs.get_nowait()
                if msg[0] == "progress":
                    _, gen, best, mean, chrom = msg
                    self.hist_best.append(best)
                    self.hist_mean.append(mean)
                    last = (gen, best, chrom)
                else:
                    self.finish(msg[1])
                    last = None          # итог уже нарисован, промежуточный не нужен
        except queue.Empty:
            pass
        if last is not None:
            gen, best, chrom = last
            self.status.set(f"Поколение {gen}: лучшая приспособленность {best:.4f}")
            if gen % 10 == 0:
                self.draw_map(decode(chrom, self.inst.n_clients), f"Поколение {gen}")
                self.draw_conv()
        self.after(100, self._poll)

    def finish(self, res):
        self.result = res
        self.btn_solve.state(["!disabled"])
        self.write(f"ГА завершён: {res.generations_run} поколений, {res.evaluations} оценок, "
                   f"{res.elapsed:.1f} с ({res.stop_reason}); лучшая приспособленность "
                   f"{res.best_fitness:.4f}")
        for name, routes in [("Жадный", nearest_neighbor(self.inst)), ("ГА", res.best_routes)]:
            m = evaluate_routes(routes, self.inst)
            self.write(f"  {name:<8} пробег {m.total_distance:7.1f} км, опозданий {m.n_late}, "
                       f"опоздание {m.total_lateness:.0f} мин, перегруз {m.overload:.0f}")
        for k, r in enumerate(res.best_routes, 1):
            self.write(f"  Машина {k}: 0 → {' → '.join(map(str, r))} → 0")
        self.status.set(f"Готово: Q = {res.best_fitness:.4f}")
        self.draw_map(res.best_routes, "Решение ГА + нечёткая оценка")
        self.draw_conv()
        self.draw_fuzzy(res.best_routes)

    # ----------------------------------------------------------------- рисование
    def draw_map(self, routes, title):
        fig = self.figs["map"]
        fig.clear()
        ax = fig.add_subplot(111)
        plot_routes(self.inst, routes, ax, title=title)
        fig.tight_layout()
        self.canvases["map"].draw_idle()

    def draw_conv(self):
        fig = self.figs["conv"]
        fig.clear()
        plot_convergence(self.hist_best, self.hist_mean, fig.add_subplot(111))
        fig.tight_layout()
        self.canvases["conv"].draw_idle()

    def draw_fuzzy(self, routes):
        ff = FuzzyFitness(self.inst)
        m = evaluate_routes(routes, self.inst)
        tr = ff.engine.trace(fuzzy_inputs(m, ff.ref_distance))
        fig = self.figs["fuzzy"]
        fig.clear()
        plot_inference(tr, ff.engine, fig.add_subplot(111))
        fig.tight_layout()
        self.canvases["fuzzy"].draw_idle()
        self.write("Нечёткий вывод для показанного решения:")
        for name, val in tr.inputs.items():
            var = ff.engine.inputs[name]
            degs = ", ".join(f"{var.terms[t].label} {mu:.2f}"
                             for t, mu in tr.fuzzified[name].items() if mu > 0)
            self.write(f"  {var.title} = {val:.3f} → {degs}")
        top = sorted(range(len(tr.activations)), key=lambda j: -tr.activations[j])[:5]
        for j in top:
            if tr.activations[j] > 0:
                self.write(f"  П{j + 1} (d={tr.activations[j]:.2f}): "
                           f"{rule_to_text(ff.engine.rules[j], ff.engine.inputs, ff.engine.output)}")
        self.write(f"  Качество решения Q = {tr.output:.4f}")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
