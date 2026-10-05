import json
import logging
import os
import re
import uuid
import stripe
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from database.dbconfig.dbconfig import get_db_connection
from database.orders import insert_order, update_order_status, get_order_status, get_order_by_id
from database.products import get_product_prices_by_names
from database.wreath import get_wreath_catalog, get_wreath_design
from routers.classes.classes import CheckoutRequest, WreathSpec
from services.mailing import send_order_confirmation
from services.wreath import (
    DISPLAY_NAME,
    WreathSpecError,
    describe_summary,
    lang_for,
    validate_and_price,
)
from services.wreath import order_item as wreath_order_item
from config import settings

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

# Delivery fee in SEK (must match client-side constant)
DELIVERY_FEE_SEK = 99
FREE_DELIVERY_THRESHOLD_SEK = 999
# Swedish VAT rate
VAT_RATE = 0.25
# Stripe product descriptions are short; keep the wreath option list well under any limit
_STRIPE_DESCRIPTION_MAX = 480

# Bot notification URL — optional; if not set, notifications are silently skipped
BOT_NOTIFICATION_URL = os.environ.get("BOT_NOTIFICATION_URL", "")

router = APIRouter(
    prefix="/stripe",
    tags=["stripe"],
    responses={404: {"description": "Not found"}}
)

stripe.api_key = settings.STRIPE_SECRET_KEY


async def _price_wreath_lines(conn, wreath_items, locale: str) -> tuple[list[dict], list[dict], int]:
    """Price custom wreath lines from their stored designs + the live option tables.

    Returns (stripe_line_items, order_item_entries, subtotal_delta_ore). Raises
    HTTPException(400) with a customer-safe message when a design is missing or
    references a retired option. Client-supplied name/price are never used.
    """
    try:
        catalog = await get_wreath_catalog(conn)
    except Exception as e:
        logger.error("Failed to load wreath options for checkout: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    lang = lang_for(locale)
    line_items: list[dict] = []
    order_entries: list[dict] = []
    subtotal_ore = 0
    for item in wreath_items:
        try:
            design = await get_wreath_design(conn, item.designID)
        except Exception as e:
            logger.error("Failed to load wreath design %s for checkout: %s", item.designID, e)
            raise HTTPException(status_code=500, detail="Internal server error")
        if design is None:
            raise HTTPException(
                status_code=400,
                detail="Custom wreath not found. Please build it again.",
            )
        try:
            priced = validate_and_price(WreathSpec(**design["spec"]), catalog)
        except WreathSpecError:
            raise HTTPException(
                status_code=400,
                detail="Your custom wreath contains an option that is no longer available. Please build it again.",
            )
        price_ore = int(priced["price"] * 100)
        subtotal_ore += price_ore * item.quantity
        product_data = {
            "name": DISPLAY_NAME[lang],
            "description": describe_summary(priced["summary"], lang)[:_STRIPE_DESCRIPTION_MAX],
        }
        picture = design["imageUrl"]
        if picture and picture.startswith("https://"):
            product_data["images"] = [picture]  # Stripe must be able to fetch it publicly
        line_items.append({
            "price_data": {
                "currency": "sek",
                "product_data": product_data,
                "unit_amount": price_ore,
            },
            "quantity": item.quantity,
        })
        order_entries.append(
            wreath_order_item(item.designID, priced, item.quantity, locale, design["imageUrl"])
        )
    return line_items, order_entries, subtotal_ore


@router.post("/create_checkout_session")
@limiter.limit("10/minute")
async def create_checkout_session(request: Request, data: CheckoutRequest, conn=Depends(get_db_connection)):
    # --- Server-side price validation ---
    # Catalogue products are priced by name from `products`; custom wreaths
    # (lines with a designID) are priced from wreath_designs + the live option
    # tables. Client-supplied prices are never used for either.
    product_items = [item for item in data.items if item.designID is None]
    wreath_items = [item for item in data.items if item.designID is not None]

    product_names = [item.name for item in product_items]
    db_prices = await get_product_prices_by_names(conn, product_names)

    # Verify all products exist
    missing = [name for name in product_names if name not in db_prices]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown products: {', '.join(missing)}",
        )

    # Build Stripe line items with DB-verified prices
    line_items = []
    subtotal_ore = 0  # in öre (SEK * 100)

    for item in product_items:
        # DB price is NUMERIC(10,2) in SEK → convert to öre (int)
        price_ore = int(db_prices[item.name] * 100)
        subtotal_ore += price_ore * item.quantity
        line_items.append({
            "price_data": {
                "currency": "sek",
                "product_data": {"name": item.name},
                "unit_amount": price_ore,
            },
            "quantity": item.quantity,
        })

    if wreath_items:
        wreath_lines, server_wreath_entries, wreath_ore = await _price_wreath_lines(
            conn, wreath_items, data.orderData.locale
        )
        line_items.extend(wreath_lines)
        subtotal_ore += wreath_ore
        # Replace the client's wreath entries with server-built ones so the
        # receipt and the shop notification never show client-controlled text.
        data.orderData.items = [
            entry for entry in data.orderData.items if not entry.get("designID")
        ] + server_wreath_entries

    # Add delivery fee only when not pickup AND subtotal is below threshold
    delivery_fee_ore = 0
    if not data.orderData.pickup and subtotal_ore < FREE_DELIVERY_THRESHOLD_SEK * 100:
        delivery_fee_ore = DELIVERY_FEE_SEK * 100
        line_items.append({
            "price_data": {
                "currency": "sek",
                "product_data": {"name": "Delivery Fee"},
                "unit_amount": delivery_fee_ore,
            },
            "quantity": 1,
        })

    # Calculate totals server-side
    total_ore = subtotal_ore + delivery_fee_ore
    moms_ore = int(total_ore * VAT_RATE)

    # Override client-supplied monetary values with server-calculated ones
    # All monetary values stored in öre (SEK × 100) for consistency
    data.orderData.subtotal = subtotal_ore
    data.orderData.deliveryFee = delivery_fee_ore
    data.orderData.total = total_ore
    data.orderData.moms = moms_ore

    # Generate orderID server-side — never trust client-supplied IDs
    order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
    data.orderData.orderID = order_id

    try:
        await insert_order(conn, data.orderData, status="pending")

        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=data.orderData.customer.email,
            line_items=line_items,
            metadata={"orderID": data.orderData.orderID},
            success_url=settings.SUCCESS_URL + data.orderData.orderID,
            cancel_url=settings.CANCEL_URL + data.orderData.orderID,
        )
        return {"session": session}
    except Exception as e:
        logger.error("Checkout session creation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook/session_completed")
@limiter.limit("60/minute")
async def stripe_webhook(request: Request, conn=Depends(get_db_connection)):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    # --- 1. Verify signature — reject with 400 on failure ---
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Webhook signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error("Webhook payload error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event["type"]

    # --- 2. Handle checkout.session.completed ---
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("orderID")

        # Fallback: parse from success_url if metadata is missing
        # (handles in-flight sessions created before metadata was added)
        if not order_id:
            order_id = session.get("success_url", "").split("/")[-1]

        if not order_id:
            logger.error("No orderID found in webhook session: %s", session.get("id"))
            return {"status": "ok"}

        # --- 3. Idempotency check — skip if already paid ---
        current_status = await get_order_status(conn, order_id)
        if current_status == "paid":
            logger.info("Order %s already paid, skipping duplicate webhook", order_id)
            return {"status": "ok"}

        if current_status is None:
            logger.error("Order %s not found in database", order_id)
            return {"status": "ok"}

        # --- DB update and email are in separate try/except blocks ---
        # so email failure never prevents the order status from being updated.
        try:
            await update_order_status(conn, order_id, "paid")
            logger.info("Order %s marked as paid", order_id)
        except Exception as e:
            logger.error("Failed to update order %s to paid: %s", order_id, e)
            raise HTTPException(status_code=500, detail="Internal server error")

        order_data = None
        try:
            customer_email = session.get("customer_details", {}).get("email")
            if customer_email:
                order_data = await get_order_by_id(conn, order_id)
                if order_data:
                    await send_order_confirmation(customer_email, order_data)
                else:
                    logger.warning("Order %s not found for email, skipping confirmation", order_id)
            else:
                logger.warning("No customer email for order %s, skipping confirmation", order_id)
        except Exception as e:
            logger.error("Failed to send confirmation email for order %s: %s", order_id, e)

        # --- Notify Telegram bot (fire-and-forget) ---
        if BOT_NOTIFICATION_URL:
            try:
                if not order_data:
                    order_data = await get_order_by_id(conn, order_id)
                if order_data:
                    # Serialize datetime fields for JSON transport
                    serializable = {
                        k: (v.isoformat() if isinstance(v, datetime) else v)
                        for k, v in order_data.items()
                    }
                    # Include environment so the bot can label non-production orders
                    serializable["env"] = os.environ.get("ENV", "dev")
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.post(
                            BOT_NOTIFICATION_URL,
                            content=json.dumps(serializable),
                            headers={"Content-Type": "application/json"},
                        )
                        logger.info(
                            "Bot notified for order %s (status=%d)", order_id, resp.status_code
                        )
            except Exception as e:
                logger.error("Failed to notify bot for order %s: %s", order_id, e)

        logger.info("Payment completed for order %s", order_id)

    # --- 4. Handle session expired — clean up stuck pending orders ---
    elif event_type == "checkout.session.expired":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("orderID")
        if not order_id:
            order_id = session.get("success_url", "").split("/")[-1]

        if order_id:
            current_status = await get_order_status(conn, order_id)
            if current_status == "pending":
                await update_order_status(conn, order_id, "expired")
                logger.info("Order %s expired (session timed out)", order_id)

    elif event_type == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]
        logger.warning(
            "Payment failed for payment_intent %s: %s",
            payment_intent.get("id"),
            payment_intent.get("last_payment_error", {}).get("message", "unknown"),
        )

    return {"status": "ok"}


@router.get("/order/{order_id}/status")
@limiter.limit("30/minute")
async def get_order_status_endpoint(
    request: Request,
    order_id: str,
    conn=Depends(get_db_connection),
):
    """Return the payment status of an order.

    Used by the SuccessPage to verify the order was actually paid
    before showing a success message and clearing the cart.
    """
    if not re.match(r"^[\w\-]+$", order_id) or len(order_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid order ID format")

    status = await get_order_status(conn, order_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return {"orderID": order_id, "status": status}
