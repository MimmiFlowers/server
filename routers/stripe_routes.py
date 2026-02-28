import logging
import stripe
from routers.classes.classes import CheckoutRequest
from fastapi import APIRouter, HTTPException, Request, Depends
from database.dbconfig.dbconfig import get_db_connection
from database.orders import insert_order, update_order_status, get_order_status
from services.mailing import send_order_confirmation
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/stripe",
    tags=["stripe"],
    responses={404: {"description": "Not found"}}
)

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/create_checkout_session")
async def create_checkout_session(data: CheckoutRequest, conn=Depends(get_db_connection)):
    try:
        await insert_order(conn, data.orderData, status="pending")

        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=data.orderData.customer['email'],
            line_items=[
                {
                    "price_data": {
                        "currency": "sek",
                        "product_data": {
                            "name": item.name,
                        },
                        "unit_amount": item.price,
                    },
                    "quantity": item.quantity,
                }
                for item in data.items
            ],
            metadata={"orderID": data.orderData.orderID},
            success_url=settings.SUCCESS_URL + data.orderData.orderID,
            cancel_url=settings.CANCEL_URL + data.orderData.orderID,
        )
        return {"session": session}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook/session_completed")
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

        await update_order_status(conn, order_id, "paid")

        customer_email = session.get("customer_details", {}).get("email")
        if customer_email:
            send_order_confirmation(customer_email, order_id)
        else:
            logger.warning("No customer email for order %s, skipping confirmation", order_id)

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
