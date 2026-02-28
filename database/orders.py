import json
from routers.classes.classes import OrderData, OrderStatus


async def insert_order(conn, order_data: OrderData, status: str = "pending"):
    try:
        async with conn.cursor() as cur:
            await cur.execute(" \
                    INSERT INTO orders ( \
                        \"orderID\", \
                        status, \
                        customer, \
                        recipient, \
                        pickup, \
                        \"orderForMyself\", \
                        items, \
                        subtotal, \
                        \"deliveryFee\", \
                        total, \
                        moms \
                    ) \
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) \
                ", (
                    order_data.orderID,
                    status,
                    order_data.customer.model_dump_json(),
                    order_data.recipient.model_dump_json() if order_data.recipient else None,
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


async def get_order_status(conn, order_id: str) -> str | None:
    """Return the current status of an order, or None if it doesn't exist."""
    async with conn.cursor() as cur:
        await cur.execute(
            'SELECT status FROM orders WHERE "orderID"=%s',
            (order_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else None


async def update_order_status(conn, order_id: str, status: OrderStatus):
    """Update order status. Only accepts valid OrderStatus values."""
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                'UPDATE orders SET status=%s, "updatedAt"=CURRENT_TIMESTAMP WHERE "orderID"=%s',
                (status, order_id),
            )
            await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise e
