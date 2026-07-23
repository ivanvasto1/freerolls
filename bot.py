import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# ======================
# НАСТРОЙКИ
# ======================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ES = "@freerolls_es"
CHAT_EN = "@freerolls_en"
URL = "https://freeroll-password.com/"

SENT_FILE = Path("sent_freerolls.json")
JSON_FILE = Path("freerolls.json")   # для сайта
IMAGES_DIR = Path(".")

AFFILIATE_LINKS = {
    "coinpoker": "https://record.coinpokeraffiliates.com/_FpCPzGFIZLTUOsjNOfgKeWNd7ZgqdRLk/5070/",
    "pokerking": "https://record.pokerkingpartners.com/_FuOKDuCubKDUOsjNOfgKeWNd7ZgqdRLk/5070/",
    "redstar": "https://c.rsppartners.com/clickthrgh?btag=a_13233b_963l_99",
    "888poker": "https://ic.aff-handler.com/c/48676?sr=2025702",
    "acr": "https://go.wpnaffiliates.com/visit/?bta=236862&brand=americascardroom&afp=poffES",
    "ggpoker": "https://click.ggpartners.com/?serial=10665&creative_id=14177&anid=poffES",
    "bcpoker": "https://bc.poker/a/POFFES",
    "bc poker": "https://bc.poker/a/POFFES",
    "wpt": "https://tracking.wptpartners.com/visit/?bta=3&nci=5373&afp=2047",
    "wpt global": "https://tracking.wptpartners.com/visit/?bta=3&nci=5373&afp=2047",
}

PROMO_CODES = {
    "redstar": "POFFES",
    "bcpoker": "POFFES",
    "bc poker": "POFFES",
}

ROOM_IMAGES = {
    "coinpoker": "coinpoker.jpg",
    "pokerking": "pokerking.jpg",
    "redstar": "redstar.jpg",
    "888poker": "888poker.jpg",
    "acr": "acr.jpg",
    "ggpoker": "ggpoker.jpg",
    "bcpoker": "bcpoker.jpg",
    "bc poker": "bcpoker.jpg",
    "wpt": "wpt.jpg",
    "wpt global": "wpt.jpg",
}

ALLOWED_ROOMS = {
    "coin poker", "coinpoker",
    "pokerking", "poker king",
    "redstar", "redstar poker",
    "888poker", "888 poker",
    "acr", "americas cardroom",
    "ggpoker", "gg poker",
    "bc poker", "bcpoker",
    "wpt", "wpt global",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
SITE_TZ = ZoneInfo("Europe/Moscow")  # сайт ≈ GMT+3


def get_ba_datetime(fr):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        dt = datetime.strptime((fr.get("date") or "").strip(), "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", fr.get("time") or "00:00")
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def load_sent() -> set:
    if SENT_FILE.exists():
        try:
            with open(SENT_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_sent(sent: set):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(sent)), f, ensure_ascii=False, indent=2)


def make_unique_id(fr: dict) -> str:
    return f"{fr.get('room','')}|{fr.get('name','')}|{fr.get('date','')}|{fr.get('time','')}"


def fetch_html() -> str:
    print("Загружаю страницу...")
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    print(f"Статус: {r.status_code}, размер: {len(r.text)}")
    return r.text


def parse_freerolls(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    freerolls = []

    for pass_el in soup.select(".expass2"):
        try:
            block = pass_el.find_parent("p", class_="fpexcerpt")
            if not block:
                block = pass_el.find_parent("div")

            text = block.get_text(" ", strip=True) if block else ""

            room = None
            room_match = re.search(
                r"Poker Room:\s*([^\n\r]+?)(?:Date:|Time:|Prize|$)", text
            )
            if room_match:
                room = room_match.group(1).strip()

            if not is_allowed_room(room):
                continue

            date = None
            date_el = block.select_one(".date-display-single") if block else None
            if date_el:
                date = date_el.get_text(strip=True)

            time_str = None
            time_match = re.search(
                r"Time:\s*([^\n\r]+?)(?:Prize|Name|$)", text
            )
            if time_match:
                time_str = time_match.group(1).strip()

            prize = None
            prize_match = re.search(
                r"Prize Pool:\s*([^\n\r]+?)(?:Name|ID|$)", text
            )
            if prize_match:
                prize = prize_match.group(1).strip()

            name = None
            name_match = re.search(
                r"Name:\s*([^\n\r]+?)(?:ID|Password|$)", text
            )
            if name_match:
                name = name_match.group(1).strip()

            password = pass_el.get_text(strip=True)
            if not password or password.lower() in ("not required", "not specified", "-"):
                password = None

            freerolls.append({
                "room": room,
                "name": name,
                "date": date,
                "time": time_str,
                "prize": prize,
                "password": password,
            })
        except Exception:
            continue

    return freerolls


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in link:
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in link:
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Código: {promo}")
        else:
            lines.append("🔑 Código no requerido")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
        else:
            lines.append("📎 Enlace de registro")
    else:
        start = convert_to_buenos_aires_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        if promo:
            lines.append(f"🔑 Code: {promo}")
        else:
            lines.append("🔑 Code not required")
        lines.append("")
        if link and "PLACEHOLDER" not in (link or ""):
            lines.append(f'📎 <a href="{link}">Registration link</a>')
        else:
            lines.append("📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def get_ba_datetime(fr: dict):
    """Переводит дату/время фриролла в timezone Buenos Aires."""
    try:
        date_str = (fr.get("date") or "").strip()
        time_str = fr.get("time") or "00:00"
        dt = datetime.strptime(date_str, "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str)
        hour = int(tm.group(1)) if tm else 0
        minute = int(tm.group(2)) if tm else 0
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        return dt.astimezone(BA_TZ)
    except Exception:
        return None


def convert_to_buenos_aires_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m
