"""Список использованных источников (ГОСТ Р 7.0.5-2008, электронные ресурсы —
ГОСТ 7.82-2001). Порядок в записке — по первому упоминанию в тексте.
Источники 1–5 методических указаний включены обязательно."""

ACCESS = "04.11.2026"

SOURCES = {
    # --- из списка рекомендуемой литературы методических указаний
    "jones": "Джонс, М. Т. Программирование искусственного интеллекта в приложениях / "
             "М. Т. Джонс ; пер. с англ. А. И. Осипова. – М. : ДМК Пресс, 2011. – 312 с.",
    "zhdanov": "Жданов, А. А. Автономный искусственный интеллект [Электронный ресурс] / "
               "А. А. Жданов. – М. : БИНОМ. Лаборатория знаний, 2012. – Режим доступа: "
               f"http://znanium.com/bookread2.php?book=539035 (дата обращения: {ACCESS}).",
    "stankevich": "Станкевич, Л. А. Искусственный интеллект и искусственный разум в "
                  "робототехнике : учеб. пособие / Л. А. Станкевич, Е. И. Юревич. – СПб. : "
                  "Изд-во Политехн. ун-та, 2012. – 167 с.",
    "chubukova": "Чубукова, И. А. Data Mining / И. А. Чубукова. – М. : Интернет-университет "
                 "информационных технологий : БИНОМ. Лаборатория знаний, 2006. – 382 с.",
    "borovskaya": "Боровская, Е. В. Основы искусственного интеллекта [Электронный ресурс] / "
                  "Е. В. Боровская, Н. А. Давыдова. – 3-е изд. (эл.). – М. : Лаборатория "
                  "знаний, 2016. – 130 с. – Режим доступа: "
                  f"http://znanium.com/catalog/product/366789 (дата обращения: {ACCESS}).",
    # --- генетические алгоритмы и нечёткая логика
    "rutkovskaya": "Рутковская, Д. Нейронные сети, генетические алгоритмы и нечеткие системы / "
                   "Д. Рутковская, М. Пилиньский, Л. Рутковский ; пер. с польск. "
                   "И. Д. Рудинского. – М. : Горячая линия – Телеком, 2006. – 452 с.",
    "gladkov": "Гладков, Л. А. Генетические алгоритмы / Л. А. Гладков, В. В. Курейчик, "
               "В. М. Курейчик ; под ред. В. М. Курейчика. – 2-е изд., испр. и доп. – М. : "
               "Физматлит, 2006. – 320 с.",
    "leonenkov": "Леоненков, А. В. Нечеткое моделирование в среде MATLAB и fuzzyTECH / "
                 "А. В. Леоненков. – СПб. : БХВ-Петербург, 2005. – 736 с.",
    "shtovba": "Штовба, С. Д. Проектирование нечетких систем средствами MATLAB / "
               "С. Д. Штовба. – М. : Горячая линия – Телеком, 2007. – 288 с.",
    "pegat": "Пегат, А. Нечеткое моделирование и управление / А. Пегат ; пер. с англ. – М. : "
             "БИНОМ. Лаборатория знаний, 2009. – 798 с.",
    "holland": "Holland, J. H. Adaptation in Natural and Artificial Systems / J. H. Holland. – "
               "Ann Arbor : University of Michigan Press, 1975. – 183 p.",
    "goldberg": "Goldberg, D. E. Genetic Algorithms in Search, Optimization, and Machine "
                "Learning / D. E. Goldberg. – Reading : Addison-Wesley, 1989. – 412 p.",
    "zadeh": "Zadeh, L. A. Fuzzy sets / L. A. Zadeh // Information and Control. – 1965. – "
             "Vol. 8, № 3. – P. 338–353.",
    "mamdani": "Mamdani, E. H. An experiment in linguistic synthesis with a fuzzy logic "
               "controller / E. H. Mamdani, S. Assilian // International Journal of Man-Machine "
               "Studies. – 1975. – Vol. 7, № 1. – P. 1–13.",
    "davis": "Davis, L. Applying adaptive algorithms to epistatic domains / L. Davis // "
             "Proceedings of the 9th International Joint Conference on Artificial "
             "Intelligence. – Los Angeles, 1985. – Vol. 1. – P. 162–164.",
    # --- задача маршрутизации транспорта
    "dantzig": "Dantzig, G. B. The truck dispatching problem / G. B. Dantzig, J. H. Ramser // "
               "Management Science. – 1959. – Vol. 6, № 1. – P. 80–91.",
    "solomon": "Solomon, M. M. Algorithms for the vehicle routing and scheduling problems with "
               "time window constraints / M. M. Solomon // Operations Research. – 1987. – "
               "Vol. 35, № 2. – P. 254–265.",
    "lenstra": "Lenstra, J. K. Complexity of vehicle routing and scheduling problems / "
               "J. K. Lenstra, A. H. G. Rinnooy Kan // Networks. – 1981. – Vol. 11, № 2. – "
               "P. 221–227.",
    "toth": "The Vehicle Routing Problem / ed. by P. Toth, D. Vigo. – Philadelphia : SIAM, "
            "2002. – 367 p.",
    "prins": "Prins, C. A simple and effective evolutionary algorithm for the vehicle routing "
             "problem / C. Prins // Computers & Operations Research. – 2004. – Vol. 31, "
             "№ 12. – P. 1985–2002.",
}
