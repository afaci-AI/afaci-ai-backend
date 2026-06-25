from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.openapi import OPENAPI_TAGS
from api.router import register_routers

app = FastAPI(title="AFACI API", openapi_tags=OPENAPI_TAGS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routers(app)