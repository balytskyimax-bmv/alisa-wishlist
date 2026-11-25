import os
import re
import html
import asyncio
import logging
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import config
import database as db
import formatter
import keyboards as kb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN) if config.BOT_TOKEN else None
dp = Dispatcher(storage=MemoryStorage())

_is_reposting = False


# --- FSM STATES ---
class PayCustomAmountState(StatesGroup):
    waiting_for_amount = State()


class EditBudgetState(StatesGroup):
    waiting_for_amount = State()


class AddMainCategoryState(StatesGroup):
    waiting_for_name = State()


class RenameMainCategoryState(StatesGroup):
    waiting_for_new_name = State()


class AddSubcatState(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_amount = State()
    waiting_for_note = State()


class RenameSubcatState(StatesGroup):
    waiting_for_new_name = State()


# --- HELPER FUNCTIONS ---
def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


async def auto_backup_to_admin(bot_instance: Bot, force: bool = False):
    """
    Sends the SQLite database backup to admin's private chat:
    - Only sends if at least 14 days have passed since the previous backup (or when force=True).
    - Preserves all payment history and edits in the database without notification spam.
    """
    if db.is_postgres():
        return
    if not config.ADMIN_ID or not os.path.exists(config.DB_PATH):
        return

    now = datetime.now()
    if not force:
        last_backup_str = await db.get_setting("last_backup_timestamp", "")
        if last_backup_str:
            try:
                last_dt = datetime.fromisoformat(last_backup_str)
                if (now - last_dt) < timedelta(days=14):
                    return
            except Exception:
                pass
        else:
            # First run: initialize timestamp so user is not spammed immediately
            await db.set_setting("last_backup_timestamp", now.isoformat())
            return

    try:
        now_str = now.strftime("%d.%m.%Y %H:%M")
        caption_title = (
            "💾 <b>Плановий бекап бази даних (раз на 2 тижні)</b>"
            if not force
            else "💾 <b>Резервна копія бази даних</b>"
        )
        await bot_instance.send_document(
            chat_id=config.ADMIN_ID,
            document=FSInputFile(config.DB_PATH),
            caption=(
                f"{caption_title}\n"
                f"📅 Час: <code>{now_str}</code>\n"
                f"📌 <i>Вся історія правок та платежів збережена. У разі потреби надішліть цей файл для /restore.</i>"
            ),
            parse_mode=ParseMode.HTML,
            disable_notification=True
        )
        await db.set_setting("last_backup_timestamp", now.isoformat())
    except Exception as e:
        logger.warning(f"Auto-backup to admin failed: {e}")


async def periodic_backup_worker(bot_instance: Bot):
    """Background worker that checks every 12 hours if the 14-day backup is due."""
    while True:
        try:
            await asyncio.sleep(43200)  # 12 hours
            await auto_backup_to_admin(bot_instance, force=False)
        except Exception as e:
            logger.warning(f"Periodic backup worker error: {e}")


async def safe_edit(call: types.CallbackQuery, text: str = None, reply_markup: types.InlineKeyboardMarkup = None):
    """Safely edits text or reply_markup, gracefully ignoring 'message is not modified' error."""
    try:
        await call.answer()
    except Exception:
        pass
    try:
        if text is not None:
            await call.message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        elif reply_markup is not None:
            await call.message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            logger.warning(f"TelegramBadRequest in safe_edit: {e}")
    except Exception as e:
        logger.warning(f"Exception in safe_edit: {e}")


async def repost_dashboard_at_bottom(bot_instance: Bot) -> bool:
    """
    Deletes the previous dashboard and sends a brand new one at the very bottom
    of the topic (used on manual /refresh, topic binding, restore, or if missing).
    """
    global _is_reposting
    if _is_reposting:
        return False
    _is_reposting = True

    try:
        chat_id = await db.get_setting("group_chat_id", str(config.GROUP_CHAT_ID or ""))
        topic_id = await db.get_setting("topic_id", str(config.TOPIC_ID or ""))
        old_msg_id = await db.get_setting("pinned_message_id")

        if not chat_id:
            return False

        # 1. Delete previous dashboard
        if old_msg_id:
            try:
                await bot_instance.delete_message(chat_id=int(chat_id), message_id=int(old_msg_id))
            except Exception as e:
                logger.warning(f"Could not delete old dashboard {old_msg_id}: {e}")

        # 2. Build text & markup
        categories = await db.get_all_data()
        month_name = await db.get_setting("current_month")
        text = formatter.format_budget_dashboard(categories, month_title=month_name)
        markup = kb.get_dashboard_main_inline_keyboard()

        kwargs = {
            "chat_id": int(chat_id),
            "text": text,
            "parse_mode": ParseMode.HTML,
            "reply_markup": markup
        }
        if topic_id:
            kwargs["message_thread_id"] = int(topic_id)

        # 3. Send at the very bottom
        try:
            new_msg = await bot_instance.send_message(**kwargs)
            await db.set_setting("pinned_message_id", str(new_msg.message_id))
            return True
        except Exception as e:
            logger.error(f"Error reposting dashboard at bottom: {e}")
            return False
    finally:
        _is_reposting = False


async def refresh_pinned_dashboard(bot_instance: Bot, custom_markup: types.InlineKeyboardMarkup = None) -> bool:
    """Updates the existing dashboard message text & markup in place without flickering."""
    chat_id = await db.get_setting("group_chat_id", str(config.GROUP_CHAT_ID or ""))
    msg_id = await db.get_setting("pinned_message_id")

    if not chat_id or not msg_id:
        return await repost_dashboard_at_bottom(bot_instance)

    categories = await db.get_all_data()
    month_name = await db.get_setting("current_month")
    text = formatter.format_budget_dashboard(categories, month_title=month_name)
    markup = custom_markup if custom_markup is not None else kb.get_dashboard_main_inline_keyboard()

    try:
        await bot_instance.edit_message_text(
            chat_id=int(chat_id),
            message_id=int(msg_id),
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return True
        logger.warning(f"In-place edit failed: {e}")
        return await repost_dashboard_at_bottom(bot_instance)
    except Exception as e:
        logger.warning(f"In-place edit failed: {e}")
        return await repost_dashboard_at_bottom(bot_instance)


# --- GROUP SETUP COMMANDS ---
@dp.message(Command(commands=["refresh", "menu", "help"]))
async def cmd_refresh(message: types.Message):
    """Deletes command message and posts the dashboard as the very last message."""
    try:
        await message.delete()
    except Exception:
        pass
    await repost_dashboard_at_bottom(bot)


@dp.message(Command("bind_topic"))
async def cmd_bind_topic(message: types.Message):
    """Admin command to bind the bot to the specific group topic."""
    if not is_admin(message.from_user.id):
        try:
            await message.delete()
        except Exception:
            pass
        return

    chat_id = message.chat.id
    thread_id = message.message_thread_id

    await db.set_setting("group_chat_id", str(chat_id))
    if thread_id:
        await db.set_setting("topic_id", str(thread_id))

    try:
        await message.delete()
    except Exception:
        pass

    await repost_dashboard_at_bottom(bot)


@dp.message(Command("pin"))
async def cmd_pin(message: types.Message):
    """Admin command to pin current dashboard."""
    try:
        await message.delete()
    except Exception:
        pass
    if not is_admin(message.from_user.id):
        return

    chat_id = await db.get_setting("group_chat_id")
    msg_id = await db.get_setting("pinned_message_id")
    if chat_id and msg_id:
        try:
            await bot.pin_chat_message(chat_id=int(chat_id), message_id=int(msg_id), disable_notification=True)
        except Exception:
            pass


# =====================================================================
# --- 1. FLOW: ВНЕСТИ ОПЛАТУ (ДОСТУПНО ВСІМ: ЧОЛОВІКУ ТА ДРУЖИНІ) ---
# =====================================================================

@dp.callback_query(F.data == "open_pay_cat_select")
async def callback_open_pay_cat_select(call: types.CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    categories = await db.get_all_data()
    kb_markup = kb.get_categories_keyboard(
        categories,
        callback_prefix="pay_cat"
    )
    await safe_edit(call, reply_markup=kb_markup)


@dp.callback_query(F.data == "ignore_info")
async def callback_ignore_info(call: types.CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass


@dp.callback_query(F.data.startswith("pay_cat:"))
async def callback_pay_cat_selected(call: types.CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    cat_id = int(call.data.split(":")[1])
    expenses = await db.get_expenses_by_category(cat_id)
    kb_markup = kb.get_subcategories_keyboard(
        expenses,
        callback_prefix="pay_subcat",
        back_callback="open_pay_cat_select",
        category_id=cat_id,
        show_pay_all=True
    )
    await safe_edit(call, reply_markup=kb_markup)


@dp.callback_query(F.data.startswith("pay_all_cat:"))
async def callback_pay_all_cat(call: types.CallbackQuery):
    cat_id = int(call.data.split(":")[1])
    cat = await db.get_category(cat_id)
    cat_name = cat["name"] if cat else "категорії"
    await db.mark_category_all_paid(cat_id)
    asyncio.create_task(auto_backup_to_admin(bot))

    expenses = await db.get_expenses_by_category(cat_id)
    kb_markup = kb.get_subcategories_keyboard(
        expenses,
        callback_prefix="pay_subcat",
        back_callback="open_pay_cat_select",
        category_id=cat_id,
        show_pay_all=True
    )
    try:
        await call.answer(f"✅ Всі витрати категорії '{cat_name}' сплачено!", show_alert=True)
    except Exception:
        pass

    if call.message and getattr(call.message.chat, "type", None) == "private":
        await refresh_pinned_dashboard(bot)
        await safe_edit(call, reply_markup=kb_markup)
    else:
        await refresh_pinned_dashboard(bot, custom_markup=kb_markup)


@dp.callback_query(F.data.startswith("pay_subcat:"))
async def callback_pay_subcat_selected(call: types.CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    exp_id = int(call.data.split(":")[1])
    exp = await db.get_expense(exp_id)
    if not exp:
        return

    history = await db.get_expense_history(exp_id, limit=5)
    hist_text = ""
    if history:
        hist_lines = []
        for h in history:
            u_name = f" ({h['user_name']})" if h.get("user_name") else ""
            hist_lines.append(f" • <b>+{formatter.format_money(h['amount'])}</b>{u_name}")
        hist_text = "\n\n📝 <b>Історія внесків:</b>\n" + "\n".join(hist_lines)

    status_icon = "✅ Сплачено" if exp["is_paid"] else "⏳ Очікує оплати"
    text = (
        f"<b>{exp['name']}</b>\n"
        f"Статус: {status_icon}\n"
        f"План: <b>{formatter.format_money(exp['amount'])}</b>\n"
        f"Вже внесено: <b>{formatter.format_money(exp['paid_amount'])}</b>"
        f"{hist_text}"
    )

    kb_markup = kb.get_pay_action_keyboard(exp, back_callback=f"pay_cat:{exp['category_id']}")
    await safe_edit(call, text=text, reply_markup=kb_markup)


@dp.callback_query(F.data.startswith("pay_full:"))
async def callback_pay_full(call: types.CallbackQuery):
    exp_id = int(call.data.split(":")[1])
    exp = await db.get_expense(exp_id)
    if not exp:
        await call.answer("Платіж не знайдено.")
        return

    user_name = call.from_user.full_name or ""
    await db.set_expense_payment(exp_id, exp["amount"], is_paid=1, user_name=user_name)
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)
    await call.answer(f"✅ {exp['name']} сплачено повністю ({formatter.format_money(exp['amount'])})!", show_alert=True)


@dp.callback_query(F.data.startswith("pay_reset:"))
async def callback_pay_reset(call: types.CallbackQuery):
    exp_id = int(call.data.split(":")[1])
    exp = await db.get_expense(exp_id)
    if not exp:
        await call.answer("Платіж не знайдено.")
        return

    await db.set_expense_payment(exp_id, 0.0, is_paid=0)
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)
    await call.answer(f"⏳ {exp['name']} скинуто на 0 грн (неоплачено).", show_alert=True)


@dp.callback_query(F.data.startswith("pay_custom:"))
async def callback_pay_custom(call: types.CallbackQuery, state: FSMContext):
    exp_id = int(call.data.split(":")[1])
    exp = await db.get_expense(exp_id)
    if not exp:
        await call.answer("Платіж не знайдено.")
        return

    await state.set_state(PayCustomAmountState.waiting_for_amount)
    await state.update_data(
        expense_id=exp_id,
        expense_name=exp["name"],
        chat_type=call.message.chat.type
    )

    current_paid_str = formatter.format_money(exp["paid_amount"])
    prompt = await call.message.reply(
        f"💬 Введіть суму, яку хочете <b>ДОДАТИ</b> до «<b>{exp['name']}</b>»:\n"
        f"<i>(Вже внесено раніше: {current_paid_str})\n\n"
        f"Наприклад: <code>500</code> або <code>1200</code>\n"
        f"Підказка: якщо потрібно перезаписати суму з нуля, введіть <code>=2000</code>)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ForceReply(selective=True)
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


@dp.message(PayCustomAmountState.waiting_for_amount)
async def process_pay_custom_amount(message: types.Message, state: FSMContext):
    if not message.text:
        return

    raw_text = message.text.strip()
    is_overwrite = raw_text.startswith("=")
    cleaned = raw_text.lstrip("=").replace(" ", "").replace(",", ".").replace("грн", "")

    try:
        val = float(cleaned)
        if val < 0:
            raise ValueError
    except ValueError:
        return

    data = await state.get_data()
    exp_id = data["expense_id"]
    prompt_msg_id = data.get("prompt_msg_id")
    user_name = message.from_user.full_name or ""

    if is_overwrite:
        await db.set_expense_payment(exp_id, val, user_name=user_name)
    else:
        await db.add_expense_payment(exp_id, val, user_name=user_name)

    await state.clear()

    # Clean up user message and prompt message immediately so topic stays clean
    try:
        if prompt_msg_id:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await message.delete()
    except Exception:
        pass

    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


# =====================================================================
# --- 2. FLOW: ЗМІНИТИ ПЛАНОВИЙ БЮДЖЕТ (ТІЛЬКИ АДМІНІСТРАТОР) ---
# =====================================================================

@dp.callback_query(F.data == "open_edit_budget_cats")
async def callback_open_edit_budget_cats(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Тільки адміністратор (чоловік) може змінювати плановий бюджет!", show_alert=True)
        return

    categories = await db.get_all_data()
    kb_markup = kb.get_categories_keyboard(categories, callback_prefix="edit_budg_cat")
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_budg_cat:"))
async def callback_edit_budg_cat_selected(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Доступ заборонено!", show_alert=True)
        return

    cat_id = int(call.data.split(":")[1])
    expenses = await db.get_expenses_by_category(cat_id)
    kb_markup = kb.get_subcategories_keyboard(
        expenses,
        callback_prefix="edit_budg_subcat",
        back_callback="open_edit_budget_cats"
    )
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_budg_subcat:"))
async def callback_edit_budg_subcat_selected(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Доступ заборонено!", show_alert=True)
        return

    exp_id = int(call.data.split(":")[1])
    exp = await db.get_expense(exp_id)
    if not exp:
        await call.answer("Платіж не знайдено.")
        return

    await state.set_state(EditBudgetState.waiting_for_amount)
    await state.update_data(
        expense_id=exp_id,
        expense_name=exp["name"],
        chat_type=call.message.chat.type
    )

    prompt = await call.message.reply(
        f"💰 Введіть нову <b>планову щомісячну суму</b> для <b>{exp['name']}</b> (поточна: {formatter.format_money(exp['amount'])}):\n"
        f"<i>(Наприклад: 3000 або 4500)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ForceReply(selective=True)
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


@dp.message(EditBudgetState.waiting_for_amount)
async def process_edit_budget_amount(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return

    cleaned = message.text.replace(" ", "").replace(",", ".").replace("грн", "")
    try:
        new_amt = float(cleaned)
        if new_amt < 0:
            raise ValueError
    except ValueError:
        return

    data = await state.get_data()
    exp_id = data["expense_id"]
    prompt_msg_id = data.get("prompt_msg_id")

    await db.update_expense_amount(exp_id, new_amt)
    await state.clear()

    # Clean up user message & prompt message
    try:
        if prompt_msg_id:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await message.delete()
    except Exception:
        pass

    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


# =====================================================================
# --- 3. FLOW: КЕРУВАННЯ СТАТТЯМИ ТА КАТЕГОРІЯМИ (ТІЛЬКИ АДМІНІСТРАТОР) ---
# =====================================================================

@dp.callback_query(F.data == "open_manage_items_menu")
async def callback_open_manage_items(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Тільки адміністратор (чоловік) має доступ!", show_alert=True)
        return

    await safe_edit(call, reply_markup=kb.get_manage_items_menu())
    await call.answer()


# --- ГОЛОВНІ КАТЕГОРІЇ ---
@dp.callback_query(F.data == "admin_add_main_cat_start")
async def callback_admin_add_main_cat_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Тільки адміністратор має доступ!", show_alert=True)
        return

    await state.set_state(AddMainCategoryState.waiting_for_name)
    prompt = await call.message.reply(
        "📁 Введіть назву нової <b>головної категорії</b> (можна з емодзі, наприклад: <code>🚗 Авто</code> або <code>🏖 Відпочинок</code>):",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ForceReply(selective=True)
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


@dp.message(AddMainCategoryState.waiting_for_name)
async def process_add_main_category_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return

    name = message.text.strip()
    prompt_msg_id = (await state.get_data()).get("prompt_msg_id")

    try:
        if prompt_msg_id:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await message.delete()
    except Exception:
        pass

    await db.add_category(name)
    await state.clear()
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


@dp.callback_query(F.data == "admin_rename_main_cat_start")
async def callback_admin_rename_main_cat_start(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Тільки адміністратор має доступ!", show_alert=True)
        return
    categories = await db.get_all_data()
    kb_markup = kb.get_categories_keyboard(
        categories,
        callback_prefix="admin_rename_cat_select",
        back_callback="open_manage_items_menu"
    )
    await safe_edit(call, reply_markup=kb_markup)


@dp.callback_query(F.data.startswith("admin_rename_cat_select:"))
async def callback_admin_rename_cat_select(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Тільки адміністратор має доступ!", show_alert=True)
        return
    cat_id = int(call.data.split(":")[1])
    cat = await db.get_category(cat_id)
    if not cat:
        return
    await state.set_state(RenameMainCategoryState.waiting_for_new_name)
    await state.update_data(category_id=cat_id, old_name=cat["name"])

    prompt = await call.message.reply(
        f"✏️ Введіть нову назву для головної категорії <b>{cat['name']}</b> (можна з емодзі):",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ForceReply(selective=True)
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


@dp.message(RenameMainCategoryState.waiting_for_new_name)
async def process_rename_main_cat(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return

    new_name = message.text.strip()
    data = await state.get_data()
    cat_id = data["category_id"]
    prompt_msg_id = data.get("prompt_msg_id")

    try:
        if prompt_msg_id:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await message.delete()
    except Exception:
        pass

    await db.rename_category(cat_id, new_name)
    await state.clear()
    if message.chat.type == "private":
        await message.answer(f"✅ Головну категорію перейменовано на <b>{new_name}</b>!", parse_mode=ParseMode.HTML)
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


@dp.callback_query(F.data == "admin_del_main_cat_start")
async def callback_admin_del_main_cat_start(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    categories = await db.get_all_data()
    kb_markup = kb.get_delete_main_cats_keyboard(categories)
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("admin_del_cat_select:"))
async def callback_admin_del_cat_select(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cat_id = int(call.data.split(":")[1])
    cat = await db.get_category(cat_id)
    cat_name = cat["name"] if cat else "категорію"
    kb_markup = kb.get_confirm_del_cat_keyboard(cat_id, cat_name)
    await safe_edit(
        call,
        text=f"⚠️ Ви дійсно хочете видалити головну категорію <b>'{cat_name}'</b> та ВСІ її статті?",
        reply_markup=kb_markup
    )
    await call.answer()


@dp.callback_query(F.data.startswith("confirm_del_main_cat:"))
async def callback_confirm_del_main_cat(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    cat_id = int(call.data.split(":")[1])
    cat = await db.get_category(cat_id)
    cat_name = cat["name"] if cat else ""
    await db.delete_category(cat_id)
    await call.answer(f"🗑 Категорію '{cat_name}' видалено!", show_alert=True)
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


# --- ПІДКАТЕГОРІЇ ---
@dp.callback_query(F.data == "admin_add_subcat_start")
async def callback_admin_add_subcat_start(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    categories = await db.get_all_data()
    kb_markup = kb.get_categories_keyboard(categories, callback_prefix="add_to_cat_id", back_callback="open_manage_items_menu")
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("add_to_cat_id:"))
async def callback_add_to_cat_selected(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    cat_id = int(call.data.split(":")[1])
    await state.update_data(category_id=cat_id)
    await state.set_state(AddSubcatState.waiting_for_name)

    prompt = await call.message.reply(
        "✏️ Введіть <b>назву</b> нової підкатегорії (наприклад: <i>Басейн</i> чи <i>Охорона</i>):",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ForceReply(selective=True)
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


@dp.message(AddSubcatState.waiting_for_name)
async def process_add_subcat_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    name = message.text.strip()
    prompt_msg_id = (await state.get_data()).get("prompt_msg_id")

    try:
        if prompt_msg_id:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await message.delete()
    except Exception:
        pass

    await state.update_data(name=name)
    await state.set_state(AddSubcatState.waiting_for_amount)

    prompt = await message.answer(
        f"Введіть щомісячну планову суму для <b>{name}</b> у грн:",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ForceReply(selective=True)
    )
    await state.update_data(prompt_amt_msg_id=prompt.message_id)


@dp.message(AddSubcatState.waiting_for_amount)
async def process_add_subcat_amount(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return

    cleaned = message.text.replace(" ", "").replace(",", ".").replace("грн", "")
    try:
        amt = float(cleaned)
        if amt < 0:
            raise ValueError
    except ValueError:
        return

    data = await state.get_data()
    prompt_amt_msg_id = data.get("prompt_amt_msg_id")

    try:
        if prompt_amt_msg_id:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_amt_msg_id)
        await message.delete()
    except Exception:
        pass

    await db.add_expense(category_id=data["category_id"], name=data["name"], amount=amt)
    await state.clear()
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


@dp.callback_query(F.data == "admin_rename_subcat_start")
async def callback_admin_rename_start(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    categories = await db.get_all_data()
    kb_markup = kb.get_categories_keyboard(categories, callback_prefix="rename_cat_id", back_callback="open_manage_items_menu")
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("rename_cat_id:"))
async def callback_rename_cat_selected(call: types.CallbackQuery):
    cat_id = int(call.data.split(":")[1])
    expenses = await db.get_expenses_by_category(cat_id)
    kb_markup = kb.get_subcategories_keyboard(expenses, callback_prefix="rename_exp_id", back_callback="admin_rename_subcat_start")
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("rename_exp_id:"))
async def callback_rename_exp_selected(call: types.CallbackQuery, state: FSMContext):
    exp_id = int(call.data.split(":")[1])
    exp = await db.get_expense(exp_id)
    if not exp:
        return
    await state.set_state(RenameSubcatState.waiting_for_new_name)
    await state.update_data(expense_id=exp_id, old_name=exp["name"])

    prompt = await call.message.reply(
        f"Введіть нову назву для <b>{exp['name']}</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=types.ForceReply(selective=True)
    )
    await state.update_data(prompt_msg_id=prompt.message_id)
    await call.answer()


@dp.message(RenameSubcatState.waiting_for_new_name)
async def process_rename_subcat(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id) or not message.text:
        return
    new_name = message.text.strip()
    data = await state.get_data()
    exp_id = data["expense_id"]
    prompt_msg_id = data.get("prompt_msg_id")

    try:
        if prompt_msg_id:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await message.delete()
    except Exception:
        pass

    await db.update_expense_name(exp_id, new_name)
    await state.clear()
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


@dp.callback_query(F.data == "admin_del_subcat_start")
async def callback_admin_del_start(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    categories = await db.get_all_data()
    kb_markup = kb.get_categories_keyboard(categories, callback_prefix="del_cat_id", back_callback="open_manage_items_menu")
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("del_cat_id:"))
async def callback_del_cat_selected(call: types.CallbackQuery):
    cat_id = int(call.data.split(":")[1])
    expenses = await db.get_expenses_by_category(cat_id)
    kb_markup = kb.get_subcategories_keyboard(expenses, callback_prefix="del_exp_id", back_callback="admin_del_subcat_start")
    await safe_edit(call, reply_markup=kb_markup)
    await call.answer()


@dp.callback_query(F.data.startswith("del_exp_id:"))
async def callback_del_exp_selected(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    exp_id = int(call.data.split(":")[1])
    exp = await db.get_expense(exp_id)
    if exp:
        await db.delete_expense(exp_id)
        await call.answer(f"🗑 Підкатегорію '{exp['name']}' видалено!", show_alert=True)
    asyncio.create_task(auto_backup_to_admin(bot))
    await refresh_pinned_dashboard(bot)


# =====================================================================
# --- 4. NEW MONTH & NAVIGATION ---
# =====================================================================

@dp.callback_query(F.data == "open_group_new_month")
async def callback_open_group_new_month(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Тільки адміністратор може розпочинати новий місяць!", show_alert=True)
        return
    await safe_edit(call, reply_markup=kb.get_confirm_new_month_keyboard())
    await call.answer()


@dp.callback_query(F.data == "confirm_new_month")
async def callback_confirm_new_month(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    # Save closing month backup before resetting
    await auto_backup_to_admin(bot, force=True)
    now = datetime.now()
    month_name = f"{formatter.MONTHS_UA.get(now.month, '')} {now.year}"
    await db.rollover_new_month(month_name)
    await call.answer(f"🎉 Новий місяць ({month_name}) розпочато! Статуси оплат очищено.", show_alert=True)
    await refresh_pinned_dashboard(bot)


async def ensure_group_bound(message):
    """Save group_chat_id and topic_id if not yet configured (e.g. fresh cloud DB)."""
    if not message or getattr(message.chat, "type", None) not in ("group", "supergroup"):
        return
    if not await db.get_setting("group_chat_id"):
        await db.set_setting("group_chat_id", str(message.chat.id))
        if getattr(message, "message_thread_id", None):
            await db.set_setting("topic_id", str(message.message_thread_id))


@dp.callback_query(F.data == "refresh_to_bottom")
async def callback_refresh_to_bottom(call: types.CallbackQuery):
    try:
        await call.answer("📊 Оновлюю табло...")
    except Exception:
        pass
    await ensure_group_bound(call.message)
    if call.message and getattr(call.message.chat, "type", None) in ("group", "supergroup"):
        if not await db.get_setting("pinned_message_id"):
            await db.set_setting("pinned_message_id", str(call.message.message_id))
    await refresh_pinned_dashboard(bot)


@dp.callback_query(F.data == "back_to_dashboard")
async def callback_back_to_dashboard(call: types.CallbackQuery, state: FSMContext = None):
    try:
        await call.answer()
    except Exception:
        pass
    if state:
        await state.clear()
    categories = await db.get_all_data()
    month_name = await db.get_setting("current_month")
    text = formatter.format_budget_dashboard(categories, month_title=month_name)
    await safe_edit(call, text=text, reply_markup=kb.get_dashboard_main_inline_keyboard())


# =====================================================================
# --- 5. PRIVATE CHAT & NATURAL TEXT ---
# =====================================================================

@dp.message(CommandStart())
async def cmd_start_handler(message: types.Message):
    if message.chat.type in ("group", "supergroup"):
        await ensure_group_bound(message)
        try:
            await message.delete()
        except Exception:
            pass
        await repost_dashboard_at_bottom(bot)
        return

    if not is_admin(message.from_user.id):
        await message.answer("Це сімейний бот обов'язкових платежів.")
        return

    await message.answer(
        "👋 <b>Панель керування сімейним бюджетом</b>\n\n"
        "Усі зміни тут або в групі <b>миттєво оновлюють дашборд</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.get_admin_main_keyboard()
    )


@dp.message(Command("backup"))
async def cmd_manual_backup(message: types.Message):
    """Admin command to download the SQLite database file (works in private chat or group)."""
    if not message.from_user or not is_admin(message.from_user.id):
        return

    in_group = message.chat.type in ("group", "supergroup")
    if in_group:
        await ensure_group_bound(message)
        try:
            await message.delete()
        except Exception:
            pass

    target_chat_id = config.ADMIN_ID if in_group else message.chat.id

    if db.is_postgres():
        await bot.send_message(
            target_chat_id,
            "🌐 <b>Ви використовуєте хмарну базу PostgreSQL!</b>\nДані зберігаються у хмарі назавжди й не залежать від локальних файлів.",
            parse_mode=ParseMode.HTML
        )
        return
    if not os.path.exists(config.DB_PATH):
        await bot.send_message(target_chat_id, "Файл бази даних не знайдено.")
        return

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    await bot.send_document(
        target_chat_id,
        document=FSInputFile(config.DB_PATH),
        caption=f"💾 <b>Резервна копія бази даних</b>\n📅 Дата: {now_str}",
        parse_mode=ParseMode.HTML
    )


@dp.message(Command("history"), F.chat.type == "private")
async def cmd_history(message: types.Message):
    """Admin command to view full audit log of recent edits and payments."""
    if not is_admin(message.from_user.id):
        return
    edits = await db.get_recent_edits(15)
    if not edits:
        await message.answer("📜 Історія змін поки порожня.")
        return
    lines = ["📜 <b>Останні 15 правок та внесків:</b>\n"]
    for item in edits:
        who = f" ({item['user_name']})" if item.get("user_name") else ""
        dt = str(item.get("created_at", ""))[:16]
        lines.append(f"• <code>{dt}</code> — {item['details']}{who}")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@dp.message(F.document, F.chat.type == "private")
async def handle_restore_db(message: types.Message):
    """Admin sends a .db file to instantly restore database state."""
    if not is_admin(message.from_user.id):
        return
    doc = message.document
    if not doc.file_name or not doc.file_name.endswith(".db"):
        return

    msg = await message.answer("⏳ Завантажую та відновлюю базу даних...")
    try:
        file_info = await bot.get_file(doc.file_id)
        await bot.download_file(file_info.file_path, destination=config.DB_PATH)
        await db.init_db()
        await msg.edit_text("✅ <b>Базу даних успішно відновлено!</b>\nОновлюю дашборд у групі...", parse_mode=ParseMode.HTML)
        await repost_dashboard_at_bottom(bot)
    except Exception as e:
        await msg.edit_text(f"❌ Помилка відновлення бази даних: {e}")


@dp.message(F.text == "➕ Додати платіж", F.chat.type == "private")
async def btn_p_add_pay(message: types.Message):
    categories = await db.get_all_data()
    await message.answer(
        "Оберіть категорію для внесення платежу:",
        reply_markup=kb.get_categories_keyboard(categories, callback_prefix="pay_cat")
    )


@dp.message(F.text == "💰 Змінити суму", F.chat.type == "private")
async def btn_p_edit_budget(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    categories = await db.get_all_data()
    await message.answer("Оберіть категорію для зміни суми:", reply_markup=kb.get_categories_keyboard(categories, callback_prefix="edit_budg_cat"))


@dp.message(F.text == "⚙️ Керування статтями", F.chat.type == "private")
async def btn_p_manage(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Оберіть дію:", reply_markup=kb.get_manage_items_menu())


@dp.message(F.text == "🔄 Новий місяць", F.chat.type == "private")
async def btn_p_new_month(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Розпочати новий місяць?", reply_markup=kb.get_confirm_new_month_keyboard())


@dp.message(F.text == "📊 Оновити дашборд", F.chat.type == "private")
async def btn_p_refresh(message: types.Message):
    ok = await repost_dashboard_at_bottom(bot)
    if ok:
        await message.answer("✅ Дашборд переміщено в самий низ топіка!")


async def try_handle_quick_text_payment(message: types.Message, text: str) -> bool:
    """
    Parses quick payments from natural text by either husband or wife:
    e.g. 'продукти 500', '500 продукти', 'бензин 1000 грн', 'оренда +', 'комуналка сплачено'.
    Sums amounts and records who added the payment.
    """
    text = text.strip()
    if not text:
        return False

    user_name = message.from_user.full_name or ""

    # Check for <name> + or <name> сплачено
    if text.endswith("+") or "сплачено" in text.lower():
        query = re.sub(r"(\+|\bсплачено\b)", "", text, flags=re.IGNORECASE).strip()
        exp = await db.find_expense_by_name(query)
        if exp:
            amt = exp["amount"] if exp["amount"] > 0 else exp["paid_amount"]
            await db.set_expense_payment(exp["id"], amt, is_paid=1, user_name=user_name)
            try:
                await message.delete()
            except Exception:
                pass
            asyncio.create_task(auto_backup_to_admin(bot))
            await refresh_pinned_dashboard(bot)
            return True

    # Try pattern: number at start e.g. "500 продукти"
    m_start = re.match(r"^(\d+(?:[.,]\d+)?)\s*(?:грн)?\s+(.+)$", text, re.IGNORECASE)
    # Try pattern: number at end e.g. "продукти 500"
    m_end = re.match(r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s*(?:грн)?$", text, re.IGNORECASE)

    val = None
    query = ""

    if m_start:
        val_str = m_start.group(1).replace(",", ".")
        try:
            val = float(val_str)
            query = m_start.group(2).strip()
        except ValueError:
            val = None
    elif m_end:
        val_str = m_end.group(2).replace(",", ".")
        try:
            val = float(val_str)
            query = m_end.group(1).strip()
        except ValueError:
            val = None

    if val is not None and val > 0 and query:
        exp = await db.find_expense_by_name(query)
        if exp:
            await db.add_expense_payment(exp["id"], val, user_name=user_name)
            try:
                await message.delete()
            except Exception:
                pass
            asyncio.create_task(auto_backup_to_admin(bot))
            await refresh_pinned_dashboard(bot)
            return True

    return False


@dp.message()
async def handle_any_incoming_message(message: types.Message, state: FSMContext):
    """
    Handles natural text commands or user receipts in group topic.
    STRICTLY ignores bot messages and service messages to prevent loops.
    Normal non-payment messages are left as-is without reposting the dashboard.
    """
    # 1. Never handle bot's own messages or service messages
    if not message.from_user or message.from_user.is_bot:
        return
    if message.pinned_message:
        return

    saved_group_id = await db.get_setting("group_chat_id")
    saved_topic_id = await db.get_setting("topic_id")

    # 2. Check if message is in the target group & budget topic:
    if message.chat.type in ["group", "supergroup"]:
        if str(message.chat.id) == saved_group_id and (not saved_topic_id or str(message.message_thread_id) == str(saved_topic_id)):
            handled_payment = False
            if message.text:
                handled_payment = await try_handle_quick_text_payment(message, message.text)

            # Only post an initial dashboard if none exists yet.
            if not handled_payment and not await db.get_setting("pinned_message_id"):
                await repost_dashboard_at_bottom(bot)


async def health_check(request):
    return web.Response(text="Family Budget & DTEK Hora Light Bots are running 24/7!")


async def run_dtek_companion_bot():
    """Runs the DTEK Hora Light companion bot (@svitlogorabot) inside the same container/service."""
    import sys
    from pathlib import Path

    dtek_dir = Path(__file__).resolve().parent / "dtek_bot"
    dtek_script = dtek_dir / "bot.py"
    if not dtek_script.exists():
        logger.warning(f"DTEK companion script not found at {dtek_script}")
        return

    env = os.environ.copy()
    env["PORT"] = "0"  # Primary web server is already handled by family_budget_bot

    while True:
        try:
            logger.info("Starting DTEK Hora Light companion bot (@svitlogorabot)...")
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(dtek_script),
                cwd=str(dtek_dir),
                env=env,
            )
            rc = await proc.wait()
            logger.warning(f"DTEK companion bot exited with code {rc}. Restarting in 10s...")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in DTEK companion bot supervisor: {e}")
        await asyncio.sleep(10)


async def api_status(request):
    group_id = await db.get_setting("group_chat_id")
    topic_id = await db.get_setting("topic_id")
    pinned_id = await db.get_setting("pinned_message_id")
    month = await db.get_setting("current_month")
    return web.json_response({
        "status": "ok",
        "bots": ["family_budget_bot", "dtek_hora_bot"],
        "group_chat_id": group_id,
        "topic_id": topic_id,
        "pinned_message_id": pinned_id,
        "current_month": month,
    })


async def api_repost(request):
    token = request.query.get("token", "")
    if token != config.BOT_TOKEN:
        return web.Response(text="Unauthorized", status=401)
    success = await repost_dashboard_at_bottom(bot)
    pinned_id = await db.get_setting("pinned_message_id")
    return web.json_response({"success": success, "pinned_message_id": pinned_id})


async def start_web_server():
    port = int(os.getenv("PORT", "0"))
    if port > 0:
        app = web.Application()
        app.router.add_get("/", health_check)
        app.router.add_get("/health", health_check)
        app.router.add_get("/api/status", api_status)
        app.router.add_get("/api/repost", api_repost)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Cloud healthcheck web server started on port {port}")


async def main():
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        return

    await db.init_db()
    if db.is_postgres():
        logger.info("Connected to Cloud PostgreSQL database!")
    else:
        logger.info("Using SQLite with Automatic Telegram Cloud Backup.")

    await start_web_server()
    asyncio.create_task(periodic_backup_worker(bot))
    asyncio.create_task(run_dtek_companion_bot())
    logger.info("Bot starting polling...")
    
    # Resilient polling loop that handles network drops/sleep smoothly
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
        except Exception as e:
            logger.warning(f"Polling loop encountered an error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
