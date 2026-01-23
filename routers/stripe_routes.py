import os, stripe
from dotenv import load_dotenv
from routers.classes.classes import CheckoutRequest
from fastapi import APIRouter, HTTPException, Request, Depends
from database.dbconfig.dbconfig import get_db_connection
from database.orders import insert_order, update_order_status

ENV = os.environ.get("ENV", "dev")

if ENV == "dev":
    load_dotenv(".env.dev")
else:
    load_dotenv(".env.stg")

router = APIRouter(
    prefix="/stripe",
    tags=["stripe"],
    responses={404: {"description": "Not found"}}
)

# conn = get_db_connection()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/create_checkout_session")
async def create_checkout_session(data: CheckoutRequest, conn=Depends(get_db_connection)):
    try:
        await insert_order(conn, data.orderData, status="pending")

        session = stripe.checkout.Session.create(
            mode="payment",
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
            success_url=os.getenv("SUCCESS_URL") + data.orderData.orderID,
            cancel_url=os.getenv("CANCEL_URL") + data.orderData.orderID,
        )
        return {"session": session}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook/session_completed")
async def stripe_webhook(request: Request, conn=Depends(get_db_connection)):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except Exception as e:
        return {"error": str(e)}

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session["success_url"].split("/")[-1]
        await update_order_status(conn, order_id, "paid")
        print("Payment completed!", session)

    return {"status": "ok"}
