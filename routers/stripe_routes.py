import stripe
from routers.classes.classes import CheckoutRequest
from fastapi import APIRouter, HTTPException, Request, Depends
from database.dbconfig.dbconfig import get_db_connection
from database.orders import insert_order, update_order_status
from services.mailing import send_order_confirmation
from config import settings

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
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except Exception as e:
        return {"error": str(e)}

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session["success_url"].split("/")[-1]
        customer_email = session.customer_details.email
        await update_order_status(conn, order_id, "paid")
        send_order_confirmation(customer_email, order_id)
        print("Payment completed!", session)

    return {"status": "ok"}
