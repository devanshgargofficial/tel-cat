# Telegram Catalogue Shop

## Local setup

1. Create a PostgreSQL database named `telcat`.
2. Copy `.env.example` to `.env` and set `BOT_TOKEN` and `DATABASE_URL`.
3. Install dependencies:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. If you have products in the old SQLite database, migrate them once:

```powershell
.venv\Scripts\python.exe migrate_sqlite_to_postgres.py
```

5. Start the shop and bot in separate processes:

```powershell
.venv\Scripts\python.exe shop_server.py
.venv\Scripts\python.exe index.py
```

The shop health check is available at `/health`. The shop URL for an owner is `/<telegram_user_id>`.

## Railway deployment

Create a PostgreSQL service and two application services from this repository:

- Shop service start command: `python shop_server.py`
- Bot service start command: `python index.py`

Set these variables on both application services:

```text
BOT_TOKEN=your-new-token
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

Set `SHOP_URL` on the bot service to the public HTTPS URL generated for the shop service. Use the Railway PostgreSQL connection string directly; do not deploy `catalogue.db` as the production database.

The old Telegram token must be revoked in BotFather. Never commit `.env`.
