#A А | обязательное | Листинг основных модулей программы

Ниже приведены исходные тексты модулей, реализующих интеллектуальное ядро системы. Полный исходный код, включая графический интерфейс, визуализацию и тесты, находится в каталогах src и tests электронного приложения к работе.

!applisting А.1 | Модуль src/model.py – модель задачи и показатели плана | src/model.py

!applisting А.2 | Модуль src/fuzzy/membership.py – функции принадлежности | src/fuzzy/membership.py

!applisting А.3 | Модуль src/fuzzy/variables.py – лингвистические переменные | src/fuzzy/variables.py

!applisting А.4 | Модуль src/fuzzy/rules.py – база нечётких правил | src/fuzzy/rules.py

!applisting А.5 | Модуль src/fuzzy/mamdani.py – механизм вывода Мамдани | src/fuzzy/mamdani.py

!applisting А.6 | Модуль src/ga/encoding.py – кодирование хромосомы | src/ga/encoding.py

!applisting А.7 | Модуль src/ga/operators.py – генетические операторы | src/ga/operators.py

!applisting А.8 | Модуль src/ga/fitness.py – функции приспособленности | src/ga/fitness.py

!applisting А.9 | Модуль src/ga/engine.py – цикл генетического алгоритма | src/ga/engine.py

#A Б | справочное | Пример входного файла задачи

Задача с N = 10 клиентами и K = 2 машинами (файл experiments/instances/N10_s1.json). Поля клиента: id – номер, x и y – координаты, км; demand – объём заказа; urgency – срочность (1 – обычный, 2 – повышенный, 3 – срочный); tw_start и tw_end – временное окно, мин от начала смены; service – время разгрузки, мин.

!include instance_json

#A В | справочное | Пример протокола работы программы

Вывод консольного интерфейса при решении задачи с N = 20 клиентами (команда python -m src.main --clients 20 --seed 2 --trace): ход эволюции, сравнение с жадным алгоритмом, маршруты машин и полный протокол нечёткого вывода для найденного решения.

!include cli_output

#A Г | справочное | Диаграмма классов интеллектуальной системы

!appfig Г.1 | docs/figures/classes.png | 16 | Диаграмма основных классов системы
