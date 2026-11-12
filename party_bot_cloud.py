import html
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9158824262:AAHGsgCWsVEV_XLBFSK-S_4oe_6Pqjiuhxk")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "467567653"))
WISHLIST_URL = os.environ.get("WISHLIST_URL", "https://alisa-wishlist.onrender.com/")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://alisa-wishlist.onrender.com").rstrip("/")

MANTLE_BOT_URL = "https://mantledb.sh/v2/alisa-bday-wishlist-2026-v1/party_bot_state"
MANTLE_KEY = os.environ.get("MANTLE_KEY", "61b275b0540537928d79e56dafca4e7804e626de874012517b602c61e31cd71b")
KVDB_BOT_URL = "https://kvdb.io/HxrGi1TgiziTmfWDjiZjr1/party_bot_state"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STICKERS_DIR = os.path.join(BASE_DIR, "stickers")
LOCAL_STATE_FILE = os.path.join(BASE_DIR, "data", "party_bot_state.json")

STICKER_EMOJIS = ["🦖", "😎", "😏", "🌷", "🙌", "🥰", "😮", "🥱", "🎂", "🧐"]

DEFAULT_SETTINGS = {
    "child_name": "Аліса",
    "age": "1 рочок",
    "event_date": "21 листопада (субота)",
    "bday_note": "День народження у Аліски 17 листопада, але святкуємо ми разом 21 листопада! 🎂",
    "event_time": "з 16:30 до 17:00",
    "location_name": "с. Гора, вул. Басейна, 22 (чекаємо у нас вдома! 🏡)",
    "location_url": "https://www.google.com/maps/search/?api=1&query=%D1%81.+%D0%93%D0%BE%D1%80%D0%B0,+%D0%B2%D1%83%D0%BB.+%D0%91%D0%B0%D1%81%D0%B5%D0%B9%D0%BD%D0%B0,+22",
    "dress_code": (
        "👕 <b>Вільний та максимально зручний!</b>\n\n"
        "Одягайтеся так, щоб було комфортно:\n"
        "• танцювати та брати участь у конкурсах 💃🕺\n"
        "• смажити найсмачніший шашлик 🍢🔥\n"
        "• співати під гітару та тепло спілкуватися 🎸🥂\n"
        "• обійматися та робити круті фото з іменинницею 📸✨"
    ),
    "welcome_note": (
        "Час летить із шаленою швидкістю, і наша <b>Аліса</b> вже святкує свій <b>перший рочок життя!</b> "
        "Запрошуємо розділити цей класний день разом із нами 🫶\n\n"
        "У програмі: конкурси, співи під гітару 🎸, шашлик 🍢 і багато теплих розмов 🥂\n"
        "Обирай кнопки нижче, щоб подивитися деталі, вішліст, забрати фірмові стікери Аліси та пройти вікторину! 👇"
    ),
    "full_invitation_text": (
        "Усім привіт! 🎉\n\n"
        "Час летить із шаленою швидкістю, і наша <b>Аліса</b> вже святкує свій перший рочок життя! "
        "Запрошуємо вас розділити цей класний день разом з нами 🫶\n\n"
        "📍 <b>Деталі нашої зустрічі:</b>\n"
        "• <b>Коли:</b> 21 листопада (субота)\n"
        "• <b>Час збору:</b> чекатимемо на вас у проміжку з 16:30 до 17:00\n"
        "• <b>Де:</b> с. Гора, вул. Басейна, 22 (чекаємо у нас вдома! 🏡)\n"
        "• <b>Дрес-код:</b> вільний і зручний — для танців, конкурсів та смаження шашлику! 🍢💃\n\n"
        "У розважальну програму заплановані конкурси, співи під гітару і багато теплих розмов, "
        "тож не запізнюйтесь, щоб нічого не пропустити! 🎸🥂\n\n"
        "🎁 <b>Щодо подарунків:</b> ми вже надсилали наш вішліст кожному окремо, але якщо ви раптом ще не встигли "
        "обрати сюрприз або лінка десь загубилася, дублюємо її тут:\n"
        "👉 <a href=\"https://alisa-wishlist.onrender.com/\">Відкрити Вішліст Алісоньки</a>\n\n"
        "Беріть із собою гарний настрій та натискайте кнопки під цим повідомленням, щоб відмітитись, хто буде, "
        "забрати стікерпак Аліси та позмагатися у вікторині!\n\n"
        "Обіймаємо,\n"
        "<b>Максим, Настя та іменинниця Аліса</b> ❤️\n\n"
        "<i>P.S. Про всяк випадок уточнення: День народження у Аліски 17-го, але святкуємо ми 21-го листопада.</i>"
    ),
    "sticker_pack_name": "",
    "sticker_pack_url": "",
}

QUIZ_QUESTIONS = [
    {
        "id": 1,
        "question": "⚖️ З якою вагою народилася наша маленька красуня Аліса?",
        "options": ["3250 г", "3600 г", "4040 г", "4300 г"],
        "correct_index": 2,
        "explanation": "Точно! Аліса народилася справжньою щікатою красунею — рівно 4040 грамів! 👶💖",
    },
    {
        "id": 2,
        "question": "📏 Який ріст був у Алісоньки при народженні?",
        "options": ["49 см", "51 см", "54 см", "57 см"],
        "correct_index": 2,
        "explanation": "Правильно! Ріст при народженні — 54 см! 🌟",
    },
    {
        "id": 3,
        "question": "⏰ О котрій годині з'явилася на світ наша іменинниця?",
        "options": ["06:15", "08:58", "11:30", "15:45"],
        "correct_index": 1,
        "explanation": "Саме так! Ранкова пташка — народилася рівно о 08:58! ☀️⏰",
    },
    {
        "id": 4,
        "question": "🦷 Скільки зубчиків вже має Аліса на свій перший день народження?",
        "options": [
            "2 зубчики",
            "4 зубчики (і ще 2 прорізуються!)",
            "6 повних зубчиків",
            "8 зубчиків",
        ],
        "correct_index": 1,
        "explanation": "Вгадали! Вже є 4 зубчики і ще 2 активно прорізуються — якраз до торта й шашлику! 😁🦷",
    },
    {
        "id": 5,
        "question": "🗣 Яке найперше слово сказала Аліса?",
        "options": ["«Мама»", "«Тато»", "«Алі»", "«Дай»"],
        "correct_index": 2,
        "explanation": "Так! Справжній бос насамперед представилася — першим словом було «Алі»! 👑😍",
    },
    {
        "id": 6,
        "question": "⛪️ У якому віці ми хрестили Аліску?",
        "options": ["1 місяць", "3 місяці", "6 місяців", "9 місяців"],
        "correct_index": 1,
        "explanation": "Правильно! Хрестини відбулися, коли Алісі було 3 місяці 🤍✨",
    },
    {
        "id": 7,
        "question": "👼 Яким церковним ім'ям була охрещена Аліса?",
        "options": ["Олександра", "Алла", "Аліна", "Анна"],
        "correct_index": 1,
        "explanation": "Точно! При хрещенні Аліса отримала ім'я Алла 👼💖",
    },
]

_state_lock = threading.Lock()
_cached_state: Optional[Dict[str, Any]] = None
_last_cloud_sync = 0.0

# Group welcome debounce buffers
_welcome_lock = threading.Lock()
_welcome_buffers: Dict[int, List[str]] = {}
_welcome_timers: Dict[int, threading.Timer] = {}


def escape(text: Any) -> str:
    return html.escape(str(text or ""))


def _default_state() -> Dict[str, Any]:
    return {
        "settings": dict(DEFAULT_SETTINGS),
        "rsvp": {},          # str(user_id): {"name": str, "username": str, "status": str, "ts": float}
        "quiz_answers": {},  # str(user_id): {"name": str, "username": str, "answers": {str(q_id): {"sel": int, "ok": bool}}}
        "stickers": [],      # list of file_ids
    }


def _fetch_cloud_state() -> Optional[Dict[str, Any]]:
    for url, headers in [
        (MANTLE_BOT_URL, {"User-Agent": "AlisaPartyBot/1.0", "X-Mantle-Key": MANTLE_KEY}),
        (KVDB_BOT_URL, {"User-Agent": "AlisaPartyBot/1.0"}),
    ]:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, dict) and "settings" in data:
                        return data
        except Exception:
            pass
    return None


def _push_cloud_state_async(state_copy: Dict[str, Any]):
    def _worker():
        payload = json.dumps(state_copy, ensure_ascii=False).encode("utf-8")
        for url, headers in [
            (
                MANTLE_BOT_URL,
                {
                    "Content-Type": "application/json",
                    "X-Mantle-Key": MANTLE_KEY,
                    "User-Agent": "AlisaPartyBot/1.0",
                },
            ),
            (
                KVDB_BOT_URL,
                {
                    "Content-Type": "application/json",
                    "User-Agent": "AlisaPartyBot/1.0",
                },
            ),
        ]:
            try:
                req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=6):
                    pass
            except Exception as e:
                print(f"[BOT CLOUD WARN] Failed pushing state to {url}: {e}", flush=True)

    threading.Thread(target=_worker, daemon=True).start()


def get_state(force_sync: bool = False) -> Dict[str, Any]:
    global _cached_state, _last_cloud_sync
    with _state_lock:
        now = time.time()
        if _cached_state is None or (force_sync and now - _last_cloud_sync > 2.0):
            remote = _fetch_cloud_state()
            if remote:
                # Merge defaults so new keys in DEFAULT_SETTINGS always exist
                merged_settings = dict(DEFAULT_SETTINGS)
                merged_settings.update(remote.get("settings", {}))
                # Always keep the latest event_date/location/dress_code from DEFAULT_SETTINGS if old placeholder was there
                if "Уточнюється" in merged_settings.get("event_date", ""):
                    merged_settings["event_date"] = DEFAULT_SETTINGS["event_date"]
                    merged_settings["event_time"] = DEFAULT_SETTINGS["event_time"]
                    merged_settings["location_name"] = DEFAULT_SETTINGS["location_name"]
                    merged_settings["location_url"] = DEFAULT_SETTINGS["location_url"]
                remote["settings"] = merged_settings
                _cached_state = remote
                _last_cloud_sync = now
            elif _cached_state is None:
                if os.path.exists(LOCAL_STATE_FILE):
                    try:
                        with open(LOCAL_STATE_FILE, "r", encoding="utf-8") as f:
                            _cached_state = json.load(f)
                    except Exception:
                        _cached_state = _default_state()
                else:
                    _cached_state = _default_state()
        return _cached_state


def save_state():
    with _state_lock:
        if _cached_state is None:
            return
        state_copy = json.loads(json.dumps(_cached_state))
        try:
            os.makedirs(os.path.dirname(LOCAL_STATE_FILE), exist_ok=True)
            with open(LOCAL_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state_copy, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    _push_cloud_state_async(state_copy)


# --- Telegram HTTP API Helpers ---

def tg_api(method: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error_code": e.code, "description": err_body}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def tg_multipart(method: str, fields: Dict[str, str], files: Dict[str, Tuple[str, bytes, str]], timeout: int = 30) -> Dict[str, Any]:
    boundary = f"----AlisaBotBoundary{uuid.uuid4().hex}"
    body = bytearray()

    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{v}\r\n".encode("utf-8"))

    for field_name, (filename, file_bytes, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error_code": e.code, "description": err_body}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def ensure_sticker_pack_published(owner_id: int = ADMIN_ID) -> str:
    state = get_state()
    existing_url = state["settings"].get("sticker_pack_url", "")
    if existing_url and state.get("stickers"):
        return existing_url

    me_res = tg_api("getMe")
    if not me_res.get("ok"):
        return ""
    bot_username = me_res["result"]["username"]
    pack_name = f"alisa_1year_by_{bot_username}"
    pack_title = "Алісі 1 рочок! 🎂👑"
    pack_url = f"https://t.me/addstickers/{pack_name}"

    # Check if sticker set already exists on Telegram servers
    set_res = tg_api("getStickerSet", {"name": pack_name})
    if not set_res.get("ok"):
        # Upload all 10 .webp stickers via multipart
        stickers_meta = []
        files_map = {}
        for i in range(1, 11):
            webp_path = os.path.join(STICKERS_DIR, f"sticker_{i:02d}.webp")
            if not os.path.exists(webp_path):
                continue
            with open(webp_path, "rb") as f:
                fbytes = f.read()
            attach_key = f"file_st_{i}"
            files_map[attach_key] = (f"sticker_{i:02d}.webp", fbytes, "image/webp")
            stickers_meta.append(
                {
                    "sticker": f"attach://{attach_key}",
                    "format": "static",
                    "emoji_list": [STICKER_EMOJIS[i - 1]],
                }
            )
        if stickers_meta:
            create_res = tg_multipart(
                "createNewStickerSet",
                fields={
                    "user_id": str(owner_id),
                    "name": pack_name,
                    "title": pack_title,
                    "stickers": json.dumps(stickers_meta),
                    "sticker_type": "regular",
                },
                files=files_map,
                timeout=45,
            )
            print(f"[BOT STICKERS] createNewStickerSet result: {create_res.get('ok')} {create_res.get('description', '')}", flush=True)
            set_res = tg_api("getStickerSet", {"name": pack_name})

    if set_res.get("ok"):
        stickers_list = set_res["result"].get("stickers", [])
        file_ids = [s["file_id"] for s in stickers_list]
        state["stickers"] = file_ids
        state["settings"]["sticker_pack_name"] = pack_name
        state["settings"]["sticker_pack_url"] = pack_url
        save_state()
        return pack_url
    return ""


def send_alisa_sticker(chat_id: int, sticker_num: Optional[int] = None):
    state = get_state()
    file_ids = state.get("stickers", [])
    if file_ids:
        fid = file_ids[(sticker_num - 1) % len(file_ids)] if sticker_num else random.choice(file_ids)
        res = tg_api("sendSticker", {"chat_id": chat_id, "sticker": fid})
        if res.get("ok"):
            return

    # Fallback: upload local .webp directly
    idx = ((sticker_num - 1) % 10 + 1) if sticker_num else random.randint(1, 10)
    webp_path = os.path.join(STICKERS_DIR, f"sticker_{idx:02d}.webp")
    if os.path.exists(webp_path):
        with open(webp_path, "rb") as f:
            fbytes = f.read()
        tg_multipart(
            "sendSticker",
            fields={"chat_id": str(chat_id)},
            files={"sticker": (f"sticker_{idx:02d}.webp", fbytes, "image/webp")},
        )


# --- Keyboards & Formatting ---

def build_main_menu_kb(sticker_pack_url: str = "", is_private: bool = False) -> Dict[str, Any]:
    rows = [
        [
            {"text": "📍 Де і коли? (21.11)", "callback_data": "nav:where"},
            {"text": "👗 Дрес-код", "callback_data": "nav:dress"},
        ],
        [
            {"text": "💌 Повний текст запрошення", "callback_data": "nav:invite"},
        ],
        [
            {"text": "🎁 Вішліст Аліси (Обрати подарунок)", "url": WISHLIST_URL},
        ],
        [
            {"text": "👶 Вікторина (7 питань)", "callback_data": "quiz:view:1"},
            {"text": "🏆 Рейтинг", "callback_data": "nav:leaders"},
        ],
        [
            {"text": "✅ Хто буде? (Відмітитись)", "callback_data": "nav:rsvp"},
        ],
    ]
    if sticker_pack_url:
        rows.append([{"text": "🎨 Додати стікерпак Аліси", "url": sticker_pack_url}])
    else:
        rows.append([{"text": "🎨 Стікерпак Аліси", "callback_data": "nav:stickers"}])

    if is_private:
        rows.append(
            [
                {"text": "🛠 Тест вітання в групі", "callback_data": "admin:test_welcome"},
                {"text": "⚙️ Налаштування", "callback_data": "admin:panel"},
            ]
        )
    return {"inline_keyboard": rows}


def build_back_kb(location_url: str = "") -> Dict[str, Any]:
    rows = []
    if location_url and location_url.startswith("http"):
        rows.append([{"text": "🗺 Відкрити локацію на Google Картах", "url": location_url}])
    rows.append(
        [
            {"text": "🎁 Вішліст Аліси", "url": WISHLIST_URL},
            {"text": "👶 Вікторина", "callback_data": "quiz:view:1"},
        ]
    )
    rows.append([{"text": "⬅️ Назад у головне меню", "callback_data": "nav:main"}])
    return {"inline_keyboard": rows}


def build_rsvp_kb() -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "🥳 Обов'язково буду!", "callback_data": "rsvp:going"}],
            [{"text": "🤔 Ще уточнюю плани", "callback_data": "rsvp:maybe"}],
            [{"text": "😢 На жаль, не вийде", "callback_data": "rsvp:cant"}],
            [{"text": "⬅️ Назад у головне меню", "callback_data": "nav:main"}],
        ]
    }


def build_quiz_kb(question_id: int) -> Dict[str, Any]:
    q_obj = next((q for q in QUIZ_QUESTIONS if q["id"] == question_id), QUIZ_QUESTIONS[0])
    rows = []
    for idx, opt_text in enumerate(q_obj["options"]):
        rows.append([{"text": opt_text, "callback_data": f"quiz:ans:{q_obj['id']}:{idx}"}])

    nav_row = []
    for q in QUIZ_QUESTIONS:
        qid = q["id"]
        label = f"🔸{qid}" if qid == q_obj["id"] else f"{qid}"
        nav_row.append({"text": label, "callback_data": f"quiz:view:{qid}"})
    rows.append(nav_row)

    rows.append(
        [
            {"text": "🏆 Таблиця лідерів", "callback_data": "nav:leaders"},
            {"text": "⬅️ В меню", "callback_data": "nav:main"},
        ]
    )
    return {"inline_keyboard": rows}


def build_leaders_kb() -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "👶 Пройти вікторину", "callback_data": "quiz:view:1"}],
            [{"text": "⬅️ Назад у головне меню", "callback_data": "nav:main"}],
        ]
    }


def build_admin_kb() -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "🎉 Симулювати вхід гостя в чат", "callback_data": "admin:test_welcome"}],
            [{"text": "🎨 Перевірити всі 10 стікерів", "callback_data": "admin:send_all_stickers"}],
            [{"text": "🔄 Скинути бали вікторини", "callback_data": "admin:reset_quiz"}],
            [{"text": "⬅️ Назад у головне меню", "callback_data": "nav:main"}],
        ]
    }


def format_welcome_text(mentions: List[str], settings: Dict[str, str]) -> str:
    names_str = ", ".join(mentions)
    pack_url = settings.get("sticker_pack_url", "")
    sticker_line = (
        f"\n🎨 <b>Стікери іменинниці:</b> <a href=\"{escape(pack_url)}\">Забрати стікерпак Аліси</a>"
        if pack_url
        else ""
    )
    return (
        f"🎉 <b>Вітаємо в чаті, {names_str}!</b>\n\n"
        f"{settings.get('welcome_note', '')}\n\n"
        f"📅 <b>Коли:</b> {escape(settings.get('event_date', ''))}\n"
        f"⏰ <b>Час збору:</b> {escape(settings.get('event_time', ''))}\n"
        f"📍 <b>Де:</b> {escape(settings.get('location_name', ''))}\n"
        f"🎁 <b>Вішліст:</b> <a href=\"{WISHLIST_URL}\">Обрати подарунок для Аліси</a>"
        f"{sticker_line}\n\n"
        f"<i>P.S. {escape(settings.get('bday_note', ''))}</i>"
    )


def format_main_menu(settings: Dict[str, str], is_private: bool = False) -> str:
    txt = (
        f"🎂 <b>Перший День народження Алісоньки — 1 рочок!</b> 👑✨\n\n"
        f"{settings.get('welcome_note', '')}\n\n"
        f"📅 <b>Дата святкування:</b> {escape(settings.get('event_date', ''))}\n"
        f"⏰ <b>Час збору:</b> {escape(settings.get('event_time', ''))}\n"
        f"📍 <b>Локація:</b> {escape(settings.get('location_name', ''))}\n\n"
        f"<i>ℹ️ {escape(settings.get('bday_note', ''))}</i>\n\n"
        f"Обирай потрібний розділ у меню нижче 👇"
    )
    if is_private:
        txt += (
            "\n\n🛠 <i>Ти в особистому чаті з ботом (режим тестування). "
            "Тут можна безпечно протестувати всі кнопки, вікторину, стікери та вітання нових гостей!</i>"
        )
    return txt


def format_where_when(settings: Dict[str, str]) -> str:
    loc_url = settings.get("location_url", "").strip()
    loc_line = f"📍 <b>Де:</b> {escape(settings.get('location_name', ''))}"
    if loc_url:
        loc_line += f"\n🗺 <a href=\"{escape(loc_url)}\">Відкрити точку на Google Картах</a>"

    return (
        f"📍 <b>Деталі нашої зустрічі на 1 рочок Аліси:</b>\n\n"
        f"📅 <b>Коли:</b> {escape(settings.get('event_date', ''))}\n"
        f"⏰ <b>Час збору:</b> чекатимемо на вас у проміжку <b>{escape(settings.get('event_time', ''))}</b>\n"
        f"{loc_line}\n\n"
        f"🎸 <b>Що у програмі:</b>\n"
        f"Заплановані веселі конкурси, співи під гітару, смаження шашлику і багато теплих розмов — "
        f"тож не запізнюйтесь, щоб нічого не пропустити! 🥂✨\n\n"
        f"<i>P.S. Про всяк випадок уточнення: День народження у Аліски 17-го, але святкуємо ми 21-го листопада! 🎂</i>\n\n"
        f"Обіймаємо,\n<b>Максим, Настя та іменинниця Аліса</b> 🫶"
    )


def format_rsvp(state: Dict[str, Any]) -> str:
    rsvp_map = state.get("rsvp", {})
    going, maybe, cant = [], [], []
    for uid, info in rsvp_map.items():
        st = info.get("status")
        entry = (info.get("name", "Гість"), info.get("username", ""))
        if st == "going":
            going.append(entry)
        elif st == "maybe":
            maybe.append(entry)
        elif st == "cant":
            cant.append(entry)

    lines = [
        "✅ <b>Хто буде на святкуванні 21 листопада?</b>\n",
        "Дайте знати кнопкою нижче, чи зможете бути, щоб ми знали, на скількох гостей готувати шашлик та святковий торт! 🎂🍢\n",
        f"🥳 <b>Обов'язково будуть ({len(going)}):</b>",
    ]
    if going:
        for i, (name, uname) in enumerate(going, 1):
            u_str = f" (@{escape(uname)})" if uname else ""
            lines.append(f"  {i}. {escape(name)}{u_str}")
    else:
        lines.append("  <i>Поки ніхто не відмітився — будь першим!</i>")

    if maybe:
        lines.append(f"\n🤔 <b>Ще уточнюють ({len(maybe)}):</b>")
        for name, _ in maybe:
            lines.append(f"  • {escape(name)}")

    if cant:
        lines.append(f"\n😢 <b>Не зможуть ({len(cant)}):</b>")
        for name, _ in cant:
            lines.append(f"  • {escape(name)}")

    return "\n".join(lines)


def format_leaderboard(state: Dict[str, Any]) -> str:
    q_map = state.get("quiz_answers", {})
    total_q = len(QUIZ_QUESTIONS)
    leaders = []
    for uid, udata in q_map.items():
        ans = udata.get("answers", {})
        if not ans:
            continue
        score = sum(1 for v in ans.values() if v.get("ok"))
        answered = len(ans)
        leaders.append((udata.get("name", "Гість"), score, answered))

    leaders.sort(key=lambda x: (-x[1], x[2]))
    lines = ["🏆 <b>Рейтинг головних знавців іменинниці Аліси:</b>\n"]
    if not leaders:
        lines.append("<i>Ще ніхто не відповів на питання вікторини. Натискай «👶 Пройти вікторину» та очолюй список!</i>")
    else:
        medals = ["🥇", "🥈", "🥉"]
        for idx, (name, score, answered) in enumerate(leaders[:15]):
            medal = medals[idx] if idx < 3 else f"<b>{idx + 1}.</b>"
            lines.append(f"{medal} <b>{escape(name)}</b> — {score} із {total_q} балів (відповідей: {answered}/{total_q})")

    lines.append("\n💡 <i>Переможця привітаємо особисто на святі 21 листопада! 🥂</i>")
    return "\n".join(lines)


# --- Update Processing ---

def _flush_welcome_group(chat_id: int):
    with _welcome_lock:
        mentions = _welcome_buffers.pop(chat_id, [])
        _welcome_timers.pop(chat_id, None)
    if not mentions:
        return
    unique_mentions = list(dict.fromkeys(mentions))
    state = get_state()
    settings = state["settings"]
    text = format_welcome_text(unique_mentions, settings)
    kb = build_main_menu_kb(settings.get("sticker_pack_url", ""), is_private=False)
    send_alisa_sticker(chat_id)
    tg_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": kb,
            "disable_web_page_preview": True,
        },
    )


def handle_update(update: Dict[str, Any]):
    try:
        if "message" in update:
            _handle_message(update["message"])
        elif "callback_query" in update:
            _handle_callback(update["callback_query"])
    except Exception as e:
        print(f"[BOT ERROR] handle_update exception: {e}", flush=True)


def _handle_message(msg: Dict[str, Any]):
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    chat_type = chat.get("type", "private")
    is_private = chat_type == "private"
    from_user = msg.get("from", {})
    user_id = from_user.get("id", ADMIN_ID)

    # 1. Check new_chat_members
    new_members = msg.get("new_chat_members", [])
    if new_members:
        mentions = []
        for u in new_members:
            if u.get("is_bot"):
                continue
            fname = escape(u.get("first_name") or "Гість")
            mentions.append(f'<a href="tg://user?id={u.get("id")}">{fname}</a>')
        if mentions:
            with _welcome_lock:
                _welcome_buffers.setdefault(chat_id, []).extend(mentions)
                if chat_id not in _welcome_timers:
                    t = threading.Timer(1.5, _flush_welcome_group, args=[chat_id])
                    t.daemon = True
                    _welcome_timers[chat_id] = t
                    t.start()
        return

    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return

    cmd_parts = text.split(maxsplit=1)
    cmd = cmd_parts[0].split("@")[0].lower()
    arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

    state = get_state(force_sync=True)
    settings = state["settings"]

    # Auto-ensure sticker pack on /start
    if is_private and not settings.get("sticker_pack_url"):
        try:
            pack_url = ensure_sticker_pack_published(user_id)
            if pack_url:
                settings["sticker_pack_url"] = pack_url
        except Exception as e:
            print(f"[BOT WARN] Sticker pack publish skipped: {e}", flush=True)

    if cmd in ("/start", "/menu"):
        reply_text = format_main_menu(settings, is_private=is_private)
        kb = build_main_menu_kb(settings.get("sticker_pack_url", ""), is_private=is_private)
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": reply_text,
                "parse_mode": "HTML",
                "reply_markup": kb,
                "disable_web_page_preview": True,
            },
        )
    elif cmd == "/invite":
        kb = build_main_menu_kb(settings.get("sticker_pack_url", ""), is_private=False)
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": settings.get("full_invitation_text", ""),
                "parse_mode": "HTML",
                "reply_markup": kb,
                "disable_web_page_preview": True,
            },
        )
    elif cmd == "/test_welcome":
        fname = escape(from_user.get("first_name") or "Гість")
        mention = f'<a href="tg://user?id={user_id}">{fname}</a>'
        w_text = format_welcome_text([mention], settings)
        kb = build_main_menu_kb(settings.get("sticker_pack_url", ""), is_private=False)
        send_alisa_sticker(chat_id)
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": w_text,
                "parse_mode": "HTML",
                "reply_markup": kb,
                "disable_web_page_preview": True,
            },
        )
    elif cmd == "/stickers":
        pack_url = settings.get("sticker_pack_url") or ensure_sticker_pack_published(user_id)
        send_alisa_sticker(chat_id)
        msg_txt = (
            f"🎨 <b>Фірмовий стікерпак іменинниці Аліси!</b>\n\n👉 <a href=\"{escape(pack_url)}\">Додати всі 10 стікерів у Telegram</a>"
            if pack_url
            else "🎨 Ось один із наших фірмових стікерів Аліси!"
        )
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": msg_txt,
                "parse_mode": "HTML",
                "reply_markup": build_main_menu_kb(pack_url, is_private=is_private),
            },
        )
    elif cmd == "/set_date" and arg:
        settings["event_date"] = arg
        save_state()
        tg_api("sendMessage", {"chat_id": chat_id, "text": f"✅ Дату оновлено: <b>{escape(arg)}</b>", "parse_mode": "HTML"})
    elif cmd == "/set_time" and arg:
        settings["event_time"] = arg
        save_state()
        tg_api("sendMessage", {"chat_id": chat_id, "text": f"✅ Час оновлено: <b>{escape(arg)}</b>", "parse_mode": "HTML"})
    elif cmd == "/set_location" and arg:
        settings["location_name"] = arg
        save_state()
        tg_api("sendMessage", {"chat_id": chat_id, "text": f"✅ Локацію оновлено: <b>{escape(arg)}</b>", "parse_mode": "HTML"})
    elif cmd == "/reset_quiz":
        state["quiz_answers"] = {}
        save_state()
        tg_api("sendMessage", {"chat_id": chat_id, "text": "🔄 Усі тестові бали вікторини очищено!", "parse_mode": "HTML"})


def _safe_edit(chat_id: int, message_id: int, text: str, reply_markup: Dict[str, Any]):
    res = tg_api(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
            "disable_web_page_preview": True,
        },
    )
    if not res.get("ok") and "message is not modified" not in str(res.get("description", "")).lower():
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
                "disable_web_page_preview": True,
            },
        )


def _handle_callback(cb: Dict[str, Any]):
    cb_id = cb.get("id")
    data = cb.get("data", "")
    msg = cb.get("message", {})
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    message_id = msg.get("message_id")
    is_private = chat.get("type") == "private"
    user = cb.get("from", {})
    user_id = str(user.get("id", ""))
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Гість"
    username = user.get("username", "")

    state = get_state()
    settings = state["settings"]

    if data == "nav:main":
        _safe_edit(
            chat_id,
            message_id,
            format_main_menu(settings, is_private=is_private),
            build_main_menu_kb(settings.get("sticker_pack_url", ""), is_private=is_private),
        )
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data == "nav:where":
        _safe_edit(
            chat_id,
            message_id,
            format_where_when(settings),
            build_back_kb(settings.get("location_url", "")),
        )
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data == "nav:dress":
        _safe_edit(
            chat_id,
            message_id,
            f"👗 <b>Дрес-код та атмосфера свята:</b>\n\n{settings.get('dress_code', '')}",
            build_back_kb(),
        )
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data == "nav:invite":
        _safe_edit(
            chat_id,
            message_id,
            settings.get("full_invitation_text", ""),
            build_back_kb(settings.get("location_url", "")),
        )
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data == "nav:rsvp":
        _safe_edit(chat_id, message_id, format_rsvp(state), build_rsvp_kb())
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data.startswith("rsvp:"):
        status = data.split(":")[1]
        state.setdefault("rsvp", {})[user_id] = {
            "name": full_name,
            "username": username,
            "status": status,
            "ts": time.time(),
        }
        save_state()
        _safe_edit(chat_id, message_id, format_rsvp(state), build_rsvp_kb())
        toast = {
            "going": "🥳 Ура! Записали тебе до списку гостей!",
            "maybe": "🤔 Добре! Сподіваємось, усе вийде!",
            "cant": "😢 Дуже шкода! Дякуємо, що попередив(ла)!",
        }.get(status, "✅ Збережено!")
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": toast})

    elif data == "nav:stickers":
        pack_url = settings.get("sticker_pack_url") or ensure_sticker_pack_published(int(user_id or ADMIN_ID))
        send_alisa_sticker(chat_id)
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Надсилаю стікер Аліси! 🎨"})

    elif data.startswith("quiz:view:"):
        qid = int(data.split(":")[2])
        q_obj = next((q for q in QUIZ_QUESTIONS if q["id"] == qid), QUIZ_QUESTIONS[0])
        txt = (
            f"👶 <b>Святкова вікторина про Алісу!</b> (Питання {q_obj['id']} із {len(QUIZ_QUESTIONS)})\n\n"
            f"❓ <b>{q_obj['question']}</b>\n\n"
            f"<i>Обирай правильний варіант нижче! Кожен гість заробляє власні бали в загальний рейтинг 🏆</i>"
        )
        _safe_edit(chat_id, message_id, txt, build_quiz_kb(q_obj["id"]))
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data.startswith("quiz:ans:"):
        parts = data.split(":")
        qid = int(parts[2])
        sel_idx = int(parts[3])
        q_obj = next((q for q in QUIZ_QUESTIONS if q["id"] == qid), QUIZ_QUESTIONS[0])
        is_ok = sel_idx == q_obj["correct_index"]

        u_quiz = state.setdefault("quiz_answers", {}).setdefault(
            user_id, {"name": full_name, "username": username, "answers": {}}
        )
        u_quiz["name"] = full_name
        u_quiz["username"] = username
        ans_map = u_quiz.setdefault("answers", {})

        if str(qid) in ans_map:
            prev_ok = ans_map[str(qid)].get("ok")
            prefix = "✅ Ти вже відповідав(ла) правильно!" if prev_ok else "ℹ️ Ти вже відповідав(ла) на це питання!"
            alert_text = f"{prefix}\n\n💡 {q_obj['explanation']}"
        else:
            ans_map[str(qid)] = {"sel": sel_idx, "ok": is_ok}
            save_state()
            if is_ok:
                alert_text = f"🎉 Правильно! (+1 бал)\n\n{q_obj['explanation']}"
            else:
                corr_txt = q_obj["options"][q_obj["correct_index"]]
                alert_text = f"🙈 Майже!\nПравильна відповідь: {corr_txt}\n\n{q_obj['explanation']}"

        tg_api(
            "answerCallbackQuery",
            {"callback_query_id": cb_id, "text": alert_text[:200], "show_alert": True},
        )

        next_qid = qid + 1
        if any(q["id"] == next_qid for q in QUIZ_QUESTIONS):
            nq = next(q for q in QUIZ_QUESTIONS if q["id"] == next_qid)
            txt = (
                f"👶 <b>Святкова вікторина про Алісу!</b> (Питання {nq['id']} із {len(QUIZ_QUESTIONS)})\n\n"
                f"❓ <b>{nq['question']}</b>\n\n"
                f"<i>Обирай правильний варіант нижче! Кожен гість заробляє власні бали в загальний рейтинг 🏆</i>"
            )
            _safe_edit(chat_id, message_id, txt, build_quiz_kb(next_qid))
        else:
            _safe_edit(chat_id, message_id, format_leaderboard(state), build_leaders_kb())

    elif data == "nav:leaders":
        _safe_edit(chat_id, message_id, format_leaderboard(state), build_leaders_kb())
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data == "admin:panel":
        txt = (
            "⚙️ <b>Панель організатора (Хмарний режим 24/7)</b>\n\n"
            f"📅 <b>Дата:</b> {escape(settings.get('event_date', ''))}\n"
            f"⏰ <b>Час:</b> {escape(settings.get('event_time', ''))}\n"
            f"📍 <b>Локація:</b> {escape(settings.get('location_name', ''))}\n\n"
            "<b>Швидкі команди для зміни тексту в будь-який момент:</b>\n"
            "• <code>/set_date 21 листопада (субота)</code>\n"
            "• <code>/set_time з 16:30 до 17:00</code>\n"
            "• <code>/set_location с. Гора, вул. Басейна, 22</code>\n"
            "• <code>/reset_quiz</code> — очистити бали вікторини перед запуском"
        )
        _safe_edit(chat_id, message_id, txt, build_admin_kb())
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id})

    elif data == "admin:test_welcome":
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Симулюю вхід гостя в групу! 🎉"})
        mention = f'<a href="tg://user?id={user_id}">{escape(user.get("first_name", "Гість"))}</a>'
        w_text = format_welcome_text([mention], settings)
        kb = build_main_menu_kb(settings.get("sticker_pack_url", ""), is_private=False)
        send_alisa_sticker(chat_id)
        tg_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": w_text,
                "parse_mode": "HTML",
                "reply_markup": kb,
                "disable_web_page_preview": True,
            },
        )

    elif data == "admin:send_all_stickers":
        tg_api("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Надсилаю всі 10 стікерів Аліси! 🎨"})
        for i in range(1, 11):
            send_alisa_sticker(chat_id, sticker_num=i)
            time.sleep(0.2)

    elif data == "admin:reset_quiz":
        state["quiz_answers"] = {}
        save_state()
        tg_api(
            "answerCallbackQuery",
            {"callback_query_id": cb_id, "text": "✅ Таблицю лідерів вікторини очищено!", "show_alert": True},
        )


def start_cloud_bot_services():
    """
    Initializes sticker pack, sets up Telegram Webhook on Render (or polling locally),
    and starts the 24/7 keep-alive worker so Render never sleeps.
    """
    def _init_and_keepalive():
        time.sleep(2)
        print("[PARTY BOT] Initializing Alisa 1st Birthday Bot...", flush=True)
        get_state(force_sync=True)
        try:
            pack_url = ensure_sticker_pack_published(ADMIN_ID)
            if pack_url:
                print(f"[PARTY BOT] Official Sticker Pack ready: {pack_url}", flush=True)
        except Exception as e:
            print(f"[PARTY BOT] Sticker pack init note: {e}", flush=True)

        is_render = bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"))
        if is_render:
            webhook_url = f"{RENDER_URL}/api/telegram-webhook"
            res = tg_api(
                "setWebhook",
                {
                    "url": webhook_url,
                    "allowed_updates": ["message", "callback_query", "chat_member"],
                    "drop_pending_updates": False,
                },
            )
            print(f"[PARTY BOT] Registered 24/7 Cloud Webhook at {webhook_url}: {res}", flush=True)
            # Keep-alive self-ping every 8 minutes so Render instance stays warm 24/7
            while True:
                time.sleep(480)
                try:
                    req = urllib.request.Request(
                        f"{RENDER_URL}/api/gifts",
                        headers={"User-Agent": "AlisaKeepAlive/1.0"},
                    )
                    with urllib.request.urlopen(req, timeout=10):
                        pass
                except Exception:
                    pass
        else:
            # Local polling mode (first remove webhook so polling works)
            tg_api("deleteWebhook", {"drop_pending_updates": False})
            print("[PARTY BOT] Running in local polling mode...", flush=True)
            offset = 0
            while True:
                try:
                    res = tg_api(
                        "getUpdates",
                        {
                            "offset": offset,
                            "timeout": 25,
                            "allowed_updates": ["message", "callback_query", "chat_member"],
                        },
                        timeout=35,
                    )
                    if res.get("ok"):
                        for upd in res.get("result", []):
                            offset = upd["update_id"] + 1
                            handle_update(upd)
                    else:
                        time.sleep(3)
                except Exception as e:
                    print(f"[PARTY BOT] Polling retry: {e}", flush=True)
                    time.sleep(3)

    threading.Thread(target=_init_and_keepalive, daemon=True).start()
