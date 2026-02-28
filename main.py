import config  # noqa: F401 — must be first import to load & validate env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import data_routes, stripe_routes
from database.dbconfig.dbconfig import lifespan

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost",
    "http://localhost:8500",
    "http://localhost:3000",
    "http://localhost:5173",
    "https://imgur.com",
    "https://i.imgur.com",
    "https://stg.mimmiflowers.se",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stripe_routes.router)
app.include_router(data_routes.router)