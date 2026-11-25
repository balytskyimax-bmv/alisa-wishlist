import os
import ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import aiosqlite
from typing import List, Dict, Any, Optional
import config

try:
    import asyncpg
except ImportError:
    asyncpg = None

DEFAULT_CATEGORIES = [
    ("🏠 Житло та паркінг", 1),
    ("💡 Комунальні платежі", 2),
    ("👶 Дитина", 3),
    ("🐕 Собака", 4),
    ("🛒 Побут та авто", 5),
    ("📱 Підписки та зв’язок", 6),
    ("⚡️ Інші незаплановані витрати", 7),
]

DEFAULT_EXPENSES = [
    (1, "Оренда будинку", 40000.0, ""),
    (1, "Оренда паркомісця", 6000.0, ""),
    (2, "Комуналка будинку (світло, газ, вода)", 5000.0, ""),
    (2, "Комуналка квартири", 2000.0, ""),
    (3, "Суміш та харчування", 5000.0, ""),
    (3, "Підгузки та догляд", 2500.0, ""),
    (3, "Вакцинація / лікар", 9000.0, ""),
    (4, "Корм та ветеринар", 3000.0, ""),
    (5, "Продукти харчування", 25000.0, ""),
    (5, "Бензин", 6000.0, ""),
    (5, "Побутова хімія", 2000.0, ""),
    (6, "Apple Music / iCloud", 350.0, "авто"),
    (6, "Домашній інтернет", 400.0, ""),
    (6, "Мобільний зв'язок (2 номери)", 500.0, ""),
    (6, "Netflix", 400.0, "авто"),
    (6, "Google One", 150.0, "авто"),
    (7, "Різне / форс-мажори", 0.0, ""),
]

_pg_pool: Optional[Any] = None


def is_postgres() -> bool:
    return bool(config.DATABASE_URL and asyncpg)


async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        dsn = config.DATABASE_URL.strip()
        if dsn.startswith("postgres://"):
            dsn = "postgresql://" + dsn[11:]

        parsed = urlparse(dsn)
        qs = parse_qs(parsed.query)
        ssl_arg = None
        if "sslmode" in qs:
            mode = qs.pop("sslmode")[0]
            if mode in ("require", "verify-ca", "verify-full"):
                ctx = ssl.create_default_context()
                if mode == "require":
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                ssl_arg = ctx
        # asyncpg does not support libpq's channel_binding parameter
        qs.pop("channel_binding", None)
        clean_query = urlencode({k: v[0] for k, v in qs.items()})
        clean_dsn = urlunparse(parsed._replace(query=clean_query))

        kwargs = {
            "dsn": clean_dsn,
            "min_size": 0,
            "max_size": 5,
            "max_inactive_connection_lifetime": 45.0,
            "statement_cache_size": 0,
        }
        if ssl_arg is not None:
            kwargs["ssl"] = ssl_arg
        _pg_pool = await asyncpg.create_pool(**kwargs)
    return _pg_pool


async def _reset_pg_pool():
    global _pg_pool
    pool = _pg_pool
    _pg_pool = None
    if pool is not None:
        try:
            pool.terminate()
        except Exception:
            pass


def _is_recoverable_pg_error(exc: Exception) -> bool:
    if isinstance(exc, (OSError, ConnectionResetError)):
        return True
    if asyncpg is not None:
        if isinstance(exc, asyncpg.ConnectionDoesNotExistError):
            return True
        if isinstance(exc, asyncpg.InterfaceError) and "closed" in str(exc).lower():
            return True
    return False


async def _run_pg(op):
    for attempt in range(2):
        try:
            pool = await get_pg_pool()
            async with pool.acquire() as conn:
                return await op(conn)
        except Exception as exc:
            if attempt == 0 and _is_recoverable_pg_error(exc):
                await _reset_pg_pool()
                continue
            raise


def _to_pg_query(query: str) -> str:
    parts = query.split("?")
    if len(parts) <= 1:
        return query
    res = []
    for i, part in enumerate(parts[:-1]):
        res.append(part)
        res.append(f"${i+1}")
    res.append(parts[-1])
    return "".join(res)


# --- UNIFIED DB QUERY RUNNERS ---
async def db_fetch_all(query: str, *params) -> List[Dict[str, Any]]:
    if is_postgres():
        pg_sql = _to_pg_query(query)
        records = await _run_pg(lambda conn: conn.fetch(pg_sql, *params))
        return [dict(r) for r in records]
    else:
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, params)
            return [dict(r) for r in await cur.fetchall()]


async def db_fetch_one(query: str, *params) -> Optional[Dict[str, Any]]:
    if is_postgres():
        pg_sql = _to_pg_query(query)
        rec = await _run_pg(lambda conn: conn.fetchrow(pg_sql, *params))
        return dict(rec) if rec else None
    else:
        async with aiosqlite.connect(config.DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, params)
            row = await cur.fetchone()
            return dict(row) if row else None


async def db_execute(query: str, *params) -> Optional[int]:
    """Executes an INSERT/UPDATE/DELETE. For INSERTs, returns the new row id when possible."""
    if is_postgres():
        is_insert = query.strip().upper().startswith("INSERT")
        pg_sql = _to_pg_query(query)
        if is_insert and "RETURNING" not in pg_sql.upper():
            pg_sql = f"{pg_sql} RETURNING id"

        async def _exec(conn):
            if is_insert and "RETURNING" in pg_sql.upper():
                return await conn.fetchval(pg_sql, *params)
            await conn.execute(pg_sql, *params)
            return None

        return await _run_pg(_exec)
    else:
        async with aiosqlite.connect(config.DB_PATH) as db:
            cur = await db.execute(query, params)
            await db.commit()
            return cur.lastrowid


async def init_db():
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    sort_order INT DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS expenses (
                    id SERIAL PRIMARY KEY,
                    category_id INT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    paid_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                    is_paid INT NOT NULL DEFAULT 0,
                    note TEXT DEFAULT '',
                    sort_order INT DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS payment_history (
                    id SERIAL PRIMARY KEY,
                    expense_id INT NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
                    amount DOUBLE PRECISION NOT NULL,
                    user_name TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_payment_history_exp ON payment_history(expense_id);
                CREATE TABLE IF NOT EXISTS edit_history (
                    id SERIAL PRIMARY KEY,
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    user_name TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Seed if empty
            count = await conn.fetchval("SELECT COUNT(*) FROM categories")
            if count == 0:
                for name, order in DEFAULT_CATEGORIES:
                    await conn.execute("INSERT INTO categories (name, sort_order) VALUES ($1, $2)", name, order)

                cat_rows = await conn.fetch("SELECT id, sort_order FROM categories ORDER BY sort_order")
                cat_map = {row["sort_order"]: row["id"] for row in cat_rows}

                for cat_order, name, amount, note in DEFAULT_EXPENSES:
                    cat_id = cat_map.get(cat_order)
                    if cat_id:
                        await conn.execute(
                            "INSERT INTO expenses (category_id, name, amount, note) VALUES ($1, $2, $3, $4)",
                            cat_id, name, amount, note
                        )

                try:
                    async with aiosqlite.connect(f"file:{config.DB_PATH}?mode=ro", uri=True) as local_db:
                        async with local_db.execute(
                            "SELECT key, value FROM settings WHERE key IN ('group_chat_id', 'topic_id', 'current_month')"
                        ) as cur:
                            for k, v in await cur.fetchall():
                                await conn.execute(
                                    "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING",
                                    k, v
                                )
                except Exception:
                    pass
    else:
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    amount REAL NOT NULL DEFAULT 0.0,
                    paid_amount REAL NOT NULL DEFAULT 0.0,
                    is_paid INTEGER NOT NULL DEFAULT 0,
                    note TEXT DEFAULT '',
                    sort_order INTEGER DEFAULT 0,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    user_name TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_payment_history_exp ON payment_history(expense_id)")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS edit_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    user_name TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM categories")
            count = (await cursor.fetchone())[0]
            if count == 0:
                for name, order in DEFAULT_CATEGORIES:
                    await db.execute("INSERT INTO categories (name, sort_order) VALUES (?, ?)", (name, order))
                await db.commit()

                cursor = await db.execute("SELECT id, sort_order FROM categories ORDER BY sort_order")
                cat_rows = await cursor.fetchall()
                cat_map = {row[1]: row[0] for row in cat_rows}

                for cat_order, name, amount, note in DEFAULT_EXPENSES:
                    cat_id = cat_map.get(cat_order)
                    if cat_id:
                        await db.execute(
                            "INSERT INTO expenses (category_id, name, amount, note) VALUES (?, ?, ?, ?)",
                            (cat_id, name, amount, note)
                        )
                await db.commit()


async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = await db_fetch_one("SELECT value FROM settings WHERE key = ?", key)
    return row["value"] if row else default


async def set_setting(key: str, value: str):
    if is_postgres():
        await _run_pg(lambda conn: conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, key, str(value)))
    else:
        await db_execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            key, str(value)
        )


async def get_all_data() -> List[Dict[str, Any]]:
    categories = await db_fetch_all("SELECT * FROM categories ORDER BY sort_order ASC, id ASC")
    for cat in categories:
        cat["expenses"] = await db_fetch_all(
            "SELECT * FROM expenses WHERE category_id = ? ORDER BY sort_order ASC, id ASC",
            cat["id"]
        )
    return categories


async def get_category(category_id: int) -> Optional[Dict[str, Any]]:
    return await db_fetch_one("SELECT * FROM categories WHERE id = ?", category_id)


async def get_expenses_by_category(category_id: int) -> List[Dict[str, Any]]:
    return await db_fetch_all(
        "SELECT * FROM expenses WHERE category_id = ? ORDER BY sort_order ASC, id ASC",
        category_id
    )


async def get_expense(expense_id: int) -> Optional[Dict[str, Any]]:
    return await db_fetch_one("SELECT * FROM expenses WHERE id = ?", expense_id)


async def get_all_expenses_flat() -> List[Dict[str, Any]]:
    return await db_fetch_all("""
        SELECT e.*, c.name as category_name 
        FROM expenses e 
        JOIN categories c ON e.category_id = c.id 
        ORDER BY c.sort_order ASC, e.id ASC
    """)


async def log_edit_action(action: str, details: str = "", user_name: str = ""):
    """Logs administrative/structural modifications for complete audit trail."""
    try:
        await db_execute(
            "INSERT INTO edit_history (action, details, user_name) VALUES (?, ?, ?)",
            action, details, user_name
        )
    except Exception:
        pass


async def get_recent_edits(limit: int = 20) -> List[Dict[str, Any]]:
    return await db_fetch_all(
        "SELECT action, details, user_name, created_at FROM edit_history ORDER BY id DESC LIMIT ?",
        limit
    )


async def update_expense_amount(expense_id: int, new_amount: float) -> bool:
    await db_execute(
        "UPDATE expenses SET amount = ? WHERE id = ?",
        round(new_amount, 2), expense_id
    )
    await log_edit_action("update_budget", f"ID {expense_id} -> {new_amount} грн")
    return True


async def update_expense_name(expense_id: int, new_name: str) -> bool:
    await db_execute(
        "UPDATE expenses SET name = ? WHERE id = ?",
        new_name.strip(), expense_id
    )
    await log_edit_action("rename_subcat", f"ID {expense_id} -> {new_name}")
    return True


async def toggle_expense_paid(expense_id: int) -> Dict[str, Any]:
    row = await get_expense(expense_id)
    if not row:
        return {}

    current_is_paid = row["is_paid"]
    new_is_paid = 0 if current_is_paid == 1 else 1
    new_paid_amount = row["amount"] if new_is_paid == 1 else 0.0

    await db_execute(
        "UPDATE expenses SET is_paid = ?, paid_amount = ? WHERE id = ?",
        new_is_paid, new_paid_amount, expense_id
    )
    return await get_expense(expense_id) or {}


async def add_expense_payment(expense_id: int, added_amount: float, user_name: str = "") -> Optional[Dict[str, Any]]:
    row = await get_expense(expense_id)
    if not row:
        return None

    current_paid = row["paid_amount"]
    target_amount = row["amount"]
    new_paid = round(current_paid + added_amount, 2)

    if target_amount > 0:
        is_paid = 1 if new_paid >= target_amount else 0
    else:
        is_paid = 1 if new_paid > 0 else 0

    await db_execute(
        "UPDATE expenses SET paid_amount = ?, is_paid = ? WHERE id = ?",
        new_paid, is_paid, expense_id
    )
    await db_execute(
        "INSERT INTO payment_history (expense_id, amount, user_name) VALUES (?, ?, ?)",
        expense_id, round(added_amount, 2), user_name
    )
    await log_edit_action("add_payment", f"{row['name']}: +{added_amount} грн (разом {new_paid})", user_name)
    return await get_expense(expense_id)


async def set_expense_payment(expense_id: int, paid_amount: float, is_paid: Optional[int] = None, user_name: str = "") -> bool:
    row = await get_expense(expense_id)
    if not row:
        return False

    target_amount = row["amount"]
    if is_paid is None:
        if target_amount > 0:
            is_paid = 1 if paid_amount >= target_amount else 0
        else:
            is_paid = 1 if paid_amount > 0 else 0

    await db_execute(
        "UPDATE expenses SET paid_amount = ?, is_paid = ? WHERE id = ?",
        round(paid_amount, 2), is_paid, expense_id
    )
    if paid_amount == 0.0:
        await db_execute("DELETE FROM payment_history WHERE expense_id = ?", expense_id)
        await log_edit_action("reset_payment", f"{row['name']}: скинуто на 0", user_name)
    elif paid_amount > 0:
        await db_execute(
            "INSERT INTO payment_history (expense_id, amount, user_name) VALUES (?, ?, ?)",
            expense_id, round(paid_amount, 2), user_name
        )
        await log_edit_action("set_payment", f"{row['name']}: встановлено {paid_amount} грн", user_name)
    return True


async def get_expense_history(expense_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    return await db_fetch_all(
        "SELECT amount, user_name, created_at FROM payment_history WHERE expense_id = ? ORDER BY id DESC LIMIT ?",
        expense_id, limit
    )


async def mark_category_all_paid(category_id: int) -> bool:
    cat = await get_category(category_id)
    cat_name = cat["name"] if cat else str(category_id)
    await db_execute(
        "UPDATE expenses SET is_paid = 1, paid_amount = amount WHERE category_id = ?",
        category_id
    )
    await log_edit_action("pay_category_all", f"Категорія: {cat_name} (ID: {category_id})")
    return True


EXPENSE_ALIASES = {
    "їжа": "продукти",
    "сільпо": "продукти",
    "атб": "продукти",
    "фора": "продукти",
    "супермаркет": "продукти",
    "пальне": "бензин",
    "азс": "бензин",
    "окко": "бензин",
    "wog": "бензин",
    "заправка": "бензин",
    "памперси": "підгузки",
    "пелюшки": "підгузки",
    "ветеринар": "корм",
    "собака": "корм",
    "пес": "корм",
    "світло": "комуналка будинку",
    "газ": "комуналка будинку",
    "вода": "комуналка будинку",
    "інтернет": "домашній інтернет",
    "форс-мажор": "різне",
    "форсмажор": "різне",
    "незаплановане": "різне",
    "інше": "різне",
    "аптека": "лікар",
}


async def find_expense_by_name(query: str) -> Optional[Dict[str, Any]]:
    clean_q = query.strip().lower()
    for alias, mapped in EXPENSE_ALIASES.items():
        if alias in clean_q:
            clean_q = clean_q.replace(alias, mapped).strip()
            break

    expenses = await get_all_expenses_flat()

    for exp in expenses:
        if exp["name"].lower() == clean_q:
            return exp

    for exp in expenses:
        exp_name_low = exp["name"].lower()
        if exp_name_low.startswith(clean_q) or clean_q in exp_name_low.split():
            return exp

    for exp in expenses:
        if clean_q in exp["name"].lower():
            return exp

    return None


async def get_frequent_expenses(limit: int = 4) -> List[Dict[str, Any]]:
    rows = await db_fetch_all("""
        SELECT e.*, COUNT(h.id) as pay_count 
        FROM expenses e 
        JOIN payment_history h ON e.id = h.expense_id 
        GROUP BY e.id 
        ORDER BY pay_count DESC, e.id ASC 
        LIMIT ?
    """, limit)
    if len(rows) >= limit:
        return rows

    all_exp = await get_all_expenses_flat()
    added_ids = {r["id"] for r in rows}
    preferred = list(rows)
    for kw in ["продукт", "бензин", "дитина", "різне", "харчування", "хімія"]:
        for e in all_exp:
            if e["id"] not in added_ids and kw in e["name"].lower():
                preferred.append(e)
                added_ids.add(e["id"])
                if len(preferred) >= limit:
                    return preferred
    for e in all_exp:
        if e["id"] not in added_ids:
            preferred.append(e)
            added_ids.add(e["id"])
            if len(preferred) >= limit:
                break
    return preferred


async def add_category(name: str) -> int:
    row = await db_fetch_one("SELECT MAX(sort_order) as max_order FROM categories")
    max_order = row["max_order"] if (row and row["max_order"] is not None) else 0
    new_order = max_order + 1

    cat_id = await db_execute(
        "INSERT INTO categories (name, sort_order) VALUES (?, ?)",
        name.strip(), new_order
    )
    # Add default subcategory so category shows on dashboard immediately
    await db_execute(
        "INSERT INTO expenses (category_id, name, amount, paid_amount, is_paid, note) VALUES (?, ?, ?, ?, ?, ?)",
        cat_id, "Основне", 0.0, 0.0, 0, ""
    )
    await log_edit_action("add_category", f"Категорія: {name} (ID: {cat_id})")
    return cat_id


async def delete_category(category_id: int) -> bool:
    cat = await get_category(category_id)
    cat_name = cat["name"] if cat else str(category_id)
    await db_execute("DELETE FROM expenses WHERE category_id = ?", category_id)
    await db_execute("DELETE FROM categories WHERE id = ?", category_id)
    await log_edit_action("delete_category", f"Категорія: {cat_name} (ID: {category_id})")
    return True


async def rename_category(category_id: int, new_name: str) -> bool:
    await db_execute("UPDATE categories SET name = ? WHERE id = ?", new_name.strip(), category_id)
    await log_edit_action("rename_category", f"ID: {category_id} -> {new_name}")
    return True


async def add_expense(category_id: int, name: str, amount: float, note: str = "") -> int:
    exp_id = await db_execute(
        "INSERT INTO expenses (category_id, name, amount, note) VALUES (?, ?, ?, ?)",
        category_id, name.strip(), round(amount, 2), note.strip()
    )
    await log_edit_action("add_subcat", f"Підкатегорія: {name}, Сума: {amount} грн (ID: {exp_id})")
    return exp_id


async def delete_expense(expense_id: int) -> bool:
    exp = await get_expense(expense_id)
    exp_name = exp["name"] if exp else str(expense_id)
    await db_execute("DELETE FROM expenses WHERE id = ?", expense_id)
    await log_edit_action("delete_subcat", f"Підкатегорія: {exp_name} (ID: {expense_id})")
    return True


async def rollover_new_month(month_name: str):
    await db_execute("UPDATE expenses SET is_paid = 0, paid_amount = 0.0")
    await db_execute("DELETE FROM payment_history")
    await set_setting("current_month", month_name)
