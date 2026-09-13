import html
import io
import json
import os

from aiohttp import web
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()
from database import close_db, connection, init_db

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
  raise RuntimeError("Set the BOT_TOKEN environment variable before starting the shop")

bot = Bot(TOKEN)


async def get_shop_data(user_id: int):
    async with connection() as db:
        category_cursor = await db.execute(
            """SELECT DISTINCT category, LOWER(category) AS category_sort FROM products
               WHERE user_id = %s AND category IS NOT NULL AND TRIM(category) != ''
               ORDER BY category_sort""",
            (user_id,),
        )
        categories = [row["category"] for row in await category_cursor.fetchall()]

        product_cursor = await db.execute(
            """SELECT id, name, description, price, category, stock
               FROM products WHERE user_id = %s ORDER BY id DESC""",
            (user_id,),
        )
        products = await product_cursor.fetchall()

    return categories, products


def product_card(product):
    product_id = product["id"]
    name = product["name"]
    description = product["description"]
    price = product["price"]
    category = product["category"]
    stock = product["stock"]
    name = html.escape(name or "Unnamed product")
    description = html.escape(description or "")
    category_value = html.escape(category or "Uncategorized")
    disabled = "disabled" if stock <= 0 else ""
    stock_label = "Out of stock" if stock <= 0 else f"{stock} available"
    return f"""
      <article class="product" data-id="{product_id}" data-category="{category_value}">
        <img src="/image/{product_id}" alt="{name}" loading="lazy">
        <div class="product-body">
          <span class="category-label">{category_value}</span>
          <h2>{name}</h2>
          <p>{description}</p>
          <div class="product-footer">
            <strong>${price:.2f}</strong>
            <span class="stock">{stock_label}</span>
          </div>
          <button class="add-button" data-add="{product_id}" {disabled}>Add to cart</button>
        </div>
      </article>
    """


def shop_page(user_id: int, categories, products):
    category_buttons = ''.join(
        f'<button class="category-button" data-category="{html.escape(category)}">'
        f'{html.escape(category)}</button>'
        for category in categories
    )
    cards = ''.join(product_card(product) for product in products)
    if not cards:
        cards = '<p class="empty">This shop has no products yet.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shop {user_id}</title>
  <style>
    :root {{ --ink: #17212b; --muted: #68737d; --line: #e5e8eb; --accent: #e85d3f; --soft: #fff5f0; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--ink); background: #fafafa; font-family: Georgia, 'Times New Roman', serif; }}
    header {{ background: var(--ink); color: white; padding: 28px 5vw; display: flex; align-items: center; justify-content: space-between; gap: 20px; }}
    header h1 {{ margin: 0; font-size: clamp(1.7rem, 4vw, 2.8rem); letter-spacing: .02em; }}
    header p {{ margin: 6px 0 0; color: #bec7ce; font-family: system-ui, sans-serif; font-size: .9rem; }}
    .cart-toggle {{ border: 0; background: var(--accent); color: white; padding: 12px 16px; border-radius: 4px; cursor: pointer; font: 700 .9rem system-ui, sans-serif; }}
    .layout {{ display: grid; grid-template-columns: 220px 1fr; gap: 34px; max-width: 1280px; margin: 0 auto; padding: 36px 5vw 80px; }}
    aside {{ border-right: 1px solid var(--line); padding-right: 22px; }}
    aside h3 {{ margin: 0 0 16px; font: 700 .8rem system-ui, sans-serif; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }}
    .category-button {{ display: block; width: 100%; border: 0; background: transparent; text-align: left; padding: 9px 0; color: var(--ink); cursor: pointer; font: 1rem Georgia, serif; }}
    .category-button:hover, .category-button.active {{ color: var(--accent); }}
    .products {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 22px; align-content: start; }}
    .product {{ overflow: hidden; background: white; border: 1px solid var(--line); }}
    .product img {{ display: block; width: 100%; aspect-ratio: 1 / 1; object-fit: cover; background: #f0f1f2; }}
    .product-body {{ padding: 16px; }}
    .category-label {{ color: var(--accent); font: 700 .7rem system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; }}
    .product h2 {{ margin: 7px 0 5px; font-size: 1.35rem; }}
    .product p {{ min-height: 40px; margin: 0 0 15px; color: var(--muted); line-height: 1.4; font-size: .94rem; }}
    .product-footer {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
    .product-footer strong {{ font-size: 1.2rem; }}
    .stock {{ color: var(--muted); font: .75rem system-ui, sans-serif; }}
    .add-button {{ width: 100%; margin-top: 14px; border: 1px solid var(--ink); background: white; color: var(--ink); padding: 10px; cursor: pointer; font: 700 .85rem system-ui, sans-serif; }}
    .add-button:hover:not(:disabled) {{ background: var(--ink); color: white; }}
    .add-button:disabled {{ cursor: not-allowed; color: #aab0b5; border-color: #d9dddf; }}
    .empty {{ color: var(--muted); font-family: system-ui, sans-serif; }}
    .cart {{ position: fixed; right: 20px; bottom: 20px; width: min(360px, calc(100vw - 40px)); max-height: 75vh; overflow: auto; padding: 22px; background: white; border: 1px solid var(--line); box-shadow: 0 12px 40px #17212b2b; display: none; z-index: 3; }}
    .cart.open {{ display: block; }}
    .cart h2 {{ margin: 0 0 16px; font-size: 1.4rem; }}
    .cart-row {{ display: grid; grid-template-columns: 1fr auto; gap: 10px; padding: 12px 0; border-top: 1px solid var(--line); }}
    .cart-name {{ font-weight: 700; }}
    .cart-controls {{ display: flex; align-items: center; gap: 8px; margin-top: 5px; font-family: system-ui, sans-serif; }}
    .cart-controls button {{ width: 26px; height: 26px; border: 1px solid var(--line); background: var(--soft); cursor: pointer; }}
    .cart-price {{ font-family: system-ui, sans-serif; font-size: .9rem; }}
    .cart-total {{ display: flex; justify-content: space-between; border-top: 2px solid var(--ink); margin-top: 8px; padding-top: 14px; font-weight: 700; font-family: system-ui, sans-serif; }}
    .checkout {{ margin-top: 18px; border-top: 1px solid var(--line); padding-top: 16px; }}
    .checkout h3 {{ margin: 0 0 12px; font-size: 1.1rem; }}
    .checkout input, .checkout textarea {{ width: 100%; margin-bottom: 9px; padding: 10px; border: 1px solid var(--line); font: .9rem system-ui, sans-serif; }}
    .checkout textarea {{ min-height: 65px; resize: vertical; }}
    .order-button {{ width: 100%; border: 0; background: var(--accent); color: white; padding: 11px; cursor: pointer; font: 700 .85rem system-ui, sans-serif; }}
    .order-button:disabled {{ opacity: .55; cursor: not-allowed; }}
    .order-message {{ margin: 10px 0 0; color: var(--muted); font: .82rem system-ui, sans-serif; }}
    @media (max-width: 700px) {{ .layout {{ grid-template-columns: 1fr; padding-top: 24px; }} aside {{ border-right: 0; border-bottom: 1px solid var(--line); padding: 0 0 15px; }} .category-list {{ display: flex; gap: 18px; overflow-x: auto; }} .category-button {{ min-width: max-content; width: auto; }} }}
  </style>
</head>
<body>
  <header><div><h1>Our Shop</h1><p>Browse the collection and choose your favourites.</p></div><button class="cart-toggle" id="cart-toggle">Cart (<span id="cart-count">0</span>)</button></header>
  <main class="layout">
    <aside><h3>Categories</h3><div class="category-list"><button class="category-button active" data-category="all">All products</button>{category_buttons}</div></aside>
    <section class="products" id="products">{cards}</section>
  </main>
  <section class="cart" id="cart">
    <h2>Your cart</h2>
    <div id="cart-items"></div>
    <div class="cart-total"><span>Total</span><span id="cart-total">$0.00</span></div>
    <form class="checkout" id="checkout-form">
      <h3>Place order</h3>
      <input name="name" placeholder="Your name" required>
      <input name="phone" type="tel" placeholder="Phone number" required>
      <textarea name="address" placeholder="Address (optional)"></textarea>
      <button class="order-button" type="submit" disabled>Place order</button>
      <p class="order-message" id="order-message"></p>
    </form>
  </section>
  <script>
    const products = {{}}, cart = {{}};
    document.querySelectorAll('.product').forEach(card => products[card.dataset.id] = {{ name: card.querySelector('h2').textContent, price: Number(card.querySelector('strong').textContent.replace('$', '')), stock: Number(card.querySelector('.stock').textContent.split(' ')[0]) || 0 }});
    const count = () => Object.values(cart).reduce((sum, item) => sum + item.quantity, 0);
    function renderCart() {{
      const items = document.getElementById('cart-items');
      items.innerHTML = Object.entries(cart).map(([id, item]) => `<div class="cart-row"><div><div class="cart-name">${{item.name}}</div><div class="cart-controls"><button data-minus="${{id}}">-</button><span>${{item.quantity}}</span><button data-plus="${{id}}">+</button></div></div><span class="cart-price">$${{(item.price * item.quantity).toFixed(2)}}</span></div>`).join('') || '<p class="empty">Your cart is empty.</p>';
      document.getElementById('cart-count').textContent = count();
        document.getElementById('cart-total').textContent = '$' + Object.values(cart).reduce((sum, item) => sum + item.price * item.quantity, 0).toFixed(2);
        document.querySelector('.order-button').disabled = count() === 0;
    }}
    document.addEventListener('click', event => {{
      const add = event.target.closest('[data-add]');
      if (add) {{ const id = add.dataset.add, product = products[id]; if (!cart[id]) cart[id] = {{ ...product, quantity: 0 }}; if (cart[id].quantity < product.stock) cart[id].quantity++; renderCart(); }}
      const plus = event.target.closest('[data-plus]');
      if (plus) {{ const item = cart[plus.dataset.plus], product = products[plus.dataset.plus]; if (item.quantity < product.stock) item.quantity++; renderCart(); }}
      const minus = event.target.closest('[data-minus]');
      if (minus) {{ const id = minus.dataset.minus; cart[id].quantity--; if (cart[id].quantity <= 0) delete cart[id]; renderCart(); }}
      const category = event.target.closest('[data-category]');
      if (category) {{ document.querySelectorAll('.category-button').forEach(button => button.classList.remove('active')); category.classList.add('active'); document.querySelectorAll('.product').forEach(card => card.hidden = category.dataset.category !== 'all' && card.dataset.category !== category.dataset.category); }}
    }});
    document.getElementById('cart-toggle').addEventListener('click', () => document.getElementById('cart').classList.toggle('open'));
    document.getElementById('checkout-form').addEventListener('submit', async event => {{
      event.preventDefault();
      if (count() === 0) return;
      const button = document.querySelector('.order-button');
      const message = document.getElementById('order-message');
      button.disabled = true;
      message.textContent = 'Sending order...';
      const form = new FormData(event.target);
      const response = await fetch('/order/{user_id}', {{
        method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ name: form.get('name'), phone: form.get('phone'), address: form.get('address'), items: Object.entries(cart).map(([id, item]) => ({{ id: Number(id), quantity: item.quantity }})) }})
      }});
      const result = await response.json();
      if (response.ok) {{
        message.textContent = 'Order sent. We will contact you soon.';
        event.target.reset();
        Object.keys(cart).forEach(id => delete cart[id]);
        renderCart();
      }} else {{
        message.textContent = result.error || 'Could not place the order.';
        button.disabled = false;
      }}
    }});
    renderCart();
  </script>
</body>
</html>"""


async def shop(request):
    try:
        user_id = int(request.match_info["user_id"])
    except ValueError:
        raise web.HTTPNotFound()
    categories, products = await get_shop_data(user_id)
    return web.Response(text=shop_page(user_id, categories, products), content_type="text/html")


async def image(request):
    try:
        product_id = int(request.match_info["product_id"])
    except ValueError:
        raise web.HTTPNotFound()
    async with connection() as db:
        cursor = await db.execute("SELECT image_id FROM products WHERE id = %s", (product_id,))
        row = await cursor.fetchone()
    if not row:
        raise web.HTTPNotFound()
    file = await bot.get_file(row["image_id"])
    output = io.BytesIO()
    await bot.download_file(file.file_path, output)
    return web.Response(body=output.getvalue(), content_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})


async def place_order(request):
    try:
        user_id = int(request.match_info["user_id"])
        data = await request.json()
        name = str(data.get("name", "")).strip()
        phone = str(data.get("phone", "")).strip()
        address = str(data.get("address", "")).strip()
        requested_items = data.get("items", [])
    except (ValueError, json.JSONDecodeError, TypeError):
        return web.json_response({"error": "Invalid order details."}, status=400)

    if not name or not phone or not isinstance(requested_items, list) or not requested_items:
        return web.json_response({"error": "Name, phone, and at least one product are required."}, status=400)

    quantities = {}
    try:
        for item in requested_items:
            product_id = int(item["id"])
            quantity = int(item["quantity"])
            if product_id <= 0 or quantity <= 0:
                raise ValueError
            quantities[product_id] = quantities.get(product_id, 0) + quantity
    except (KeyError, TypeError, ValueError):
        return web.json_response({"error": "Invalid products in cart."}, status=400)

    placeholders = ",".join("%s" for _ in quantities)
    async with connection() as db:
        cursor = await db.execute(
        f"SELECT id, name, price, stock FROM products WHERE user_id = %s AND id IN ({placeholders}) FOR UPDATE",
            (user_id, *quantities.keys()),
        )
        products = await cursor.fetchall()

    if len(products) != len(quantities):
        return web.json_response({"error": "One or more products are no longer available."}, status=409)

    lines = []
    total = 0
    for product in products:
        product_id = product["id"]
        product_name = product["name"]
        price = product["price"]
        stock = product["stock"]
        quantity = quantities[product_id]
        if quantity > stock:
            return web.json_response({"error": f"Only {stock} of {product_name} are available."}, status=409)
        line_total = price * quantity
        total += line_total
        lines.append(f"- {product_name} x {quantity} = ${line_total:.2f}")

    order_cursor = await db.execute(
        """INSERT INTO orders (shop_owner_id, customer_name, phone, address, total)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (user_id, name, phone, address or None, total),
    )
    order = await order_cursor.fetchone()
    for product in products:
        product_id = product["id"]
        quantity = quantities[product_id]
        await db.execute(
            """INSERT INTO order_items
               (order_id, product_id, product_name, unit_price, quantity)
               VALUES (%s, %s, %s, %s, %s)""",
            (order["id"], product_id, product["name"], product["price"], quantity),
        )
        await db.execute(
            "UPDATE products SET stock = stock - %s WHERE id = %s",
            (quantity, product_id),
        )
    await db.commit()

    order_message = (
        "<b>New shop order</b>\n\n"
        f"<b>Name:</b> {html.escape(name)}\n"
        f"<b>Phone:</b> {html.escape(phone)}\n"
        f"<b>Address:</b> {html.escape(address or 'Not provided')}\n\n"
        "<b>Products:</b>\n" + "\n".join(html.escape(line) for line in lines) +
        f"\n\n<b>Total bill:</b> ${total:.2f}"
    )
    try:
        await bot.send_message(user_id, order_message, parse_mode="HTML")
    except Exception:
        async with connection() as db:
            await db.execute("UPDATE orders SET status = 'notification_failed' WHERE id = %s", (order["id"],))
            await db.commit()
        return web.json_response({"error": "The shop owner could not receive this order."}, status=502)

    return web.json_response({"message": "Order sent successfully."})


async def database_context(app):
    await init_db()
    try:
        yield
    finally:
        await close_db()
        await bot.session.close()


async def health(request):
    async with connection() as db:
        await db.execute("SELECT 1")
    return web.json_response({"status": "ok"})


app = web.Application()
app.cleanup_ctx.append(database_context)
app.router.add_get("/health", health)
app.router.add_get("/image/{product_id}", image)
app.router.add_post("/order/{user_id}", place_order)
app.router.add_get("/{user_id}", shop)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
