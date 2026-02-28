import config  # noqa: F401 — must be first import to load & validate env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import data_routes, stripe_routes
from database.dbconfig.dbconfig import lifespan
from config import CORS_ORIGINS

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stripe_routes.router)
app.include_router(data_routes.router)