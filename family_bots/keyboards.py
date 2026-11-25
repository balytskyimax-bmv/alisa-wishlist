from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any
from formatter import format_money


def get_dashboard_main_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Compact 2-row dashboard buttons in group.
    - '➕ Внести оплату' is open to EVERYONE (wife & husband).
    - Other buttons are admin only.
    - '📊 Оновити' reposts the dashboard at the very bottom.
    """
    inline_kb = [
        [
            InlineKeyboardButton(text="➕ Внести оплату", callback_data="open_pay_cat_select"),
            InlineKeyboardButton(text="💰 Змінити суму", callback_data="open_edit_budget_cats"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Статті", callback_data="open_manage_items_menu"),
            InlineKeyboardButton(text="🔄 Новий місяць", callback_data="open_group_new_month"),
            InlineKeyboardButton(text="📊 Оновити", callback_data="refresh_to_bottom"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Bottom persistent keyboard for the Admin in private chat."""
    kb = [
        [
            KeyboardButton(text="➕ Додати платіж"),
            KeyboardButton(text="💰 Змінити суму"),
        ],
        [
            KeyboardButton(text="⚙️ Керування статтями"),
            KeyboardButton(text="🔄 Новий місяць"),
        ],
        [
            KeyboardButton(text="📊 Оновити дашборд"),
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# --- PAY FLOW KEYBOARDS (EVERYONE) ---
def get_categories_keyboard(
    categories: List[Dict[str, Any]], 
    callback_prefix: str, 
    back_callback: str = "back_to_dashboard"
) -> InlineKeyboardMarkup:
    inline_kb = []

    row = []
    for cat in categories:
        cat_id = cat["id"]
        name = cat["name"]
        row.append(InlineKeyboardButton(text=name, callback_data=f"{callback_prefix}:{cat_id}"))
        if len(row) == 2:
            inline_kb.append(row)
            row = []
    if row:
        inline_kb.append(row)

    back_text = "⬅️ Назад до табло" if back_callback == "back_to_dashboard" else "⬅️ Назад"
    inline_kb.append([InlineKeyboardButton(text=back_text, callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_subcategories_keyboard(expenses: List[Dict[str, Any]], callback_prefix: str, back_callback: str, category_id: int = None, show_pay_all: bool = False) -> InlineKeyboardMarkup:
    inline_kb = []

    if show_pay_all and category_id and expenses:
        cat_total = sum(e["amount"] for e in expenses)
        if cat_total > 0:
            inline_kb.append([
                InlineKeyboardButton(text=f"✅ Сплатити ВСЕ в категорії ({format_money(cat_total)})", callback_data=f"pay_all_cat:{category_id}")
            ])

    for exp in expenses:
        exp_id = exp["id"]
        name = exp["name"]
        disp_val = max(exp["amount"], exp.get("paid_amount", 0.0))
        amt = format_money(disp_val)
        is_paid = exp["is_paid"]
        icon = "✅" if is_paid else "⏳"
        btn_text = f"{icon} {name} ({amt})"
        inline_kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"{callback_prefix}:{exp_id}")])

    inline_kb.append([InlineKeyboardButton(text="⬅️ Назад до категорій", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_pay_action_keyboard(expense: Dict[str, Any], back_callback: str) -> InlineKeyboardMarkup:
    exp_id = expense["id"]
    amt_str = format_money(expense["amount"])

    inline_kb = [
        [
            InlineKeyboardButton(text="➕ Додати суму (+ грн)", callback_data=f"pay_custom:{exp_id}"),
        ],
        [
            InlineKeyboardButton(text=f"✅ Сплачено повністю ({amt_str})", callback_data=f"pay_full:{exp_id}"),
            InlineKeyboardButton(text="⏳ Скинути (0 грн)", callback_data=f"pay_reset:{exp_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад до підкатегорій", callback_data=back_callback),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


# --- MANAGE ITEMS MENU (ADMIN ONLY) ---
def get_manage_items_menu() -> InlineKeyboardMarkup:
    inline_kb = [
        [
            InlineKeyboardButton(text="📁 Створити ГОЛОВНУ категорію", callback_data="admin_add_main_cat_start"),
        ],
        [
            InlineKeyboardButton(text="✏️ Перейменувати ГОЛОВНУ категорію", callback_data="admin_rename_main_cat_start"),
        ],
        [
            InlineKeyboardButton(text="🗑 Видалити ГОЛОВНУ категорію", callback_data="admin_del_main_cat_start"),
        ],
        [
            InlineKeyboardButton(text="➕ Створити підкатегорію", callback_data="admin_add_subcat_start"),
        ],
        [
            InlineKeyboardButton(text="✏️ Перейменувати підкатегорію", callback_data="admin_rename_subcat_start"),
        ],
        [
            InlineKeyboardButton(text="🗑 Видалити підкатегорію", callback_data="admin_del_subcat_start"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Повернутися до табло", callback_data="back_to_dashboard"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_delete_main_cats_keyboard(categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    inline_kb = []
    for cat in categories:
        inline_kb.append([
            InlineKeyboardButton(text=f"🗑 {cat['name']}", callback_data=f"admin_del_cat_select:{cat['id']}")
        ])
    inline_kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="open_manage_items_menu")])
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_confirm_del_cat_keyboard(cat_id: int, cat_name: str) -> InlineKeyboardMarkup:
    inline_kb = [
        [
            InlineKeyboardButton(text="⚠️ Так, видалити категорію", callback_data=f"confirm_del_main_cat:{cat_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Скасувати", callback_data="open_manage_items_menu"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def get_confirm_new_month_keyboard(back_callback: str = "back_to_dashboard") -> InlineKeyboardMarkup:
    inline_kb = [
        [
            InlineKeyboardButton(text="✅ Так, почати новий місяць", callback_data="confirm_new_month"),
        ],
        [
            InlineKeyboardButton(text="❌ Скасувати", callback_data=back_callback),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)
