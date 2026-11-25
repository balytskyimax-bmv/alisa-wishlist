from __future__ import annotations
import aiosqlite
import logging
from config import DB_PATH, TOPIC_ID

logger = logging.getLogger(__name__)

async def init_db() -> None:
    """Initialize database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedule_history (
                date_str TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()

        # If TOPIC_ID is pre-set in config, store it in db if not exists
        if TOPIC_ID:
            row = await get_setting("topic_id")
            if not row:
                await set_setting("topic_id", str(TOPIC_ID))
    logger.info("Database initialized successfully.")

async def get_setting(key: str, default: str | None = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()

async def get_topic_id() -> int | None:
    val = await get_setting("topic_id")
    if val:
        try:
            return int(val)
        except ValueError:
            return None
    return TOPIC_ID

async def set_topic_id(topic_id: int) -> None:
    await set_setting("topic_id", str(topic_id))

async def get_stored_schedule(date_str: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT date_str, hash, raw_json, sent_at, updated_at FROM schedule_history WHERE date_str = ?",
            (date_str,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def save_sent_schedule(date_str: str, hash_val: str, raw_json: str, sent_at: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO schedule_history (date_str, hash, raw_json, sent_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date_str) DO UPDATE SET
                hash = excluded.hash,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
        """, (date_str, hash_val, raw_json, sent_at, sent_at))
        await db.commit()
