# import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:8500",
    "http://localhost:3000",
    "http://localhost:5173",
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
async def favorite_info():
    return {
        "data": [
            {
                "id": "1",
                "name": "Favorite Bouqet 1",
                "description": "This description is for bouqet 1",
                "picture": "https://i.imgur.com/ScOiPDx.jpg",
                "price": "1111"
            },
            {
                "id": "2",
                "name": "Favorite Bouqet 2",
                "description": "This description is for bouqet 2",
                "picture": "https://i.imgur.com/RgtoxyG.jpg",
                "price": "2222"
            },
            {
                "id": "3",
                "name": "Favorite Bouqet 3",
                "description": "This description is for bouqet 3",
                "picture": "https://i.imgur.com/hMmLLC2.jpg",
                "price": "3333"
            },
            {
                "id": "4",
                "name": "Favorite Bouqet 4",
                "description": "This description is for bouqet 4",
                "picture": "https://i.imgur.com/TAPsYEH.jpg",
                "price": "4444"
            }
        ]
    }


@app.get('/season')
async def season_info():
    return {
        "data": [
            {
                "id": "5",
                "name": "Season Bouqet 1",
                "description": "This description is for bouqet 1",
                "picture": "https://i.imgur.com/HnNqj2k.jpg",
                "price": "1111"
            },
            {
                "id": "6",
                "name": "Season Bouqet 2",
                "description": "This description is for bouqet 2",
                "picture": "https://i.imgur.com/EwKcxnl.jpg",
                "price": "2222"
            },
            {
                "id": "7",
                "name": "Season Bouqet 3",
                "description": "This description is for bouqet 3",
                "picture": "https://i.imgur.com/5PMLpcl.jpg",
                "price": "3333"
            },
            {
                "id": "8",
                "name": "Season Bouqet 4",
                "description": "This description is for bouqet 4",
                "picture": "https://i.imgur.com/vbSwDFa.jpg",
                "price": "4444"
            }
        ]
    }

@app.get('/flowers')
async def get_flowers():
    return {
        "data": [
            {
                "id": "1",
                "name": "Bouquet 1",
                "category": "",
                "collection": "Monobouquets",
                "description": "This is bouquet 1",
                "picture": "https://i.imgur.com/ScOiPDx.jpg",
                "price": "1111",
                "contents": ["flower2"]
            },
            {
                "id": "2",
                "name": "Bouquet 2",
                "category": "Favorite",
                "collection": "Monobouquets",
                "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed porta tristique feugiat. Donec suscipit, risus sed porta euismod, urna sapien tempor metus, ut faucibus elit felis congue sem. Duis porta tortor libero, sed auctor diam suscipit nec. Maecenas dignissim ipsum sit amet turpis pellentesque blandit. Aenean in dictum elit, non blandit metus. Curabitur vel ornare nunc. Aenean et elit blandit, porta odio ut, viverra metus. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Fusce tincidunt enim arcu, non semper ante volutpat eget. In hac habitasse platea dictumst. Phasellus posuere turpis est, id sollicitudin purus commodo quis. Morbi porta pharetra nibh a hendrerit.",
                "picture": "https://i.imgur.com/RgtoxyG.jpg",
                "price": "2222",
                "contents": ["flower1"]
            },
            {
                "id": "3",
                "name": "Favorite Bouqet 3",
                "description": "This description is for bouqet 3",
                "picture": "https://i.imgur.com/hMmLLC2.jpg",
                "price": "3333"
            },
            {
                "id": "4",
                "name": "Favorite Bouqet 4",
                "description": "This description is for bouqet 4",
                "picture": "https://i.imgur.com/TAPsYEH.jpg",
                "price": "4444"
            },
            {
                "id": "5",
                "name": "Season Bouqet 1",
                "description": "This description is for bouqet 1",
                "picture": "https://i.imgur.com/HnNqj2k.jpg",
                "price": "1111"
            },
            {
                "id": "6",
                "name": "Season Bouqet 2",
                "description": "This description is for bouqet 2",
                "picture": "https://i.imgur.com/EwKcxnl.jpg",
                "price": "2222"
            },
            {
                "id": "7",
                "name": "Season Bouqet 3",
                "description": "This description is for bouqet 3",
                "picture": "https://i.imgur.com/5PMLpcl.jpg",
                "price": "3333"
            },
            {
                "id": "8",
                "name": "Season Bouqet 4",
                "description": "This description is for bouqet 4",
                "picture": "https://i.imgur.com/vbSwDFa.jpg",
                "price": "4444"
            }
        ]
    }

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

@app.get('/flowers/{id}')
async def get_bouquet(id: str):
    bouquets = {
        "1": {
            "id": "1",
            "name": "Bouquet 1",
            "category": "",
            "collection": "Monobouquets",
            "description": "This is bouquet 1",
            "picture": "https://i.imgur.com/ScOiPDx.jpg",
            "price": "1111",
            "contents": ["flower2"]
        },
        "2": {
            "id": "2",
            "name": "Bouquet 2",
            "category": "Favorite",
            "collection": "Monobouquets",
            "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed porta tristique feugiat. Donec suscipit, risus sed porta euismod, urna sapien tempor metus, ut faucibus elit felis congue sem. Duis porta tortor libero, sed auctor diam suscipit nec. Maecenas dignissim ipsum sit amet turpis pellentesque blandit. Aenean in dictum elit, non blandit metus. Curabitur vel ornare nunc. Aenean et elit blandit, porta odio ut, viverra metus. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Fusce tincidunt enim arcu, non semper ante volutpat eget. In hac habitasse platea dictumst. Phasellus posuere turpis est, id sollicitudin purus commodo quis. Morbi porta pharetra nibh a hendrerit.",
            "picture": "https://i.imgur.com/RgtoxyG.jpg",
            "price": "2222",
            "contents": ["flower1"]
        },
        "3": {
            "id": "3",
            "name": "Gift 1",
            "category": "",
            "collection": "Gifts",
            "description": "This is gift 1",
            "picture": "https://i.imgur.com/hMmLLC2.jpg",
            "price": "123",
            "contents": ["component1", "component2"]
        },
        # Add more bouquets as needed
    }
    response = bouquets.get(id)
    return bouquets.get(id, {"error": "Bouquet not found"})