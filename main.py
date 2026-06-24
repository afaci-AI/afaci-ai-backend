from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import api
from routers import table
from routers import calculator
from routers import auth
from routers import saved

app = FastAPI(
    title="AFACI API",
    openapi_tags=[
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
        {"name": "Calculator", "description": "Калькулятор пищевой и биологической ценности (методика Липатова)."},
        {"name": "Auth", "description": "Регистрация, вход, текущий пользователь (JWT)."},
        {"name": "Saved", "description": "Сохранённые рецептуры, группы и ранжирование рецептур (по пользователю)."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(table.router)
app.include_router(api.router)
app.include_router(calculator.router)
app.include_router(auth.router)
app.include_router(saved.router)