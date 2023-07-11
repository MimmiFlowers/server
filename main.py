import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8500",
    "http://localhost:3000",
    "https://imgur.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/favorite')
def favorite_info():
    return {
    "data": [
        {
            "name": "Favorite Bouqet 1",
            "description": "This description is for bouqet 1",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "11.11"
        },
        {
            "name": "Favorite Bouqet 2",
            "description": "This description is for bouqet 2",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "22.22"
        },
        {
            "name": "Favorite Bouqet 3",
            "description": "This description is for bouqet 3",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "33.33"
        },
        {
            "name": "Favorite Bouqet 4",
            "description": "This description is for bouqet 4",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "44.44"
        }
    ]
}


@app.get('/season')
def season_info():
    return {
    "data": [
        {
            "name": "Season Bouqet 1",
            "description": "This description is for bouqet 1",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "11.11"
        },
        {
            "name": "Season Bouqet 2",
            "description": "This description is for bouqet 2",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "22.22"
        },
        {
            "name": "Season Bouqet 3",
            "description": "This description is for bouqet 3",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "33.33"
        },
        {
            "name": "Season Bouqet 4",
            "description": "This description is for bouqet 4",
            "picture": "https://i.imgur.com/0NCCt4A.png",
            "price": "44.44"
        }
    ]
}