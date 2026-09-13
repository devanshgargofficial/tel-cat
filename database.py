import os
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Set the DATABASE_URL environment variable before starting")

pool = AsyncConnectionPool(
    conninfo=DATABASE_URL,
    min_size=int(os.getenv("DB_POOL_MIN_SIZE", "1")),
    max_size=int(os.getenv("DB_POOL_MAX_SIZE", "10")),
    open=False,
    kwargs={"row_factory": dict_row},
)


@asynccontextmanager
async def connection():
    async with pool.connection() as conn:
        yield conn


async def init_db():
    await pool.open()
    async with connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                image_id TEXT NOT NULL,
                description TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT 'Unnamed product',
                price NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (price >= 0),
                category TEXT,
                stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id BIGSERIAL PRIMARY KEY,
                shop_owner_id BIGINT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT,
                total NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id BIGSERIAL PRIMARY KEY,
                order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id BIGINT NOT NULL,
                product_name TEXT NOT NULL,
                unit_price NUMERIC(12, 2) NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0)
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS products_user_id_idx ON products(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS products_category_idx ON products(user_id, category)")
        await conn.commit()


async def close_db():
    await pool.close()
