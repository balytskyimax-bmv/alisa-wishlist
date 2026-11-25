from __future__ import annotations
import asyncio
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from config import (
    BOT_TOKEN,
    GROUP_CHAT_ID,
    ADMIN_ID,
    TOPIC_ID,
    CHECK_INTERVAL_SECONDS,
    SEND_IMAGE_WITH_ALERT,
    LOCATION_NAME,
    TARGET_GROUP,
)
from database import (
    init_db,
    get_topic_id,
    set_topic_id,
    get_stored_schedule,
    save_sent_schedule,
    get_setting,
    set_setting,
)
from dtek_service import DtekService
from formatter import format_schedule_message
from image_generator import generate_schedule_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dtek_bot")
KYIV_TZ = ZoneInfo("Europe/Kyiv")

dtek_service = DtekService()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Quick access buttons for chat."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💡 Світло сьогодні", callback_data="btn_today"),
                InlineKeyboardButton(text="⚡️ Графік на завтра", callback_data="btn_tomorrow")
            ],
            [
                InlineKeyboardButton(text="🖼 Графічне зображення", callback_data="btn_image"),
                InlineKeyboardButton(text="🔄 Оновити дані", callback_data="btn_check")
            ]
        ]
    )

async def auto_create_topic_if_needed() -> int | None:
    """Attempt to create '💡 Світло / Гора' forum topic in GROUP_CHAT_ID if not already set."""
    if not GROUP_CHAT_ID:
        return None

    current_topic = await get_topic_id()
    if current_topic:
        return current_topic

    try:
        topic = await bot.create_forum_topic(
            chat_id=GROUP_CHAT_ID,
            name="💡 Світло / Гора"
        )
        await set_topic_id(topic.message_thread_id)
        logger.info(f"Successfully auto-created topic '💡 Світло / Гора' with ID: {topic.message_thread_id}")

        welcome_text = (
            "👋 <b>Вітаю в темі моніторингу світла!</b>\n\n"
            f"📍 <b>Адреса:</b> {LOCATION_NAME}\n"
            f"⚡️ <b>Група відключень:</b> {TARGET_GROUP.replace('GPV', 'Черга ')}\n\n"
            "Тут щодня автоматично з'являтимуться свіжі графіки від ДТЕК, а також повідомлення про їх зміни.\n"
            "Для швидкої перевірки використовуйте меню або кнопки нижче."
        )
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            message_thread_id=topic.message_thread_id,
            text=welcome_text,
            reply_markup=get_main_keyboard()
        )
        return topic.message_thread_id
    except Exception as e:
        logger.warning(
            f"Could not auto-create topic (ensure bot is admin in group with 'Manage Topics' permission): {e}"
        )
        return None

async def broadcast_schedule(
    schedule: dict,
    updated_str: str,
    alert_type: str,
    tomorrow_schedule: dict | None = None
) -> bool:
    """Send an alert to the designated Telegram group/topic, or fallback to ADMIN_ID."""
    topic_id = await get_topic_id()
    text = format_schedule_message(
        schedule,
        updated_str=updated_str,
        alert_type=alert_type,
        tomorrow_schedule=tomorrow_schedule
    )

    delivered = False

    # 1. Try sending to GROUP_CHAT_ID first
    if GROUP_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=topic_id,
                text=text,
                reply_markup=get_main_keyboard()
            )
            if SEND_IMAGE_WITH_ALERT:
                try:
                    img_path = generate_schedule_image(schedule, updated_str)
                    date_label = schedule.get("date_formatted", "")
                    await bot.send_photo(
                        chat_id=GROUP_CHAT_ID,
                        message_thread_id=topic_id,
                        photo=FSInputFile(img_path),
                        caption=f"🖼 <i>Графік відключень на {date_label}</i>"
                    )
                except Exception as img_err:
                    logger.warning(f"Failed to send schedule photo to group: {img_err}")
            delivered = True
            logger.info(f"Broadcasted schedule alert ({alert_type}) to group for {schedule.get('date_str')}")
        except Exception as e:
            logger.warning(f"Could not broadcast to GROUP_CHAT_ID ({GROUP_CHAT_ID}): {e}")

    # 2. Fallback to ADMIN_ID private chat if group delivery did not happen
    if not delivered and ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=text,
                reply_markup=get_main_keyboard()
            )
            if SEND_IMAGE_WITH_ALERT:
                try:
                    img_path = generate_schedule_image(schedule, updated_str)
                    date_label = schedule.get("date_formatted", "")
                    await bot.send_photo(
                        chat_id=ADMIN_ID,
                        photo=FSInputFile(img_path),
                        caption=f"🖼 <i>Графік відключень на {date_label}</i>"
                    )
                except Exception as img_err:
                    logger.warning(f"Failed to send schedule photo to admin: {img_err}")
            delivered = True
            logger.info(f"Broadcasted schedule alert ({alert_type}) to ADMIN_ID for {schedule.get('date_str')}")
        except Exception as e:
            logger.error(f"Error broadcasting schedule to ADMIN_ID: {e}")

    return delivered

async def monitoring_loop() -> None:
    """Background task to poll DTEK and broadcast updates."""
    logger.info("Starting background DTEK monitoring loop...")
    while True:
        try:
            # Check if topic needs to be created
            await auto_create_topic_if_needed()

            updated_str, schedules = await dtek_service.get_all_schedules(force=True)
            if schedules:
                await set_setting("last_checked_at", datetime.now(KYIV_TZ).strftime("%d.%m.%Y %H:%M:%S"))
                if updated_str:
                    await set_setting("last_dtek_updated", updated_str)

                today_s = next((s for s in schedules if s.get("is_today")), None)
                tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

                for s in schedules:
                    date_str = s["date_str"]
                    curr_hash = s["hash"]
                    stored = await get_stored_schedule(date_str)

                    if not stored:
                        # New day discovered!
                        alert_type = "new_tomorrow" if s.get("is_tomorrow") else "normal"
                        logger.info(f"New schedule detected for {date_str} (alert: {alert_type})")
                        ok = await broadcast_schedule(
                            s,
                            updated_str=updated_str,
                            alert_type=alert_type,
                            tomorrow_schedule=tomorrow_s if s.get("is_today") else None
                        )
                        if ok:
                            sent_at = datetime.now(KYIV_TZ).isoformat()
                            await save_sent_schedule(date_str, curr_hash, str(s["raw_hours"]), sent_at)
                    elif stored["hash"] != curr_hash:
                        # Schedule was modified by DTEK!
                        logger.info(f"Schedule for {date_str} has been modified by DTEK!")
                        ok = await broadcast_schedule(
                            s,
                            updated_str=updated_str,
                            alert_type="updated",
                            tomorrow_schedule=tomorrow_s if s.get("is_today") else None
                        )
                        if ok:
                            sent_at = datetime.now(KYIV_TZ).isoformat()
                            await save_sent_schedule(date_str, curr_hash, str(s["raw_hours"]), sent_at)
                    else:
                        # Unchanged
                        pass
        except Exception as e:
            logger.error(f"Exception in monitoring_loop: {e}", exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

# ----------------- Command Handlers -----------------

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "👋 <b>Бот графіків відключення світла ДТЕК</b>\n\n"
        f"📍 <b>Адреса:</b> {LOCATION_NAME}\n"
        f"⚡️ <b>Черга:</b> {TARGET_GROUP.replace('GPV', 'Черга ')}\n\n"
        "<b>Доступні команди:</b>\n"
        "• /today або /світло — розклад на сьогодні та поточний статус\n"
        "• /tomorrow або /завтра — розклад на завтра (якщо опубліковано)\n"
        "• /image або /графік — офіційна інфографіка ДТЕК\n"
        "• /check — перевірити сайт ДТЕК прямо зараз\n"
        "• /status — статус моніторингу\n"
        "• /set_topic — встановити поточну тему для сповіщень\n"
        "• /help — довідка"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await cmd_start(message)

@dp.message(Command("today", "light", "світло"))
async def cmd_today(message: Message) -> None:
    updated_str, schedules = await dtek_service.get_all_schedules(force=False)
    today_s = next((s for s in schedules if s.get("is_today")), None)
    tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

    if not today_s:
        await message.answer(
            "⚠️ На сьогодні розклад відключень ще не сформовано або немає обмежень від Укренерго.",
            reply_markup=get_main_keyboard()
        )
        return

    text = format_schedule_message(
        today_s,
        updated_str=updated_str,
        alert_type="normal",
        tomorrow_schedule=tomorrow_s
    )
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(Command("tomorrow", "завтра"))
async def cmd_tomorrow(message: Message) -> None:
    updated_str, schedules = await dtek_service.get_all_schedules(force=False)
    tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

    if not tomorrow_s:
        await message.answer(
            "⏳ <b>Графік на завтра ще не опубліковано.</b>\n"
            "Зазвичай ДТЕК публікує його ввечері після розпорядження Укренерго (орієнтовно 18:00 - 22:00).\n"
            "Як тільки графік з'явиться, бот автоматично надішле його сюди!",
            reply_markup=get_main_keyboard()
        )
        return

    text = format_schedule_message(
        tomorrow_s,
        updated_str=updated_str,
        alert_type="normal"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

async def send_schedule_graphic(target: Message | CallbackQuery, for_tomorrow: bool = False) -> None:
    """Generate and send fresh schedule chart for today or tomorrow."""
    updated_str, schedules = await dtek_service.get_all_schedules(force=False)
    today_s = next((s for s in schedules if s.get("is_today")), None)
    tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

    target_s = tomorrow_s if for_tomorrow else (today_s or tomorrow_s)
    if not target_s:
        msg = "⚠️ Графік ще не опубліковано ДТЕК."
        if isinstance(target, CallbackQuery):
            await target.message.answer(msg)
        else:
            await target.answer(msg)
        return

    try:
        img_path = generate_schedule_image(target_s, updated_str)
        photo = FSInputFile(img_path)

        buttons = []
        if today_s and tomorrow_s:
            if for_tomorrow:
                buttons.append([InlineKeyboardButton(text="◀️ Переглянути графік на сьогодні", callback_data="btn_img_today")])
            else:
                buttons.append([InlineKeyboardButton(text="▶️ Переглянути графік на завтра", callback_data="btn_img_tomorrow")])
        buttons.append([
            InlineKeyboardButton(text="💡 Текст на сьогодні", callback_data="btn_today"),
            InlineKeyboardButton(text="⚡️ Текст на завтра", callback_data="btn_tomorrow")
        ])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        caption = (
            f"🖼 <b>Актуальний графік на {target_s['date_formatted']}</b>\n"
            f"📍 <i>{LOCATION_NAME} ({TARGET_GROUP.replace('GPV', 'Черга ')})</i>"
        )

        if isinstance(target, CallbackQuery):
            await target.message.answer_photo(photo=photo, caption=caption, reply_markup=kb)
        else:
            await target.answer_photo(photo=photo, caption=caption, reply_markup=kb)
    except Exception as e:
        logger.error(f"Error generating/sending schedule graphic: {e}")
        err_msg = f"Помилка створення зображення: {e}"
        if isinstance(target, CallbackQuery):
            await target.message.answer(err_msg)
        else:
            await target.answer(err_msg)

@dp.message(Command("image", "графік", "фото"))
async def cmd_image(message: Message) -> None:
    await send_schedule_graphic(message, for_tomorrow=False)

@dp.message(Command("check"))
async def cmd_check(message: Message) -> None:
    status_msg = await message.answer("🔄 Перевіряю оновлення на сайті ДТЕК...")
    updated_str, schedules = await dtek_service.get_all_schedules(force=True)

    today_s = next((s for s in schedules if s.get("is_today")), None)
    tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

    dates_found = []
    if today_s:
        dates_found.append(f"• Сьогодні ({today_s['date_formatted']})")
    if tomorrow_s:
        dates_found.append(f"• Завтра ({tomorrow_s['date_formatted']})")

    res_text = (
        "✅ <b>Дані успішно оновлено!</b>\n\n"
        f"🕒 <b>Останнє оновлення ДТЕК:</b> {updated_str or 'невідомо'}\n"
        f"📅 <b>Знайдено графіків:</b> {len(schedules)}\n"
        + ("\n".join(dates_found) if dates_found else "Немає активних графіків")
    )
    await status_msg.edit_text(res_text, reply_markup=get_main_keyboard())

@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    topic_id = await get_topic_id()
    last_chk = await get_setting("last_checked_at", "ще не проводилась")
    last_dtek = await get_setting("last_dtek_updated", "невідомо")

    text = (
        "⚙️ <b>Статус моніторингу:</b>\n\n"
        f"• <b>Адреса:</b> {LOCATION_NAME}\n"
        f"• <b>Черга:</b> {TARGET_GROUP.replace('GPV', 'Черга ')}\n"
        f"• <b>Цільова група:</b> <code>{GROUP_CHAT_ID}</code>\n"
        f"• <b>Топік ID:</b> <code>{topic_id or 'не встановлено'}</code>\n"
        f"• <b>Інтервал опитування:</b> {CHECK_INTERVAL_SECONDS // 60} хв\n"
        f"• <b>Остання перевірка:</b> {last_chk}\n"
        f"• <b>Останнє оновлення на ДТЕК:</b> {last_dtek}\n"
        "• <b>Статус:</b> 🟢 Активний"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(Command("set_topic"))
async def cmd_set_topic(message: Message) -> None:
    """Set the topic where this command was sent as the official alert topic."""
    thread_id = message.message_thread_id
    if not thread_id:
        await message.answer("⚠️ Ця команда має бути відправлена всередині теми (топіка) у супергрупі.")
        return

    await set_topic_id(thread_id)
    await message.answer(
        f"✅ <b>Цю тему успішно встановлено для сповіщень!</b> (ID теми: <code>{thread_id}</code>)",
        reply_markup=get_main_keyboard()
    )
    logger.info(f"Topic ID updated manually to {thread_id}")

@dp.message(Command("init_topic"))
async def cmd_init_topic(message: Message) -> None:
    """Force auto-create the topic."""
    topic_id = await auto_create_topic_if_needed()
    if topic_id:
        await message.answer(f"✅ Тему '💡 Світло / Гора' створено! ID: <code>{topic_id}</code>")
    else:
        await message.answer(
            "⚠️ Не вдалося створити тему автоматично.\n"
            "Переконайтеся, що бота додано в групу як адміністратора з правом 'Управління темами' (Manage Topics).\n"
            "Або створіть тему вручну і напишіть у ній команду <code>/set_topic</code>."
        )

# ----------------- Callback Handlers -----------------

@dp.callback_query(F.data == "btn_today")
async def cb_today(call: CallbackQuery) -> None:
    await call.answer()
    updated_str, schedules = await dtek_service.get_all_schedules(force=False)
    today_s = next((s for s in schedules if s.get("is_today")), None)
    tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

    if not today_s:
        await call.message.answer("⚠️ На сьогодні графік ще не сформовано.")
        return

    text = format_schedule_message(today_s, updated_str=updated_str, alert_type="normal", tomorrow_schedule=tomorrow_s)
    await call.message.answer(text, reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "btn_tomorrow")
async def cb_tomorrow(call: CallbackQuery) -> None:
    await call.answer()
    updated_str, schedules = await dtek_service.get_all_schedules(force=False)
    tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

    if not tomorrow_s:
        await call.message.answer(
            "⏳ <b>Графік на завтра ще не опубліковано ДТЕК.</b>\n"
            "Зазвичай публікується ввечері. Бот надішле його автоматично!",
            reply_markup=get_main_keyboard()
        )
        return

    text = format_schedule_message(tomorrow_s, updated_str=updated_str, alert_type="normal")
    await call.message.answer(text, reply_markup=get_main_keyboard())

@dp.callback_query(F.data == "btn_image")
async def cb_image(call: CallbackQuery) -> None:
    await call.answer()
    await send_schedule_graphic(call, for_tomorrow=False)

@dp.callback_query(F.data == "btn_img_today")
async def cb_img_today(call: CallbackQuery) -> None:
    await call.answer()
    await send_schedule_graphic(call, for_tomorrow=False)

@dp.callback_query(F.data == "btn_img_tomorrow")
async def cb_img_tomorrow(call: CallbackQuery) -> None:
    await call.answer()
    await send_schedule_graphic(call, for_tomorrow=True)

@dp.callback_query(F.data == "btn_check")
async def cb_check(call: CallbackQuery) -> None:
    await call.answer("Оновлюю дані з сайту ДТЕК...")
    updated_str, schedules = await dtek_service.get_all_schedules(force=True)
    today_s = next((s for s in schedules if s.get("is_today")), None)
    tomorrow_s = next((s for s in schedules if s.get("is_tomorrow")), None)

    dates_found = []
    if today_s:
        dates_found.append(f"• Сьогодні ({today_s['date_formatted']})")
    if tomorrow_s:
        dates_found.append(f"• Завтра ({tomorrow_s['date_formatted']})")

    res_text = (
        "✅ <b>Дані оновлено!</b>\n\n"
        f"🕒 <b>Останнє оновлення ДТЕК:</b> {updated_str or 'невідомо'}\n"
        f"📅 <b>Знайдено графіків:</b> {len(schedules)}\n"
        + ("\n".join(dates_found) if dates_found else "Немає активних графіків")
    )
    await call.message.answer(res_text, reply_markup=get_main_keyboard())

# ----------------- Render Web Server (for 24/7 Uptime) -----------------

async def health_check(request: web.Request) -> web.Response:
    return web.Response(text="DTEK Hora Light Bot is running 24/7!")

async def start_web_server() -> web.AppRunner | None:
    port = int(os.getenv("PORT", "0"))
    if port > 0:
        app = web.Application()
        app.router.add_get("/", health_check)
        app.router.add_get("/health", health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Health check web server running on port {port}")
        return runner
    return None

# ----------------- Main Entrypoint -----------------

async def main() -> None:
    logger.info("Initializing database...")
    await init_db()

    # Attempt to auto-create topic if bot already added to group
    await auto_create_topic_if_needed()

    # Launch background monitoring loop
    monitor_task = asyncio.create_task(monitoring_loop())

    # Start health check server if PORT is provided (Render.com)
    web_runner = await start_web_server()

    logger.info("Starting Telegram bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
