from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

# app.mount("/assets", StaticFiles(directory="assets"), name="assets")

@app.get('/collections')
async def get_collections():
    return {
        "data": [
            {
                "id": "1",
                "name": "Season",
                "picture": "https://i.imgur.com/TAPsYEH.jpg"
            },
            {
                "id": "2",
                "name": "Mono bouquets",
                "picture": "https://i.imgur.com/TAPsYEH.jpg"
            },
            {
                "id": "3",
                "name": "Boxes and Baskets",
                "picture": "https://i.imgur.com/TAPsYEH.jpg"
            },
            {
                "id": "4",
                "name": "Gifts",
                "picture": "https://i.imgur.com/TAPsYEH.jpg"
            }
        ]
    }

app.include_router(stripe_routes.router)
app.include_router(data_routes.router)