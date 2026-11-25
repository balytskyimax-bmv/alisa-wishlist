import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# DTEK Bot Token (@svitlogorabot) - isolated from family_budget_bot's BOT_TOKEN
BOT_TOKEN = os.getenv("DTEK_BOT_TOKEN", "9010327112:AAHh0Qn6whHTyvUsbKa4Ww6QN48n76n9LAU").strip()

# Target Group Chat ID (e.g. -100xxxxxxxxxx)
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1003872009004")) if os.getenv("GROUP_CHAT_ID", "-1003872009004") else None

# Admin Private Chat ID (fallback if bot is not in group yet)
ADMIN_ID = int(os.getenv("ADMIN_ID", "467567653")) if os.getenv("ADMIN_ID", "467567653") else None

# Topic ID (Forum thread for DTEK light notifications - isolated from budget TOPIC_ID)
TOPIC_ID = int(os.getenv("DTEK_TOPIC_ID", "0")) if os.getenv("DTEK_TOPIC_ID") else None

# Target Region and Group
TARGET_REGION = os.getenv("TARGET_REGION", "kyiv-region").strip()
TARGET_GROUP = os.getenv("TARGET_GROUP", "GPV5.1").strip()
LOCATION_NAME = os.getenv("LOCATION_NAME", "с. Гора, вул. Басейна, 20").strip()

# Polling Interval (every 30 mins)
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "1800"))

# Visual Options
SEND_IMAGE_WITH_ALERT = os.getenv("SEND_IMAGE_WITH_ALERT", "true").lower() in ("true", "1", "yes")

# Database Path
DB_PATH = str(BASE_DIR / os.getenv("DTEK_DB_PATH", "dtek_bot.db"))

# Data URLs
DATA_URL = f"https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/{TARGET_REGION}.json"
group_num = TARGET_GROUP.replace("GPV", "").replace(".", "-").lower()
IMAGE_URL = f"https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/images/{TARGET_REGION}/gpv-{group_num}.png"
