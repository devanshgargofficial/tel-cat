import asyncio
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from database import close_db, connection, init_db

SQLITE_DATABASE = Path(__file__).with_name("catalogue.db")


async def migrate():
    if not SQLITE_DATABASE.exists():
        print("No catalogue.db found; nothing to migrate.")
        return

    sqlite = sqlite3.connect(SQLITE_DATABASE)
    sqlite.row_factory = sqlite3.Row
    rows = sqlite.execute(
        """SELECT id, user_id, image_id, description, name, price, category, stock
           FROM products ORDER BY id"""
    ).fetchall()
    sqlite.close()

    await init_db()
    try:
        async with connection() as db:
            for row in rows:
                await db.execute(
                    """INSERT INTO products
                       (id, user_id, image_id, description, name, price, category, stock)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO UPDATE SET
                         user_id = EXCLUDED.user_id,
                         image_id = EXCLUDED.image_id,
                         description = EXCLUDED.description,
                         name = EXCLUDED.name,
                         price = EXCLUDED.price,
                         category = EXCLUDED.category,
                         stock = EXCLUDED.stock""",
                    tuple(row),
                )
            await db.execute("""
                SELECT setval(
                    pg_get_serial_sequence('products', 'id'),
                    COALESCE(MAX(id), 1),
                    MAX(id) IS NOT NULL
                ) FROM products
            """)
            await db.commit()
        print(f"Migrated {len(rows)} product(s) to PostgreSQL.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(migrate())
