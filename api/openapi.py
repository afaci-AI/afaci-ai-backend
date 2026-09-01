OPENAPI_TAGS = [
    {
        "name": "Table (Flat)",
        "description": (
            "Плоские таблицы с разыменованием FK — готовы для `pd.DataFrame(response.json())`. "
            "Поддерживают фильтрацию (ILIKE), сортировку и пагинацию через query-параметры."
        ),
    },
    {"name": "Products"},
    {"name": "Nutrients"},
    {"name": "Categories"},
    {"name": "Subcategories"},
    {"name": "Regions"},
    {"name": "Units"},
    {"name": "Nutrient Types"},
    {"name": "Nutrient Names"},
    {
        "name": "Calculator",
        "description": "Калькулятор пищевой и биологической ценности (методика Липатова).",
    },
    {"name": "Auth", "description": "Регистрация, вход, текущий пользователь (JWT)."},
    {
        "name": "Saved",
        "description": "Сохранённые рецептуры, группы и ранжирование рецептур (по пользователю).",
    },
    {
        "name": "App Version",
        "description": (
            "Проверка версии мобильного приложения (публично) и управление "
            "версиями/загрузка APK (только для администраторов)."
        ),
    },
]
