from pydantic import BaseModel

class CartItem(BaseModel):
    name: str
    price: int
    quantity: int

class OrderData(BaseModel):
    orderID: str
    customer: dict
    recipient: dict | None = None
    pickup: bool
    orderForMyself: bool
    items: list[dict]
    subtotal: int
    deliveryFee: int
    total: int
    moms: float

class CheckoutRequest(BaseModel):
    items: list[CartItem]
    orderData: OrderData