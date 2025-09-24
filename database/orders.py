import json
from routers.classes.classes import OrderData

async def insert_order(conn, order_data: OrderData, status: str = "pending"):
    try:
        async with conn.cursor() as cur:
            await cur.execute(" \
                    INSERT INTO orders ( \
                        orderID, \
                        status, \
                        customer, \
                        recipient, \
                        pickup, \
                        orderForMyself, \
                        items, \
                        subtotal, \
                        deliveryFee, \
                        total, \
                        moms \
                    ) \
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) \
                ", (
                    order_data.orderID,
                    status,
                    json.dumps(order_data.customer),
                    json.dumps(order_data.recipient) if order_data.recipient else None,
                    order_data.pickup,
                    order_data.orderForMyself,
                    json.dumps(order_data.items),
                    order_data.subtotal,
                    order_data.deliveryFee,
                    order_data.total,
                    order_data.moms               
                )
            )
            await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e


async def update_order_status(conn, order_id: str, status: str):
    try:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE orders SET status=%s WHERE orderID=%s", (status, order_id))
            await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e