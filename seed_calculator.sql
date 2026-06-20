-- ============================================================================
-- Seed-данные для Калькулятора пищевой и биологической ценности
-- (методика Липатова). Запуск:
--   PGPASSWORD=d psql -U erikomaraliev -h localhost -d afaci -f afaci/seed_calculator.sql
-- Идемпотентен: повторный запуск не создаёт дубликатов.
-- ============================================================================
BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Единица измерения «г» (граммы) для рецептур
-- ----------------------------------------------------------------------------
INSERT INTO units (id, name)
VALUES (gen_random_uuid(), 'г')
ON CONFLICT (name) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. Нутриент «Пищевые волокна» (тип «Химический состав», %/100г)
-- ----------------------------------------------------------------------------
INSERT INTO nutrients_names (id, nutrient_type_id, name)
SELECT gen_random_uuid(), nt.id, 'Пищевые волокна'
FROM nutrients_types nt
WHERE nt.name = 'Химический состав'
ON CONFLICT (name) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2b. Отдельный «регион» для стандартизированного рецептурного сырья.
--     Нужен, чтобы ингредиенты рецептур не пересекались с реальными
--     региональными продуктами банка (у которых свой аминокислотный профиль),
--     а эталонный расчёт оставался воспроизводимым.
-- ----------------------------------------------------------------------------
INSERT INTO regions (id, name)
VALUES (gen_random_uuid(), 'Рецептурное сырьё')
ON CONFLICT (name) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 3. Новые таблицы: эталонные белки и рецептуры
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reference_proteins (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        varchar NOT NULL UNIQUE,
    year        integer,
    is_default  boolean NOT NULL DEFAULT false,
    description text
);

CREATE TABLE IF NOT EXISTS reference_protein_values (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_protein_id uuid NOT NULL REFERENCES reference_proteins(id) ON DELETE CASCADE,
    amino_acid           varchar NOT NULL,          -- ИЗО / ЛЕЙ / ВАЛ / МЕТ+ЦИС / Ф+Т / ТРИ / ТРЕ / ЛИЗ
    value                double precision NOT NULL,  -- г/100 г белка
    sort_order           integer NOT NULL DEFAULT 0,
    UNIQUE (reference_protein_id, amino_acid)
);

CREATE TABLE IF NOT EXISTS recipes (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        varchar NOT NULL UNIQUE,
    description text,
    sample_type varchar NOT NULL DEFAULT 'контроль'  -- контроль / опытный
);

CREATE TABLE IF NOT EXISTS recipe_items (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id  uuid NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    product_id uuid NOT NULL REFERENCES products(id),
    amount_g   double precision NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    UNIQUE (recipe_id, product_id)
);

-- ----------------------------------------------------------------------------
-- 4. Эталонные белки ФАО/ВОЗ (1973 / 1985 / 1991)
-- ----------------------------------------------------------------------------
INSERT INTO reference_proteins (name, year, is_default, description) VALUES
 ('ФАО/ВОЗ 1973', 1973, true,
  'Классический «идеальный» (провизорный) эталонный белок ФАО/ВОЗ 1973 г. Его аминокислотный профиль оптимально сбалансирован под потребности человека и исторически опирается на состав яичного и грудного молока — белков наивысшей биологической ценности. Сумма восьми незаменимых аминокислот равна 36 г/100 г белка. Именно эта шкала применена в исходном расчёте контрольного образца, поэтому выбрана эталоном по умолчанию.'),
 ('ФАО/ВОЗ 1985', 1985, false,
  'Эталон ФАО/ВОЗ/УООН 1985 г., построенный на профиле потребностей детей дошкольного возраста (2–5 лет). Требования к ряду незаменимых кислот ниже, чем в шкале 1973 г., поэтому аминокислотные скоры по нему, как правило, выше.'),
 ('ФАО/ВОЗ 1991', 1991, false,
  'Эталон ФАО/ВОЗ 1991 г. (Expert Consultation on Protein Quality Evaluation). Подтверждает профиль потребностей детей дошкольного возраста (2–5 лет) и лежит в основе метода PDCAAS — современного стандарта оценки качества белка.')
ON CONFLICT (name) DO NOTHING;

-- Значения эталонов (г/100 г белка)
INSERT INTO reference_protein_values (reference_protein_id, amino_acid, value, sort_order)
SELECT rp.id, v.aa, v.val, v.ord
FROM reference_proteins rp
JOIN (VALUES
    -- 1973 (сумма НАК = 36)
    ('ФАО/ВОЗ 1973','ИЗО',     4.0, 1),
    ('ФАО/ВОЗ 1973','ЛЕЙ',     7.0, 2),
    ('ФАО/ВОЗ 1973','ВАЛ',     5.0, 3),
    ('ФАО/ВОЗ 1973','МЕТ+ЦИС', 3.5, 4),
    ('ФАО/ВОЗ 1973','Ф+Т',     6.0, 5),
    ('ФАО/ВОЗ 1973','ТРИ',     1.0, 6),
    ('ФАО/ВОЗ 1973','ТРЕ',     4.0, 7),
    ('ФАО/ВОЗ 1973','ЛИЗ',     5.5, 8),
    -- 1985 (дети 2–5 лет)
    ('ФАО/ВОЗ 1985','ИЗО',     2.8, 1),
    ('ФАО/ВОЗ 1985','ЛЕЙ',     6.6, 2),
    ('ФАО/ВОЗ 1985','ВАЛ',     3.5, 3),
    ('ФАО/ВОЗ 1985','МЕТ+ЦИС', 2.5, 4),
    ('ФАО/ВОЗ 1985','Ф+Т',     6.3, 5),
    ('ФАО/ВОЗ 1985','ТРИ',     1.1, 6),
    ('ФАО/ВОЗ 1985','ТРЕ',     3.4, 7),
    ('ФАО/ВОЗ 1985','ЛИЗ',     5.8, 8),
    -- 1991 (дети 2–5 лет, PDCAAS)
    ('ФАО/ВОЗ 1991','ИЗО',     2.8, 1),
    ('ФАО/ВОЗ 1991','ЛЕЙ',     6.6, 2),
    ('ФАО/ВОЗ 1991','ВАЛ',     3.5, 3),
    ('ФАО/ВОЗ 1991','МЕТ+ЦИС', 2.5, 4),
    ('ФАО/ВОЗ 1991','Ф+Т',     6.3, 5),
    ('ФАО/ВОЗ 1991','ТРИ',     1.1, 6),
    ('ФАО/ВОЗ 1991','ТРЕ',     3.4, 7),
    ('ФАО/ВОЗ 1991','ЛИЗ',     5.8, 8)
) AS v(rpname, aa, val, ord) ON rp.name = v.rpname
ON CONFLICT (reference_protein_id, amino_acid) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 5. Продукты-ингредиенты рецептуры (регион «Рецептурное сырьё»)
-- ----------------------------------------------------------------------------
INSERT INTO products (id, name, category_id, subcategory_id, region_id)
SELECT gen_random_uuid(), p.pname, c.id, s.id, r.id
FROM (VALUES
    ('Мясо говяжье котлетное',  'Мясо',                     'Мясо убойных животных'),
    ('Жир-сырец говяжий',       'Жиры, масла',              'Сало, животный жир'),
    ('Хлеб пшеничный',          'Мука, продукты из муки',   'Хлеб, лепёшки и др.'),
    ('Сухари панировочные',     'Мука, продукты из муки',   'Хлеб, лепёшки и др.'),
    ('Лук репчатый',            'Овощи и овощные продукты',  'Луковичные'),
    ('Перец чёрный молотый',    'Специи, пряности',          NULL),
    ('Соль поваренная',         'Специи, пряности',          NULL),
    ('Вода питьевая',           'Напитки, соки',             NULL)
) AS p(pname, cat, subcat)
JOIN categories c ON c.name = p.cat
LEFT JOIN subcategories s ON s.name = p.subcat AND s.category_id = c.id
CROSS JOIN (SELECT id FROM regions WHERE name = 'Рецептурное сырьё') r
ON CONFLICT (name, region_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 6a. Химический состав ингредиентов (%/100г): белок, жир, углеводы, ПВ
-- ----------------------------------------------------------------------------
INSERT INTO nutrients (id, id_product, id_name_component, id_type_component, unit_id, quantity)
SELECT gen_random_uuid(), pr.id, nn.id, nn.nutrient_type_id, u.id, m.qty
FROM (VALUES
    ('Мясо говяжье котлетное','Массовая доля белка', 17.8),
    ('Мясо говяжье котлетное','Массовая доля жира',  10.0),
    ('Мясо говяжье котлетное','Углеводы',             0.6),
    ('Мясо говяжье котлетное','Пищевые волокна',      0.0),
    ('Жир-сырец говяжий',     'Массовая доля белка',  0.98),
    ('Жир-сырец говяжий',     'Массовая доля жира',  89.0),
    ('Жир-сырец говяжий',     'Углеводы',             0.0),
    ('Жир-сырец говяжий',     'Пищевые волокна',      0.0),
    ('Хлеб пшеничный',        'Массовая доля белка',  7.9),
    ('Хлеб пшеничный',        'Массовая доля жира',   1.0),
    ('Хлеб пшеничный',        'Углеводы',            48.3),
    ('Хлеб пшеничный',        'Пищевые волокна',      3.3),
    ('Сухари панировочные',   'Массовая доля белка', 11.2),
    ('Сухари панировочные',   'Массовая доля жира',   1.4),
    ('Сухари панировочные',   'Углеводы',            67.5),
    ('Сухари панировочные',   'Пищевые волокна',      5.1),
    ('Лук репчатый',          'Массовая доля белка',  1.4),
    ('Лук репчатый',          'Массовая доля жира',   0.2),
    ('Лук репчатый',          'Углеводы',             8.2),
    ('Лук репчатый',          'Пищевые волокна',      3.0)
) AS m(pname, nname, qty)
JOIN products pr ON pr.name = m.pname
                AND pr.region_id = (SELECT id FROM regions WHERE name = 'Рецептурное сырьё')
JOIN nutrients_names nn ON nn.name = m.nname
                AND nn.nutrient_type_id = (SELECT id FROM nutrients_types WHERE name = 'Химический состав')
CROSS JOIN (SELECT id FROM units WHERE name = '%/100г') u
ON CONFLICT (id_product, id_name_component) DO UPDATE SET quantity = EXCLUDED.quantity;

-- ----------------------------------------------------------------------------
-- 6b. Аминокислотный состав (мг/100г продукта) — только говядина и хлеб.
--     Значения восстановлены из Mij (г/100г белка) исходного решения:
--     мг/100г = Mij · белок% · 10. МЕТ+ЦИС и Ф+Т разнесены на отд. кислоты так,
--     чтобы их сумма давала исходную групповую величину.
-- ----------------------------------------------------------------------------
INSERT INTO nutrients (id, id_product, id_name_component, id_type_component, unit_id, quantity)
SELECT gen_random_uuid(), pr.id, nn.id, nn.nutrient_type_id, u.id, a.qty
FROM (VALUES
    -- Говядина котлетная (белок 17.8%)
    ('Мясо говяжье котлетное','Изолейцин',     530.44),
    ('Мясо говяжье котлетное','Лейцин',       1121.40),
    ('Мясо говяжье котлетное','Валин',         640.80),
    ('Мясо говяжье котлетное','Метионин',      352.44),
    ('Мясо говяжье котлетное','Цистеин',       234.96),
    ('Мясо говяжье котлетное','Фенилаланин',   576.72),
    ('Мясо говяжье котлетное','Тирозин',       491.28),
    ('Мясо говяжье котлетное','Триптофан',     213.60),
    ('Мясо говяжье котлетное','Треонин',       658.60),
    ('Мясо говяжье котлетное','Лизин',        1210.40),
    -- Хлеб пшеничный (белок 7.9%)
    ('Хлеб пшеничный','Изолейцин',     292.30),
    ('Хлеб пшеничный','Лейцин',        513.50),
    ('Хлеб пшеничный','Валин',         331.80),
    ('Хлеб пшеничный','Метионин',      118.50),
    ('Хлеб пшеничный','Цистеин',       181.70),
    ('Хлеб пшеничный','Фенилаланин',   379.20),
    ('Хлеб пшеничный','Тирозин',       213.30),
    ('Хлеб пшеничный','Триптофан',      79.00),
    ('Хлеб пшеничный','Треонин',       213.30),
    ('Хлеб пшеничный','Лизин',         165.90)
) AS a(pname, nname, qty)
JOIN products pr ON pr.name = a.pname
                AND pr.region_id = (SELECT id FROM regions WHERE name = 'Рецептурное сырьё')
JOIN nutrients_names nn ON nn.name = a.nname
                AND nn.nutrient_type_id = (SELECT id FROM nutrients_types WHERE name = 'Аминокислотный состав')
CROSS JOIN (SELECT id FROM units WHERE name = 'мг/100г') u
ON CONFLICT (id_product, id_name_component) DO UPDATE SET quantity = EXCLUDED.quantity;

-- ----------------------------------------------------------------------------
-- 7. Контрольная рецептура «Московские котлеты» (Σ = 100 г)
-- ----------------------------------------------------------------------------
INSERT INTO recipes (id, name, description, sample_type)
VALUES (gen_random_uuid(), 'Котлеты «Московские» (контроль)',
        'Контрольный образец рубленых котлет. Рецептура на 100 г: масса в граммах численно равна доле Xᵢ, %.',
        'контроль')
ON CONFLICT (name) DO NOTHING;

INSERT INTO recipe_items (id, recipe_id, product_id, amount_g, sort_order)
SELECT gen_random_uuid(), rc.id, pr.id, ri.amt, ri.ord
FROM (VALUES
    ('Мясо говяжье котлетное', 50.00, 1),
    ('Жир-сырец говяжий',       8.94, 2),
    ('Хлеб пшеничный',         14.00, 3),
    ('Лук репчатый',            1.00, 4),
    ('Перец чёрный молотый',    0.06, 5),
    ('Соль поваренная',         1.20, 6),
    ('Вода питьевая',          20.80, 7),
    ('Сухари панировочные',     4.00, 8)
) AS ri(pname, amt, ord)
JOIN products pr ON pr.name = ri.pname
                AND pr.region_id = (SELECT id FROM regions WHERE name = 'Рецептурное сырьё')
CROSS JOIN (SELECT id FROM recipes WHERE name = 'Котлеты «Московские» (контроль)') rc
ON CONFLICT (recipe_id, product_id) DO UPDATE SET amount_g = EXCLUDED.amount_g, sort_order = EXCLUDED.sort_order;

COMMIT;

-- ----------------------------------------------------------------------------
-- Контрольные суммы
-- ----------------------------------------------------------------------------
SELECT 'reference_proteins'        AS t, count(*) FROM reference_proteins
UNION ALL SELECT 'reference_protein_values', count(*) FROM reference_protein_values
UNION ALL SELECT 'recipes',                  count(*) FROM recipes
UNION ALL SELECT 'recipe_items',             count(*) FROM recipe_items
UNION ALL SELECT 'ingredient products',      count(*) FROM products WHERE region_id=(SELECT id FROM regions WHERE name='Рецептурное сырьё') AND name IN ('Мясо говяжье котлетное','Жир-сырец говяжий','Хлеб пшеничный','Сухари панировочные','Лук репчатый','Перец чёрный молотый','Соль поваренная','Вода питьевая');
