from pydantic import BaseModel, Field


class CartItem(BaseModel):
    name: str
    price: int = Field(ge=1, description="Price in öre (smallest currency unit)")
    quantity: int = Field(ge=1, le=99, description="Quantity must be 1-99")


class OrderData(BaseModel):
    orderID: str = Field(min_length=1, max_length=64)
    customer: dict
    recipient: dict | None = None
    pickup: bool
    orderForMyself: bool
    items: list[dict]
    subtotal: int
    deliveryFee: int = Field(ge=0)
    total: int = Field(ge=1)
    moms: float = Field(ge=0)


class CheckoutRequest(BaseModel):
    items: list[CartItem] = Field(min_length=1)
    orderData: OrderData
