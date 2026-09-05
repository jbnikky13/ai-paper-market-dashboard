import os
import time
import requests
from ng_ipo_scanner import scan, telegram_text


def send_telegram(messages, max_attempts=5):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel = os.getenv("TELEGRAM_CHANNEL_ID", "")
    if not token or not channel:
        return False, "Telegram secrets missing"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for index, message in enumerate(messages):
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                response = requests.post(
                    url,
                    json={
                        "chat_id": channel,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=30,
                )
            except requests.RequestException as exc:
                if attempt >= max_attempts:
                    return False, f"Telegram request failed: {exc}"
                time.sleep(min(5 * attempt, 20))
                continue

            if response.ok:
                # Telegram applies per-chat/per-bot message rate limits. Keep a
                # small gap between alerts so a large IPO discovery batch does
                # not trigger a 429.
                if index < len(messages) - 1:
                    time.sleep(1.2)
                break

            if response.status_code == 429:
                try:
                    retry_after = int(response.json().get("parameters", {}).get("retry_after", 10))
                except (ValueError, TypeError):
                    retry_after = 10
                if attempt >= max_attempts:
                    return False, f"Telegram rate limit persisted after {max_attempts} attempts"
                time.sleep(max(retry_after, 1) + 1)
                continue

            if 500 <= response.status_code < 600 and attempt < max_attempts:
                time.sleep(min(5 * attempt, 20))
                continue

            return False, response.text[:500]

    return True, "sent"


def main():
    fresh = scan()
    if not fresh:
        print("No new Nigeria SEC/NGX public-offer signal.")
        return

    ok, msg = send_telegram([telegram_text(x) for x in fresh])
    if not ok:
        raise SystemExit(msg)
    print(f"Sent {len(fresh)} Nigeria capital-market alert(s).")


if __name__ == "__main__":
    main()
