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
CHAT_ID = "@freerolls_es"
URL = "https://freeroll-password.com/"

SENT_FILE = Path("sent_freerolls.json")
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
    "wpt": "https://PLACEHOLDER_WPT",
    "wpt global": "https://PLACEHOLDER_WPT",
}

# Ваши промокоды (где есть)
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
SITE_TZ = ZoneInfo("Europe/Moscow")

# ======================
# ФУНКЦИИ
# ======================

def normalize_room(room: str) -> str:
    return (room or "").lower().strip()

def is_allowed_room(room: str) -> bool:
    r = normalize_room(room)
    for allowed in ALLOWED_ROOMS:
        if allowed in r or r in allowed:
            return True
    return False

def get_room_key(room: str) -> str:
    r = normalize_room(room)
    if "coin" in r:
        return "coinpoker"
    if "king" in r:
        return "pokerking"
    if "redstar" in r or "red star" in r:
        return "redstar"
    if "888" in r:
        return "888poker"
    if "acr" in r or "americas" in r:
        return "acr"
    if "gg" in r:
        return "ggpoker"
    if "bc" in r:
        return "bcpoker"
    if "wpt" in r:
        return "wpt"
    return r

def load_sent() -> set:
    if SENT_FILE.exists():
        with open(SENT_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_sent(sent: set):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(sent)), f, ensure_ascii=False, indent=2)

def make_unique_id(fr: dict) -> str:
    return f"{fr.get('room','')}|{fr.get('name','')}|{fr.get('date','')}|{fr.get('time','')}|{fr.get('password','')}"

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
            block = pass_el.find_parent("p", class_="fpexcerpt") or pass_el.find_parent("div")
            text = block.get_text(" ", strip=True) if block else ""

            room = None
            m = re.search(r"Poker Room:\s*([^\n\r]+?)(?:Date:|Time:|Prize|$)", text)
            if m:
                room = m.group(1).strip()
            if not is_allowed_room(room):
                continue

            date = None
            date_el = block.select_one(".date-display-single") if block else None
            if date_el:
                date = date_el.get_text(strip=True)

            time_str = None
            m = re.search(r"Time:\s*([^\n\r]+?)(?:Prize|Name|$)", text)
            if m:
                time_str = m.group(1).strip()

            prize = None
            m = re.search(r"Prize Pool:\s*([^\n\r]+?)(?:Name|ID|$)", text)
            if m:
                prize = m.group(1).strip()

            name = None
            m = re.search(r"Name:\s*([^\n\r]+?)(?:ID|Password|$)", text)
            if m:
                name = m.group(1).strip()

            password = pass_el.get_text(strip=True)
            if password.lower() in ("not required", "not specified", "-", ""):
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

def convert_to_buenos_aires(date_str: str, time_str: str) -> str:
    try:
        dt = datetime.strptime(date_str.strip(), "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", time_str or "")
        if not tm:
            return dt.strftime("%d.%m.%Y")
        hour, minute = int(tm.group(1)), int(tm.group(2))
        dt = dt.replace(hour=hour, minute=minute, tzinfo=SITE_TZ)
        ba = dt.astimezone(BA_TZ)
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    except Exception:
        return f"{date_str} {time_str}"

def sort_key(fr):
    try:
        dt = datetime.strptime(fr.get("date") or "January 1, 2099", "%B %d, %Y")
        tm = re.search(r"(\d{1,2}):(\d{2})", fr.get("time") or "23:59")
        hour = int(tm.group(1)) if tm else 23
        minute = int(tm.group(2)) if tm else 59
        return (dt, hour, minute)
    except Exception:
        return (datetime(2099, 1, 1), 23, 59)

def format_message(fr: dict) -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)
    start = convert_to_buenos_aires(fr.get("date") or "", fr.get("time") or "")

    lines = [
        f"▶️ Sala: {fr['room']}",
        f"✅ Nombre: {fr['name']}",
        f"📆 Inicio: {start}",
        f"💵 Premio: {fr['prize']}",
    ]

    # Только наш код, либо "не требуется"
    if promo:
        lines.append(f"🔑 Código: {promo}")
    else:
        lines.append("🔑 Código no requerido")

    lines.append("")

    if link and "PLACEHOLDER" not in link:
        lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
    else:
        lines.append("📎 Enlace de registro")

    lines.append(f"#{fr['room'].replace(' ', '')}")
    return "\n".join(lines)

    # Ссылка (HTML — лучше кликается в Telegram)
    if link and "PLACEHOLDER" not in link:
        lines.append(f'📎 <a href="{link}">Enlace de registro</a>')
    else:
        lines.append("📎 Enlace de registro")

    lines.append(f"#{fr['room'].replace(' ', '')}")
    return "\n".join(lines)

def send_to_telegram(fr: dict) -> bool:
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден")
        return False

    room_key = get_room_key(fr["room"])
    image_name = ROOM_IMAGES.get(room_key)
    image_path = IMAGES_DIR / image_name if image_name else None
    text = format_message(fr)

    if image_path and image_path.exists():
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(image_path, "rb") as photo:
            r = requests.post(url, data={
                "chat_id": CHAT_ID,
                "caption": text,
                "parse_mode": "HTML",
            }, files={"photo": photo}, timeout=30)
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=30)

    if r.status_code == 200:
        print(f"✅ Отправлено: [{fr['room']}] {fr['name']}")
        return True
    print(f"❌ Ошибка Telegram: {r.status_code} — {r.text[:300]}")
    return False

def main():
    print(f"Запуск: {datetime.now(BA_TZ).strftime('%d.%m.%Y %H:%M')} BA")
    html = fetch_html()
    freerolls = parse_freerolls(html)
    print(f"Найдено подходящих: {len(freerolls)}")

    # Сегодня по Buenos Aires (без времени)
    today = datetime.now(BA_TZ).date()

    def is_future_or_today(fr):
        try:
            dt = datetime.strptime(fr.get("date") or "January 1, 2000", "%B %d, %Y").date()
            return dt >= today
        except Exception:
            return False

    # Только сегодня и будущее
    freerolls = [fr for fr in freerolls if is_future_or_today(fr)]
    print(f"Актуальных (сегодня+): {len(freerolls)}")

    sent = load_sent()
    new_ones = [fr for fr in freerolls if make_unique_id(fr) not in sent]
    new_ones.sort(key=sort_key)
    print(f"Новых: {len(new_ones)}")

    if not new_ones:
        print("Нечего отправлять")
        return

    fr = new_ones[0]
    if send_to_telegram(fr):
        sent.add(make_unique_id(fr))
        save_sent(sent)
        print("Готово")
