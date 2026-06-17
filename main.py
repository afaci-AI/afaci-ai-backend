from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import api
from routers import table

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