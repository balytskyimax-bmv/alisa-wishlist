from __future__ import annotations
import aiohttp
import hashlib
import json
import logging
import time
from datetime import datetime, date, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from config import DATA_URL, TARGET_GROUP, TARGET_REGION

logger = logging.getLogger(__name__)
KYIV_TZ = ZoneInfo("Europe/Kyiv")

UKR_WEEKDAYS = {
    0: "Понеділок",
    1: "Вівторок",
    2: "Середа",
    3: "Четвер",
    4: "П'ятниця",
    5: "Субота",
    6: "Неділя"
}

def slot_to_time(slot_idx: int) -> str:
    """Convert half-hour slot index (0..47) to HH:MM string."""
    h = slot_idx // 2
    m = (slot_idx % 2) * 30
    return f"{h:02d}:{m:02d}"

def calculate_hash(raw_hours: dict[str, str]) -> str:
    """Generate deterministic hash for a daily schedule to track changes."""
    sorted_items = sorted(raw_hours.items(), key=lambda x: int(x[0]))
    raw_str = "|".join(f"{k}:{v}" for k, v in sorted_items)
    return hashlib.md5(raw_str.encode("utf-8")).hexdigest()

def parse_group_schedule(dt_date: date, raw_hours: dict[str, str]) -> dict[str, Any]:
    """Parse DTEK hourly format for a single day into 48 slots and intervals."""
    # Build 48 half-hour slots: 0..47
    # Build 48 half-hour slots: 0..47
    # Note: In DTEK system, 'yes' means power is ON, 'no' means power is OFF (blackout)
    slots: list[str] = []
    for h in range(1, 25):
        val = raw_hours.get(str(h), "yes")
        if val == "yes":
            slots.extend(["on", "on"])
        elif val == "no":
            slots.extend(["off", "off"])
        elif val == "first":
            # Світла не буде перші 30 хв
            slots.extend(["off", "on"])
        elif val == "second":
            # Світла не буде другі 30 хв
            slots.extend(["on", "off"])
        elif val == "mfirst":
            slots.extend(["maybe", "on"])
        elif val == "msecond":
            slots.extend(["on", "maybe"])
        elif val == "maybe":
            slots.extend(["maybe", "maybe"])
        else:
            slots.extend(["unknown", "unknown"])

    # Group into consecutive ranges
    ranges = []
    if slots:
        curr_state = slots[0]
        start_slot = 0
        for i in range(1, len(slots)):
            if slots[i] != curr_state:
                ranges.append((start_slot, i, curr_state))
                start_slot = i
                curr_state = slots[i]
        ranges.append((start_slot, len(slots), curr_state))

    formatted_ranges = []
    for start, end, state in ranges:
        start_t = slot_to_time(start)
        end_t = "24:00" if end == 48 else slot_to_time(end)
        duration_mins = (end - start) * 30
        
        hours = duration_mins // 60
        mins = duration_mins % 60
        if hours > 0 and mins > 0:
            dur_str = f"{hours} год {mins} хв"
        elif hours > 0:
            dur_str = f"{hours} год"
        else:
            dur_str = f"{mins} хв"

        formatted_ranges.append({
            "start": start_t,
            "end": end_t,
            "duration_mins": duration_mins,
            "duration_str": dur_str,
            "state": state
        })

    off_minutes = slots.count("off") * 30
    on_minutes = slots.count("on") * 30
    maybe_minutes = slots.count("maybe") * 30

    # 24-char visual bar
    bar_icons = []
    for h in range(1, 25):
        val = raw_hours.get(str(h), "yes")
        if val == "yes":
            bar_icons.append("🟩")
        elif val == "no":
            bar_icons.append("🟥")
        elif val in ("first", "second"):
            bar_icons.append("🟧")
        elif val in ("maybe", "mfirst", "msecond"):
            bar_icons.append("🟨")
        else:
            bar_icons.append("⬜️")
    bar_str = "".join(bar_icons)

    weekday_name = UKR_WEEKDAYS.get(dt_date.weekday(), "")
    date_str = dt_date.isoformat()
    date_formatted = f"{dt_date.strftime('%d.%m.%Y')} ({weekday_name})"

    now_kyiv = datetime.now(KYIV_TZ)
    is_today = (dt_date == now_kyiv.date())
    is_tomorrow = (dt_date == (now_kyiv.date() + timedelta(days=1)))

    return {
        "date": dt_date,
        "date_str": date_str,
        "date_formatted": date_formatted,
        "is_today": is_today,
        "is_tomorrow": is_tomorrow,
        "raw_hours": raw_hours,
        "slots": slots,
        "ranges": formatted_ranges,
        "off_minutes": off_minutes,
        "on_minutes": on_minutes,
        "maybe_minutes": maybe_minutes,
        "bar_str": bar_str,
        "hash": calculate_hash(raw_hours)
    }

def get_current_power_status(
    today_schedule: dict[str, Any] | None,
    tomorrow_schedule: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Calculate the live power status right now and time to next change."""
    now_kyiv = datetime.now(KYIV_TZ)
    if not today_schedule:
        return {
            "has_data": False,
            "current_state": "unknown",
            "time_str": now_kyiv.strftime("%H:%M")
        }

    slots = today_schedule["slots"]
    # 0..47
    current_slot = now_kyiv.hour * 2 + (1 if now_kyiv.minute >= 30 else 0)
    if current_slot >= 48:
        current_slot = 47

    current_state = slots[current_slot]

    # Find next change within today
    next_slot = current_slot + 1
    while next_slot < 48 and slots[next_slot] == current_state:
        next_slot += 1

    next_change_time = None
    next_state = None
    mins_until_change = 0

    if next_slot < 48:
        next_change_time = slot_to_time(next_slot)
        next_state = slots[next_slot]
        next_slot_target_mins = (next_slot // 2) * 60 + ((next_slot % 2) * 30)
        curr_mins = now_kyiv.hour * 60 + now_kyiv.minute
        mins_until_change = max(0, next_slot_target_mins - curr_mins)
    else:
        # Crosses to midnight. Check tomorrow if available
        curr_mins = now_kyiv.hour * 60 + now_kyiv.minute
        mins_until_midnight = max(0, 1440 - curr_mins)

        if tomorrow_schedule and tomorrow_schedule.get("slots"):
            t_slots = tomorrow_schedule["slots"]
            t_idx = 0
            while t_idx < 48 and t_slots[t_idx] == current_state:
                t_idx += 1
            if t_idx < 48:
                next_state = t_slots[t_idx]
                next_change_time = f"завтра о {slot_to_time(t_idx)}"
                mins_until_change = mins_until_midnight + (t_idx * 30)
            else:
                next_state = "unknown"
                next_change_time = "завтра"
                mins_until_change = mins_until_midnight + 1440
        else:
            next_state = "unknown"
            next_change_time = "24:00"
            mins_until_change = mins_until_midnight

    hours_left = mins_until_change // 60
    mins_left = mins_until_change % 60
    if hours_left > 0 and mins_left > 0:
        time_left_str = f"{hours_left} год {mins_left} хв"
    elif hours_left > 0:
        time_left_str = f"{hours_left} год"
    else:
        time_left_str = f"{mins_left} хв"

    return {
        "has_data": True,
        "current_time_str": now_kyiv.strftime("%H:%M"),
        "current_state": current_state,
        "next_change_time": next_change_time,
        "next_state": next_state,
        "mins_until_change": mins_until_change,
        "time_left_str": time_left_str
    }

class DtekService:
    def __init__(self, data_url: str = DATA_URL, group: str = TARGET_GROUP):
        self.data_url = data_url
        self.group = group
        self._last_data: dict[str, Any] | None = None
        self._last_fetch_time: float = 0

    async def fetch_data(self, force: bool = False) -> dict[str, Any] | None:
        """Fetch raw JSON from upstream repository with cache headers."""
        now = time.time()
        # Cache for 60 seconds unless forced
        if not force and self._last_data and (now - self._last_fetch_time < 60):
            return self._last_data

        cache_buster_url = f"{self.data_url}?_cb={int(now)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; DtekLightBot/1.0)",
            "Accept": "application/json"
        }

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(cache_buster_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        self._last_data = data
                        self._last_fetch_time = now
                        logger.info("Successfully fetched DTEK outage data.")
                        return data
                    else:
                        logger.warning(f"Failed to fetch DTEK data, HTTP status: {response.status}")
                        return self._last_data
        except Exception as e:
            logger.error(f"Error fetching DTEK data: {e}")
            return self._last_data

    async def get_all_schedules(self, force: bool = False) -> tuple[str, list[dict[str, Any]]]:
        """
        Fetch and parse all schedules for TARGET_GROUP.
        Returns: (source_last_updated_str, list of parsed daily schedules sorted by date)
        """
        data = await self.fetch_data(force=force)
        if not data:
            return "", []

        source_updated_iso = data.get("lastUpdated", "")
        updated_str = ""
        if source_updated_iso:
            try:
                # Handle ISO datetime e.g. "2026-11-06T19:51:15.433Z"
                dt_iso = datetime.fromisoformat(source_updated_iso.replace("Z", "+00:00"))
                dt_kyiv = dt_iso.astimezone(KYIV_TZ)
                updated_str = dt_kyiv.strftime("%d.%m о %H:%M")
            except Exception:
                updated_str = source_updated_iso

        fact_data = data.get("fact", {}).get("data", {})
        schedules: list[dict[str, Any]] = []

        for ts_str, groups in fact_data.items():
            try:
                ts = int(ts_str)
                dt = datetime.fromtimestamp(ts, tz=KYIV_TZ)
                dt_date = dt.date()
            except Exception:
                continue

            group_data = groups.get(self.group)
            if not group_data:
                continue

            parsed = parse_group_schedule(dt_date, group_data)
            schedules.append(parsed)

        schedules.sort(key=lambda s: s["date"])
        return updated_str, schedules

    async def get_today_schedule(self) -> tuple[str, dict[str, Any] | None]:
        updated_str, schedules = await self.get_all_schedules()
        now_date = datetime.now(KYIV_TZ).date()
        for s in schedules:
            if s["date"] == now_date:
                return updated_str, s
        return updated_str, None

    async def get_tomorrow_schedule(self) -> tuple[str, dict[str, Any] | None]:
        updated_str, schedules = await self.get_all_schedules()
        tomorrow_date = datetime.now(KYIV_TZ).date() + timedelta(days=1)
        for s in schedules:
            if s["date"] == tomorrow_date:
                return updated_str, s
        return updated_str, None
