from pydantic import BaseModel, EmailStr, Field
from typing import Literal


_OPTION_CODE = r"^[a-z0-9\-]{1,40}$"
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class CartItem(BaseModel):
    name: str
    price: int = Field(ge=1, description="Price in öre (smallest currency unit)")
    quantity: int = Field(ge=1, le=99, description="Quantity must be 1-99")
    # Set for custom wreath lines. The server then ignores `name`/`price` and
    # prices the line from wreath_designs + the live option tables.
    designID: str | None = Field(default=None, pattern=UUID_PATTERN)


class WreathPlacement(BaseModel):
    slot: int = Field(ge=0, le=63, description="0-based slot index, clockwise from the bow")
    code: str = Field(pattern=_OPTION_CODE)


class WreathSpec(BaseModel):
    """What the customer chose. Codes reference the wreath_* option tables."""
    sizeCode: str = Field(pattern=_OPTION_CODE)
    materialCode: str = Field(pattern=_OPTION_CODE)
    bandCode: str | None = Field(default=None, pattern=_OPTION_CODE)
    decorations: list[WreathPlacement] = Field(default_factory=list, max_length=64)


class WreathDesignRequest(BaseModel):
    spec: WreathSpec
    # PNG data URL rendered by the browser; optional so a failed render never blocks a sale.
    image: str | None = Field(default=None, max_length=700_000)


class CustomerModel(BaseModel):
    """Customer placing the order. All fields are required."""
    email: EmailStr
    firstName: str = Field(min_length=1, max_length=100)
    lastName: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=30)


class RecipientModel(BaseModel):
    """Delivery recipient. Always present with date/time; name/phone/address conditional."""
    firstName: str = Field(max_length=100, default="")
    lastName: str = Field(max_length=100, default="")
    phone: str = Field(max_length=30, default="")
    address: str = Field(max_length=300, default="")
    date: str = Field(min_length=1, max_length=20)
    time: str = Field(min_length=1, max_length=10)


# Valid order status values
OrderStatus = Literal["pending", "paid", "expired", "failed", "cancelled"]


class OrderData(BaseModel):
    orderID: str = Field(min_length=1, max_length=64, pattern=r"^[\w\-]+$")
    locale: str = Field(default="en", max_length=10)
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
