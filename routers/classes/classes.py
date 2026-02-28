from pydantic import BaseModel, EmailStr, Field
from typing import Literal


class CartItem(BaseModel):
    name: str
    price: int = Field(ge=1, description="Price in öre (smallest currency unit)")
    quantity: int = Field(ge=1, le=99, description="Quantity must be 1-99")


class CustomerModel(BaseModel):
    """Customer placing the order. All fields are required."""
    email: EmailStr
    firstName: str = Field(min_length=1, max_length=100)
    lastName: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=30)


class RecipientModel(BaseModel):
    """Delivery recipient. Required when pickup=false and orderForMyself=false."""
    firstName: str = Field(min_length=1, max_length=100)
    lastName: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=30)
    address: str = Field(min_length=1, max_length=300)
    date: str = Field(min_length=1, max_length=20)
    time: str = Field(min_length=1, max_length=10)


# Valid order status values
OrderStatus = Literal["pending", "paid", "expired", "failed", "cancelled"]


class OrderData(BaseModel):
    orderID: str = Field(min_length=1, max_length=64, pattern=r"^[\w\-]+$")
    customer: CustomerModel
    recipient: RecipientModel | None = None
    pickup: bool
    orderForMyself: bool
    items: list[dict]
    subtotal: int
    deliveryFee: int = Field(ge=0)
    total: int = Field(ge=1)
    moms: int = Field(ge=0)


class CheckoutRequest(BaseModel):
    items: list[CartItem] = Field(min_length=1)
    orderData: OrderData
