"""initial schema

Revision ID: 79140f858d29
Revises:
Create Date: 2026-02-28 12:56:14.770177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79140f858d29'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables, indexes, triggers."""
    # --- collections (before products, referenced by FK) ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            "collectionID" SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            image TEXT
        )
    """)

    # --- products ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS products (
            "productID" SERIAL PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description JSONB,
            price NUMERIC(10, 2) NOT NULL,
            stock INT NOT NULL DEFAULT 0,
            category TEXT,
            "collectionID" INT REFERENCES collections("collectionID") ON DELETE SET NULL,
            image TEXT,
            contents TEXT[],
            "createdAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_products_collection ON products("collectionID")')
    op.execute('CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)')

    # --- orders ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            "orderID" TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            customer JSONB NOT NULL,
            recipient JSONB,
            pickup BOOLEAN NOT NULL DEFAULT FALSE,
            "orderForMyself" BOOLEAN NOT NULL DEFAULT FALSE,
            items JSONB NOT NULL,
            subtotal INT NOT NULL,
            "deliveryFee" INT NOT NULL DEFAULT 0,
            total INT NOT NULL,
            moms INT NOT NULL DEFAULT 0,
            "createdAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute('CREATE INDEX IF NOT EXISTS idx_orders_orderid ON orders("orderID")')
    op.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')

    # --- updatedAt trigger function (shared) ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW."updatedAt" = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_orders_updated_at ON orders;
        CREATE TRIGGER trg_orders_updated_at
            BEFORE UPDATE ON orders
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trg_products_updated_at ON products;
        CREATE TRIGGER trg_products_updated_at
            BEFORE UPDATE ON products
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at()
    """)


def downgrade() -> None:
    """Drop all tables and the shared trigger function."""
    op.execute("DROP TRIGGER IF EXISTS trg_products_updated_at ON products")
    op.execute("DROP TRIGGER IF EXISTS trg_orders_updated_at ON orders")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")
    op.execute("DROP TABLE IF EXISTS orders")
    op.execute("DROP TABLE IF EXISTS collections")
    op.execute("DROP TABLE IF EXISTS products")
