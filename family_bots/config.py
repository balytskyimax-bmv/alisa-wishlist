import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Telegram Bot Token for Family Budget (@Bbudgett_bot)
BOT_TOKEN = (
    os.getenv("BUDGET_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or "8816257474:AAE4gpvMMcRHnYHboYTI6SCivdnajQae-ZA"
).strip()

# Admin Telegram User ID (Husband)
ADMIN_ID = int(os.getenv("ADMIN_ID", "467567653"))

# Target Group Chat ID (e.g., -100xxxxxxxxxx)
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1003872009004")) if os.getenv("GROUP_CHAT_ID", "-1003872009004") else None

# Target Topic ID (message_thread_id in Telegram forum group)
TOPIC_ID = int(os.getenv("TOPIC_ID", "173")) if os.getenv("TOPIC_ID", "173") else None

# Database Configuration (Neon PostgreSQL Cloud Production)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_1qlkJs2MGWcU@ep-green-brook-ba6ndeof-pooler.c-8.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
).strip()
DB_PATH = os.getenv("DB_PATH", "family_budget.db")
