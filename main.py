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
            "picture": "https://i.imgur.com/ScOiPDx.jpg",
            "price": "1111"
        },
        {
            "name": "Favorite Bouqet 2",
            "description": "This description is for bouqet 2",
            "picture": "https://i.imgur.com/RgtoxyG.jpg",
            "price": "2222"
        },
        {
            "name": "Favorite Bouqet 3",
            "description": "This description is for bouqet 3",
            "picture": "https://i.imgur.com/hMmLLC2.jpg",
            "price": "3333"
        },
        {
            "name": "Favorite Bouqet 4",
            "description": "This description is for bouqet 4",
            "picture": "https://i.imgur.com/TAPsYEH.jpg",
            "price": "4444"
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
            "picture": "https://i.imgur.com/HnNqj2k.jpg",
            "price": "1111"
        },
        {
            "name": "Season Bouqet 2",
            "description": "This description is for bouqet 2",
            "picture": "https://i.imgur.com/EwKcxnl.jpg",
            "price": "2222"
        },
        {
            "name": "Season Bouqet 3",
            "description": "This description is for bouqet 3",
            "picture": "https://i.imgur.com/5PMLpcl.jpg",
            "price": "3333"
        },
        {
            "name": "Season Bouqet 4",
            "description": "This description is for bouqet 4",
            "picture": "https://i.imgur.com/vbSwDFa.jpg",
            "price": "4444"
        }
    ]
}