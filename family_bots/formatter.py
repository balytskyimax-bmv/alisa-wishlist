import datetime
import html
from typing import List, Dict, Any

MONTHS_UA = {
    1: "СІЧЕНЬ", 2: "ЛЮТИЙ", 3: "БЕРЕЗЕНЬ", 4: "КВІТЕНЬ",
    5: "ТРАВЕНЬ", 6: "ЧЕРВЕНЬ", 7: "ЛИПЕНЬ", 8: "СЕРПЕНЬ",
    9: "ВЕРЕСЕНЬ", 10: "ЖОВТЕНЬ", 11: "ЛИСТОПАД", 12: "ГРУДЕНЬ"
}


def format_money(amount: float) -> str:
    """Format money with space as thousands separator, e.g. 35 000 грн."""
    if amount == int(amount):
        formatted = f"{int(amount):,}".replace(",", " ")
    else:
        formatted = f"{amount:,.2f}".replace(",", " ")
    return f"{formatted} грн"


def format_money_short(amount: float) -> str:
    """Compact format for headers, e.g. 35k or 2.5k."""
    if amount >= 1000:
        val = amount / 1000
        if val == int(val):
            return f"{int(val)}k"
        return f"{val:.1f}k"
    return f"{int(amount)}"


def generate_progress_bar(paid: float, total: float, length: int = 8) -> str:
    """Compact visual progress bar like [████░░░░]."""
    if total <= 0:
        return f"[{'░' * length}]"
    
    ratio = min(max(paid / total, 0.0), 1.0)
    filled = round(ratio * length)
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}]"


def format_budget_dashboard(categories: List[Dict[str, Any]], month_title: str = None) -> str:
    """
    Compact 1-screen aesthetic HTML dashboard for mobile.
    """
    now = datetime.datetime.now()
    if not month_title:
        month_name = MONTHS_UA.get(now.month, "")
        month_title = f"{month_name} {now.year}"
    month_title = html.escape(str(month_title))

    def get_item_paid(e: Dict[str, Any]) -> float:
        if e["paid_amount"] > 0:
            return e["paid_amount"]
        return e["amount"] if e["is_paid"] == 1 else 0.0

    # Calculate grand total across all categories to determine share of budget
    grand_total = 0.0
    for cat in categories:
        expenses = cat.get("expenses", [])
        grand_total += sum(max(e["amount"], get_item_paid(e)) for e in expenses)

    total_amount = 0.0
    total_paid = 0.0

    sections_text = []

    for cat in categories:
        cat_name = html.escape(str(cat["name"]))
        expenses = cat.get("expenses", [])
        if not expenses:
            continue

        cat_total = sum(max(e["amount"], get_item_paid(e)) for e in expenses)
        cat_paid = sum(get_item_paid(e) for e in expenses)

        total_amount += cat_total
        total_paid += cat_paid

        cat_ratio = min(max(cat_paid / cat_total, 0.0), 1.0) if cat_total > 0 else 0.0
        cat_percent = int(cat_ratio * 100)

        # Share of total budget
        if grand_total > 0 and cat_total > 0:
            share_pct = (cat_total / grand_total) * 100
            if 0 < share_pct < 1:
                share_str = "&lt;1% від бюджету • "
            else:
                share_str = f"{round(share_pct)}% від бюджету • "
        else:
            share_str = ""

        # Header with category name, share of budget, and paid progress
        if cat_total > 0:
            header_meta = f"{share_str}оплачено {cat_percent}% • {format_money_short(cat_paid)}/{format_money_short(cat_total)}"
        elif cat_paid > 0:
            header_meta = f"оплачено {format_money(cat_paid)}"
        else:
            header_meta = "оплачено 0% • 0/0"

        lines = [f"<b>{cat_name}</b> <i>({header_meta})</i>"]

        for exp in expenses:
            name = html.escape(str(exp["name"]))
            is_paid = exp["is_paid"]
            paid_amt = get_item_paid(exp)
            planned_amt = exp["amount"]
            note = exp.get("note", "")

            note_str = f" <i>({html.escape(str(note))})</i>" if note else ""

            if planned_amt > 0 and paid_amt > planned_amt:
                amt = format_money(paid_amt)
                status_icon = "✅"
                extra_str = f" <i>(план {format_money_short(planned_amt)})</i>"
            else:
                effective_amt = planned_amt if planned_amt > 0 else paid_amt
                amt = format_money(effective_amt)
                status_icon = "✅" if (is_paid or (planned_amt == 0 and paid_amt > 0)) else "⏳"

                if planned_amt > 0 and not is_paid and paid_amt > 0:
                    extra_str = f" <i>(спл. {format_money_short(paid_amt)})</i>"
                else:
                    extra_str = ""

            lines.append(f" • {name}: <b>{amt}</b> {status_icon}{note_str}{extra_str}")

        sections_text.append("\n".join(lines))

    # Calculate remaining & totals
    remaining = max(0.0, total_amount - total_paid)
    total_percent = int((total_paid / total_amount * 100)) if total_amount > 0 else 0
    total_bar = generate_progress_bar(total_paid, total_amount, length=8)

    body = "\n\n".join(sections_text)

    dashboard = (
        f"📌 <b>БЮДЖЕТ — {month_title}</b>\n"
        f"──────\n"
        f"{body}\n"
        f"──────\n"
        f"📊 <code>{total_bar}</code> <b>{total_percent}%</b> (сплачено <b>{format_money(total_paid)}</b>)\n"
        f"💳 Всього: <b>{format_money(total_amount)}</b> | ⏳ Залишок: <b>{format_money(remaining)}</b>"
    )

    return dashboard
