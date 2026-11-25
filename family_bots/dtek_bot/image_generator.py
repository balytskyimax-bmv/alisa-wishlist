from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont

from config import BASE_DIR, LOCATION_NAME, TARGET_GROUP

BUNDLED_REGULAR = BASE_DIR / "fonts" / "Regular.ttf"
BUNDLED_BOLD = BASE_DIR / "fonts" / "Bold.ttf"

def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            BUNDLED_BOLD,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        if bold
        else [
            BUNDLED_REGULAR,
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    )
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_lightning_icon(draw: ImageDraw.ImageDraw, x: int, y: int, color=(40, 50, 60), crossed: bool = True):
    """Draw a vector lightning bolt, optionally with a slash across it."""
    # Polygon lightning points relative to (x, y), box 24x28
    pts = [
        (x + 14, y + 2),
        (x + 5,  y + 14),
        (x + 11, y + 14),
        (x + 8,  y + 26),
        (x + 19, y + 11),
        (x + 13, y + 11)
    ]
    draw.polygon(pts, fill=color)
    if crossed:
        # Red or dark slash line across
        draw.line([(x + 3, y + 4), (x + 21, y + 24)], fill=(180, 40, 40), width=3)

def generate_schedule_image(schedule: dict[str, Any], updated_str: str = "") -> str:
    """Generate an official-style DTEK schedule PNG graphic for the given schedule."""
    date_formatted = schedule.get("date_formatted", "")
    raw_hours = schedule.get("raw_hours", {})
    group_name = TARGET_GROUP.replace("GPV", "Черга ")

    width = 960
    height = 840
    img = Image.new("RGB", (width, height), color=(244, 246, 248))
    draw = ImageDraw.Draw(img)

    # Fonts
    font_brand = get_font(18, bold=True)
    font_title = get_font(26, bold=True)
    font_sub = get_font(16, bold=False)
    font_badge = get_font(18, bold=True)
    font_tbl_head = get_font(16, bold=True)
    font_hour = get_font(16, bold=True)
    font_legend = get_font(14, bold=False)
    font_footer = get_font(13, bold=False)

    # Top brand bar
    draw.rectangle([(0, 0), (width, 8)], fill=(255, 204, 0))

    # Header Card
    draw.rounded_rectangle([(30, 25), (width - 30, 140)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    
    # DTEK Logo-like text
    draw.text((50, 40), "DTEK", fill=(26, 26, 26), font=font_title)
    draw.text((130, 42), "КИЇВСЬКІ РЕГІОНАЛЬНІ ЕЛЕКТРОМЕРЕЖІ", fill=(80, 90, 100), font=font_brand)
    
    # Address and Date
    draw.text((50, 78), f"Графік відключень: {LOCATION_NAME}", fill=(26, 26, 26), font=font_sub)
    draw.text((50, 102), f"Дата: {date_formatted}", fill=(10, 100, 200), font=font_sub)

    # Queue Badge on the right
    badge_w, badge_h = 130, 38
    badge_x = width - 50 - badge_w
    badge_y = 48
    draw.rounded_rectangle([(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)], radius=19, fill=(254, 229, 126))
    draw.text((badge_x + 18, badge_y + 8), group_name, fill=(26, 26, 26), font=font_badge)

    # Main Table Container Card
    tbl_top = 160
    tbl_bottom = 690
    draw.rounded_rectangle([(30, tbl_top), (width - 30, tbl_bottom)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)

    # 2 columns: Column 1 is hours 1..12 (00-01 to 11-12), Column 2 is hours 13..24 (12-13 to 23-24)
    col_w = (width - 60 - 40) // 2
    col1_x = 50
    col2_x = 50 + col_w + 20

    def draw_column(start_h: int, end_h: int, x: int):
        # Column header
        draw.rounded_rectangle([(x, tbl_top + 15), (x + col_w, tbl_top + 50)], radius=8, fill=(241, 245, 249))
        draw.text((x + 25, tbl_top + 22), "Часовий проміжок", fill=(71, 85, 105), font=font_tbl_head)
        draw.text((x + col_w - 120, tbl_top + 22), "Світло", fill=(71, 85, 105), font=font_tbl_head)

        row_y = tbl_top + 60
        row_h = 37

        for h in range(start_h, end_h + 1):
            h_str = str(h)
            val = raw_hours.get(h_str, "yes")
            time_label = f"{h-1:02d}:00 – {h:02d}:00"

            # Row background
            draw.line([(x, row_y + row_h), (x + col_w, row_y + row_h)], fill=(241, 245, 249), width=1)

            # Hour label
            draw.text((x + 20, row_y + 8), time_label, fill=(30, 41, 59), font=font_hour)

            # Status cell (box on right)
            box_w, box_h = 130, 30
            box_x = x + col_w - box_w - 10
            box_y = row_y + 3

            if val == "yes":
                # Power ON
                draw.rounded_rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
                draw.text((box_x + 30, box_y + 6), "Є світло", fill=(16, 149, 90), font=get_font(14, bold=True))
            elif val == "no":
                # Power OFF
                draw.rounded_rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)], radius=6, fill=(243, 244, 246), outline=(209, 213, 219), width=1)
                draw_lightning_icon(draw, box_x + 12, box_y + 2, color=(55, 65, 81), crossed=True)
                draw.text((box_x + 42, box_y + 6), "Немає", fill=(75, 85, 99), font=get_font(14, bold=True))
            elif val == "first":
                # First 30 min OFF, second 30 min ON
                draw.rounded_rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)], radius=6, fill=(255, 255, 255), outline=(209, 213, 219), width=1)
                # Left half: OFF (first 30 min)
                draw.rectangle([(box_x + 1, box_y + 1), (box_x + box_w // 2, box_y + box_h - 1)], fill=(243, 244, 246))
                draw_lightning_icon(draw, box_x + 6, box_y + 2, color=(55, 65, 81), crossed=True)
                # Right half: ON
                draw.rectangle([(box_x + box_w // 2, box_y + 1), (box_x + box_w - 1, box_y + box_h - 1)], fill=(236, 253, 245))
                draw.text((box_x + box_w // 2 + 8, box_y + 6), "30 хв є", fill=(16, 149, 90), font=get_font(12, bold=True))
            elif val == "second":
                # First 30 min ON, second 30 min OFF
                draw.rounded_rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)], radius=6, fill=(255, 255, 255), outline=(209, 213, 219), width=1)
                # Left half: ON
                draw.rectangle([(box_x + 1, box_y + 1), (box_x + box_w // 2, box_y + box_h - 1)], fill=(236, 253, 245))
                draw.text((box_x + 6, box_y + 6), "30 хв є", fill=(16, 149, 90), font=get_font(12, bold=True))
                # Right half: OFF
                draw.rectangle([(box_x + box_w // 2, box_y + 1), (box_x + box_w - 1, box_y + box_h - 1)], fill=(243, 244, 246))
                draw_lightning_icon(draw, box_x + box_w // 2 + 10, box_y + 2, color=(55, 65, 81), crossed=True)
            else:
                # Maybe / Yellow
                draw.rounded_rectangle([(box_x, box_y), (box_x + box_w, box_y + box_h)], radius=6, fill=(254, 252, 232), outline=(254, 240, 138), width=1)
                draw.text((box_x + 25, box_y + 6), "Можливо", fill=(161, 98, 7), font=get_font(14, bold=True))

            row_y += row_h

    # Draw both 12-hour columns
    draw_column(1, 12, col1_x)
    draw_column(13, 24, col2_x)

    # Footer Card with Legend & Timestamp
    foot_y = 710
    draw.rounded_rectangle([(30, foot_y), (width - 30, foot_y + 105)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)

    # Legend items
    leg_x = 50
    leg_y = foot_y + 20

    # 1. On
    draw.rounded_rectangle([(leg_x, leg_y), (leg_x + 22, leg_y + 22)], radius=4, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    draw.text((leg_x + 30, leg_y + 2), "Світло є", fill=(30, 41, 59), font=font_legend)

    # 2. Off
    leg_x += 160
    draw.rounded_rectangle([(leg_x, leg_y), (leg_x + 22, leg_y + 22)], radius=4, fill=(243, 244, 246), outline=(209, 213, 219), width=1)
    draw_lightning_icon(draw, leg_x - 1, leg_y - 2, color=(55, 65, 81), crossed=True)
    draw.text((leg_x + 30, leg_y + 2), "Світла немає", fill=(30, 41, 59), font=font_legend)

    # 3. Partial 30m
    leg_x += 180
    draw.rounded_rectangle([(leg_x, leg_y), (leg_x + 22, leg_y + 22)], radius=4, fill=(255, 255, 255), outline=(209, 213, 219), width=1)
    draw.rectangle([(leg_x + 1, leg_y + 1), (leg_x + 11, leg_y + 21)], fill=(243, 244, 246))
    draw.rectangle([(leg_x + 11, leg_y + 1), (leg_x + 21, leg_y + 21)], fill=(236, 253, 245))
    draw.text((leg_x + 30, leg_y + 2), "Відключення на 30 хв", fill=(30, 41, 59), font=font_legend)

    # Timestamp & Generator note
    out_dir = BASE_DIR / "generated_charts"
    out_dir.mkdir(exist_ok=True)
    
    update_note = f"Останнє оновлення ДТЕК: {updated_str}" if updated_str else ""
    draw.text((50, foot_y + 60), f"Графік відключень @svitlogorabot  •  {update_note}", fill=(100, 116, 139), font=font_footer)

    date_key = schedule.get("date_str", "latest")
    file_path = out_dir / f"schedule_{date_key}.png"
    img.save(str(file_path), format="PNG", optimize=True)
    return str(file_path)
