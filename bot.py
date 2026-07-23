import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ES = "@freerolls_es"
CHAT_EN = "@freerolls_en"
URL = "https://freeroll-password.com/"

SENT_FILE = Path("sent_freerolls.json")
JSON_FILE = Path("freerolls.json")
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
SITE_TZ = ZoneInfo("Europe/Moscow")


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


def get_ba_datetime(fr: dict):
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


def convert_display(date_str: str, time_str: str, lang: str = "en") -> str:
    ba = get_ba_datetime({"date": date_str, "time": time_str})
    if not ba:
        return f"{date_str} {time_str}"
    if lang == "es":
        return ba.strftime("%d.%m.%Y a las %H:%M (Buenos Aires)")
    return ba.strftime("%d.%m.%Y at %H:%M (Buenos Aires)")


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

            freerolls.append({
                "room": room,
                "name": name,
                "date": date,
                "time": time_str,
                "prize": prize,
            })
        except Exception:
            continue
    return freerolls


def save_site_json(actual: list):
    data = []
    for fr in actual:
        room_key = get_room_key(fr["room"])
        ba = get_ba_datetime(fr)
        if not ba:
            continue
        data.append({
            "room": fr["room"],
            "title": fr["name"],
            "prize": fr["prize"],
            "startsAt": ba.isoformat(),
            "registerUrl": AFFILIATE_LINKS.get(room_key, ""),
            "promoCode": PROMO_CODES.get(room_key),
        })
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Сохранён {JSON_FILE}: {len(data)} фрироллов")


def format_message(fr: dict, lang: str = "en") -> str:
    room_key = get_room_key(fr["room"])
    link = AFFILIATE_LINKS.get(room_key, "")
    promo = PROMO_CODES.get(room_key)

    if lang == "es":
        start = convert_display(fr.get("date") or "", fr.get("time") or "", "es")
        lines = [
            f"▶️ Sala: {fr['room']}",
            f"✅ Nombre: {fr['name']}",
            f"📆 Inicio: {start}",
            f"💵 Premio: {fr['prize']}",
        ]
        lines.append(f"🔑 Código: {promo}" if promo else "🔑 Código no requerido")
        lines.append("")
        lines.append(f'📎 <a href="{link}">Enlace de registro</a>' if link else "📎 Enlace de registro")
    else:
        start = convert_display(fr.get("date") or "", fr.get("time") or "", "en")
        lines = [
            f"▶️ Room: {fr['room']}",
            f"✅ Name: {fr['name']}",
            f"📆 Start: {start}",
            f"💵 Prize: {fr['prize']}",
        ]
        lines.append(f"🔑 Code: {promo}" if promo else "🔑 Code not required")
        lines.append("")
        lines.append(f'📎 <a href="{link}">Registration link</a>' if link else "📎 Registration link")

    lines.append(f"#{(fr.get('room') or '').replace(' ', '')}")
    return "\n".join(lines)


def send_one(chat_id: str, text: str, image_path) -> bool:
    if image_path and image_path.exists():
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(image_path, "rb") as photo:
            r = requests.post(url, data={
                "chat_id": chat_id,
                "caption": text,
                "parse_mode": "HTML",
            }, files={"photo": photo}, timeout=30)
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=30)

    if r.status_code == 200:
        print(f"   ✅ {chat_id}")
        return True
    print(f"   ❌ {chat_id}: {r.status_code} — {r.text[:200]}")
    return False


def send_to_telegram(fr: dict) -> bool:
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден")
        return False

    room_key = get_room_key(fr["room"])
    image_name = ROOM_IMAGES.get(room_key)
    image_path = IMAGES_DIR / image_name if image_name else None

    ok_es = send_one(CHAT_ES, format_message(fr, "es"), image_path)
    ok_en = send_one(CHAT_EN, format_message(fr, "en"), image_path)
    return ok_es or ok_en


def main():
    print(f"Запуск: {datetime.now(BA_TZ).strftime('%d.%m.%Y %H:%M')} BA")
    html = fetch_html()
    freerolls = parse_freerolls(html)
    print(f"Найдено подходящих: {len(freerolls)}")

    now_ba = datetime.now(BA_TZ)
    actual = []
    for fr in freerolls:
        ba_dt = get_ba_datetime(fr)
        if ba_dt and ba_dt >= now_ba:
            actual.append(fr)

    print(f"Актуальных: {len(actual)}")
    actual.sort(key=lambda x: get_ba_datetime(x) or datetime(2099, 1, 1, tzinfo=BA_TZ))

    # JSON для сайта
    save_site_json(actual)

    # Один пост в TG
    sent = load_sent()
    new_ones = [fr for fr in actual if make_unique_id(fr) not in sent]
    print(f"Новых для TG: {len(new_ones)}")

    if not new_ones:
        print("Нечего отправлять в TG")
        return

    fr = new_ones[0]
    print(f"Отправляю: [{fr['room']}] {fr['name']}")
    if send_to_telegram(fr):
        sent.add(make_unique_id(fr))
        save_sent(sent)
        print("Готово")


if __name__ == "__main__":
    main()
