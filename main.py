import requests
from fastapi import FastAPI

app = FastAPI()

@app.get('/favorite')
def favorite_info():
    return {
    "data": [
        {
            "name": "Favorite Bouqet 1",
            "description": "This description is for bouqet 1",
            "picture": "",
            "price": "11.11"
        },
        {
            "name": "Favorite Bouqet 2",
            "description": "This description is for bouqet 2",
            "picture": "",
            "price": "22.22"
        },
        {
            "name": "Favorite Bouqet 3",
            "description": "This description is for bouqet 3",
            "picture": "",
            "price": "33.33"
        },
        {
            "name": "Favorite Bouqet 4",
            "description": "This description is for bouqet 4",
            "picture": "",
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
            "picture": "",
            "price": "11.11"
        },
        {
            "name": "Season Bouqet 2",
            "description": "This description is for bouqet 2",
            "picture": "",
            "price": "22.22"
        },
        {
            "name": "Season Bouqet 3",
            "description": "This description is for bouqet 3",
            "picture": "",
            "price": "33.33"
        },
        {
            "name": "Season Bouqet 4",
            "description": "This description is for bouqet 4",
            "picture": "",
            "price": "44.44"
        }
    ]
}