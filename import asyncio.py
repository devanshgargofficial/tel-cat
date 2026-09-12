import asyncio
import os
import aiosqlite
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Set the BOT_TOKEN environment variable before starting the bot")

bot = Bot(TOKEN)
dp = Dispatcher()
SHOP_URL = os.getenv("SHOP_URL", "http://localhost:8080")


class ProductForm(StatesGroup):
    waiting_for_image = State()
    waiting_for_description = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_category = State()
    waiting_for_stock = State()


def product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Edit", callback_data=f"edit:{product_id}"),
        InlineKeyboardButton(text="Delete", callback_data=f"delete:{product_id}"),
    ]])


def category_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=category, callback_data=f"category:{index}")
    ] for index, category in enumerate(categories)])


async def send_products(message: Message, user_id: int, category: str | None = None):
    async with aiosqlite.connect("catalogue.db") as db:
        if category is None:
            cursor = await db.execute("""
                SELECT id, image_id, description, name, price, category, stock
                FROM products
                WHERE user_id = ?
                ORDER BY id DESC
            """, (user_id,))
        else:
            cursor = await db.execute("""
                SELECT id, image_id, description, name, price, category, stock
                FROM products
                WHERE user_id = ? AND LOWER(category) = LOWER(?)
                ORDER BY id DESC
            """, (user_id, category))
        products = await cursor.fetchall()

    if not products:
        if category is None:
            await message.answer("Your catalogue is empty.")
        else:
            await message.answer(f'No products found in category "{category}".')
        return

    for product_id, image_id, description, name, price, product_category, stock in products:
        details = f"{name}\n{description}\nPrice: {price:g}\nStock: {stock}"
        if product_category:
            details += f"\nCategory: {product_category}"
        await message.answer_photo(
            photo=image_id,
            caption=details,
            reply_markup=product_keyboard(product_id),
        )


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Welcome!\n\n"
        "Use /new to add an item.\n"
        "Use /catalog to view your catalogue.\n"
        "Use /cancel to stop the current action."
    )


@dp.message(Command("shop"))
async def shop(message: Message):
    shop_link = f"{SHOP_URL.rstrip('/')}/{message.from_user.id}"
    await message.answer(f"Open my shop:\n{shop_link}")


@dp.message(Command("new"))
async def new_item(message: Message, state: FSMContext):
    await state.set_state(ProductForm.waiting_for_image)
    await message.answer("Send me an image.")


@dp.message(ProductForm.waiting_for_image, F.photo)
async def receive_image(message: Message, state: FSMContext):
    image_id = message.photo[-1].file_id

    await state.update_data(image_id=image_id)
    await state.set_state(ProductForm.waiting_for_description)
    await message.answer("Now send a description.")


@dp.message(ProductForm.waiting_for_description, F.text)
async def receive_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(ProductForm.waiting_for_name)
    await message.answer("Product name?")


@dp.message(ProductForm.waiting_for_name, F.text)
async def receive_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ProductForm.waiting_for_price)
    await message.answer("Price? Send a number, or 0 if you do not want to show one.")


@dp.message(ProductForm.waiting_for_price, F.text)
async def receive_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Please send a valid non-negative price.")
        return

    await state.update_data(price=price)
    await state.set_state(ProductForm.waiting_for_category)
    await message.answer("Category? Send - if you want to skip it.")


@dp.message(ProductForm.waiting_for_category, F.text)
async def receive_category(message: Message, state: FSMContext):
    await state.update_data(category=None if message.text == "-" else message.text)
    await state.set_state(ProductForm.waiting_for_stock)
    await message.answer("How many are in stock? Send a whole number.")


@dp.message(ProductForm.waiting_for_stock, F.text)
async def receive_stock(message: Message, state: FSMContext):
    try:
        stock = int(message.text)
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("Please send a non-negative whole number.")
        return

    data = await state.get_data()
    async with aiosqlite.connect("catalogue.db") as db:
        if data.get("edit_id"):
            await db.execute("""
                UPDATE products
                SET description = ?, name = ?, price = ?, category = ?, stock = ?
                WHERE id = ? AND user_id = ?
            """, (
                data["description"],
                data["name"],
                data["price"],
                data["category"],
                stock,
                data["edit_id"],
                message.from_user.id,
            ))
            confirmation = "Item updated."
        else:
            await db.execute("""
                INSERT INTO products
                    (user_id, image_id, description, name, price, category, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                message.from_user.id,
                data["image_id"],
                data["description"],
                data["name"],
                data["price"],
                data["category"],
                stock,
            ))
            confirmation = "Item added to your catalogue."
        await db.commit()

    await state.clear()
    await message.answer(f"{confirmation} Use /catalog to view it.")


@dp.message(Command("catalog"))
async def show_catalog(message: Message):
    await send_products(message, message.from_user.id)


@dp.message(Command("listcat"))
async def list_categories(message: Message):
    async with aiosqlite.connect("catalogue.db") as db:
        cursor = await db.execute("""
            SELECT DISTINCT category
            FROM products
            WHERE user_id = ? AND category IS NOT NULL AND TRIM(category) != ''
            ORDER BY category COLLATE NOCASE
        """, (message.from_user.id,))
        categories = [row[0] for row in await cursor.fetchall()]

    if not categories:
        await message.answer("No categories found. Add a product with /new first.")
        return

    await message.answer("Choose a category:", reply_markup=category_keyboard(categories))


@dp.message(Command("category"))
async def products_by_category(message: Message):
    category = message.text.partition(" ")[2].strip()
    if not category:
        await message.answer("Usage: /category category_name")
        return
    await send_products(message, message.from_user.id, category)


@dp.callback_query(F.data.startswith("category:"))
async def category_selected(callback: CallbackQuery):
    category_index = int(callback.data.split(":", 1)[1])
    async with aiosqlite.connect("catalogue.db") as db:
        cursor = await db.execute("""
            SELECT DISTINCT category
            FROM products
            WHERE user_id = ? AND category IS NOT NULL AND TRIM(category) != ''
            ORDER BY category COLLATE NOCASE
            LIMIT 1 OFFSET ?
        """, (callback.from_user.id, category_index))
        selected = await cursor.fetchone()

    if not selected:
        await callback.answer("Category not found", show_alert=True)
        return

    await callback.answer()
    await send_products(callback.message, callback.from_user.id, selected[0])


@dp.callback_query(F.data.startswith("delete:"))
async def delete_product(callback: CallbackQuery):
    product_id = int(callback.data.split(":", 1)[1])
    async with aiosqlite.connect("catalogue.db") as db:
        await db.execute(
            "DELETE FROM products WHERE id = ? AND user_id = ?",
            (product_id, callback.from_user.id),
        )
        await db.commit()
    await callback.message.delete()
    await callback.answer("Item deleted")


@dp.callback_query(F.data.startswith("edit:"))
async def edit_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":", 1)[1])
    async with aiosqlite.connect("catalogue.db") as db:
        cursor = await db.execute(
            "SELECT id, image_id, description, name, price, category, stock "
            "FROM products WHERE id = ? AND user_id = ?",
            (product_id, callback.from_user.id),
        )
        product = await cursor.fetchone()

    if not product:
        await callback.answer("Item not found", show_alert=True)
        return

    await state.update_data(edit_id=product_id, image_id=product[1])
    await state.set_state(ProductForm.waiting_for_description)
    await callback.message.answer("Send the new description.")
    await callback.answer()


@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Action cancelled.")


async def main():
    async with aiosqlite.connect("catalogue.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                image_id TEXT NOT NULL,
                description TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT 'Unnamed product',
                price REAL NOT NULL DEFAULT 0,
                category TEXT,
                stock INTEGER NOT NULL DEFAULT 0
            )
        """)
        columns = await (await db.execute("PRAGMA table_info(products)")).fetchall()
        existing_columns = {column[1] for column in columns}
        migrations = {
            "name": "ALTER TABLE products ADD COLUMN name TEXT NOT NULL DEFAULT 'Unnamed product'",
            "price": "ALTER TABLE products ADD COLUMN price REAL NOT NULL DEFAULT 0",
            "category": "ALTER TABLE products ADD COLUMN category TEXT",
            "stock": "ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 0",
        }
        for column, migration in migrations.items():
            if column not in existing_columns:
                await db.execute(migration)
        await db.commit()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())