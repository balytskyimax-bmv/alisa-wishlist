from __future__ import annotations
from typing import Any
from config import LOCATION_NAME, TARGET_GROUP
from dtek_service import get_current_power_status

def format_schedule_message(
    schedule: dict[str, Any],
    updated_str: str = "",
    alert_type: str = "normal",  # "normal", "new_tomorrow", "updated"
    tomorrow_schedule: dict[str, Any] | None = None,
) -> str:
    """Format parsed schedule into an aesthetic Telegram HTML message."""
    is_today = schedule.get("is_today", False)
    is_tomorrow = schedule.get("is_tomorrow", False)
    date_formatted = schedule.get("date_formatted", "")
    group_name = TARGET_GROUP.replace("GPV", "Черга ")

    # Header depending on context
    if alert_type == "new_tomorrow":
        header = f"⚡️ <b>НОВИЙ ГРАФІК НА ЗАВТРА</b>\n📅 <b>{date_formatted}</b>"
    elif alert_type == "updated":
        day_label = "СЬОГОДНІ" if is_today else ("ЗАВТРА" if is_tomorrow else date_formatted)
        header = f"🚨 <b>УВАГА: ОНОВЛЕНО ГРАФІК НА {day_label}!</b>\n📅 <b>{date_formatted}</b>"
    elif is_today:
        header = f"💡 <b>ГРАФІК ТА СТАТУС НА СЬОГОДНІ</b>\n📅 <b>{date_formatted}</b>"
    elif is_tomorrow:
        header = f"⚡️ <b>ГРАФІК НА ЗАВТРА</b>\n📅 <b>{date_formatted}</b>"
    else:
        header = f"📅 <b>ГРАФІК НА {date_formatted}</b>"

    lines = [
        header,
        f"📍 <i>{LOCATION_NAME} ({group_name})</i>",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    # Live status if today
    if is_today:
        live = get_current_power_status(schedule, tomorrow_schedule=tomorrow_schedule)
        if live.get("has_data"):
            curr_state = live["current_state"]
            if curr_state == "off":
                curr_icon = "🔴"
                curr_text = "Світла немає"
            elif curr_state == "on":
                curr_icon = "🟢"
                curr_text = "Світло є"
            elif curr_state == "maybe":
                curr_icon = "🟡"
                curr_text = "Можливе відключення"
            else:
                curr_icon = "⚪️"
                curr_text = "Статус невизначений"

            lines.append(f"{curr_icon} <b>Зараз ({live['current_time_str']}): {curr_text}</b>")

            if live.get("next_change_time"):
                next_st = live["next_state"]
                if next_st == "off":
                    act = "Вимкнення світла"
                    act_icon = "🔻"
                elif next_st == "on":
                    act = "Увімкнення світла"
                    act_icon = "🔺"
                else:
                    act = "Зміна графіка"
                    act_icon = "⏳"

                lines.append(f"{act_icon} {act}: о <b>{live['next_change_time']}</b> <i>(через {live['time_left_str']})</i>")
            lines.append("────────────────────")

    # 24-hour visual progress bar (split into two 12-hour rows for perfect mobile rendering)
    bar_str = schedule.get("bar_str", "")
    if bar_str and len(bar_str) >= 24:
        row1 = bar_str[:12]
        row2 = bar_str[12:24]
        lines.append("📊 <b>Шкала доби:</b>")
        lines.append(f"<code>00–12: {row1}</code>")
        lines.append(f"<code>12–24: {row2}</code>")
        lines.append("<i>(🟩 є світло  |  🟥 немає  |  🟧 30 хв)</i>")
        lines.append("────────────────────")

    # Time ranges
    lines.append("⏰ <b>Розклад по годинах:</b>")
    ranges = schedule.get("ranges", [])
    if not ranges:
        lines.append("<i>Графік відсутній або відключень не заплановано</i>")
    else:
        for r in ranges:
            state = r["state"]
            if state == "off":
                icon = "🔴"
                state_text = "Немає світла"
            elif state == "on":
                icon = "🟢"
                state_text = "Світло є"
            elif state == "maybe":
                icon = "🟡"
                state_text = "Можливе відключення"
            else:
                icon = "⚪️"
                state_text = "Невідомо"

            lines.append(f"{icon} <code>{r['start']} – {r['end']}</code> ({r['duration_str']}) — {state_text}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Summary
    off_mins = schedule.get("off_minutes", 0)
    on_mins = schedule.get("on_minutes", 0)
    maybe_mins = schedule.get("maybe_minutes", 0)

    off_h = off_mins // 60
    off_m = off_mins % 60
    off_str = f"{off_h} год" + (f" {off_m} хв" if off_m else "")

    on_h = on_mins // 60
    on_m = on_mins % 60
    on_str = f"{on_h} год" + (f" {on_m} хв" if on_m else "")

    lines.append("⏳ <b>Підсумок доби:</b>")
    lines.append(f"• ❌ Без світла: <b>~{off_str}</b>")
    lines.append(f"• ✅ Зі світлом: <b>~{on_str}</b>")
    if maybe_mins > 0:
        maybe_h = maybe_mins // 60
        maybe_m = maybe_mins % 60
        maybe_str = f"{maybe_h} год" + (f" {maybe_m} хв" if maybe_m else "")
        lines.append(f"• ⚠️ Можливе відключення: <b>~{maybe_str}</b>")

    if updated_str:
        lines.append(f"\n🕒 <i>Оновлено ДТЕК: {updated_str}</i>")

    return "\n".join(lines)
