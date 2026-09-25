"""Проверяет floor price коллекции на OpenSea и шлёт изменение в Telegram."""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SLUG = os.environ.get("COLLECTION_SLUG", "proof-of-narnian-nft-og")
STATE = Path(__file__).with_name("state.json")
# Минимальное изменение в процентах, ниже которого не беспокоим. 0 — любое.
MIN_CHANGE_PCT = float(os.environ.get("MIN_CHANGE_PCT") or 0)


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "floor-watch", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_floor():
    headers = {"accept": "application/json"}
    if os.environ.get("OPENSEA_API_KEY"):
        headers["x-api-key"] = os.environ["OPENSEA_API_KEY"]
    total = get_json(f"https://api.opensea.io/api/v2/collections/{SLUG}/stats", headers)["total"]
    return total["floor_price"], total.get("floor_price_symbol") or "ETH"


def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    data = urllib.parse.urlencode({
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "disable_web_page_preview": "true",
    }).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=30)


def main():
    floor, symbol = fetch_floor()
    prev = json.loads(STATE.read_text())["floor"] if STATE.exists() else None
    print(f"floor={floor} {symbol}, prev={prev}")

    if floor == prev:
        return
    if prev and floor and abs(floor - prev) / prev * 100 < MIN_CHANGE_PCT:
        print("изменение ниже порога, не шлём")
        return

    link = f"https://opensea.io/collection/{SLUG}"
    if floor is None:
        text = f"{SLUG}: floor пропал (нет листингов)\n{link}"
    elif prev is None:
        text = f"{SLUG}: мониторинг запущен\nFloor: {floor:g} {symbol}\n{link}"
    else:
        pct = (floor - prev) / prev * 100
        arrow = "вверх" if floor > prev else "вниз"
        text = (f"{SLUG}: floor {arrow} {pct:+.2f}%\n"
                f"Сейчас: {floor:g} {symbol}\nБыло: {prev:g} {symbol}\n{link}")

    if "--dry-run" in sys.argv:
        print(text)
        return
    send_telegram(text)
    STATE.write_text(json.dumps({"floor": floor, "symbol": symbol}) + "\n")


if __name__ == "__main__":
    main()
