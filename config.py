import os
import time

from dotenv import load_dotenv


load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


BOT_TOKEN = _require_env("BOT_TOKEN")
CHAT_ID = int(_require_env("CHAT_ID"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
if "TZ" not in os.environ:
    os.environ["TZ"] = TIMEZONE
    try:
        time.tzset()
    except AttributeError:
        pass
NOTIFY_TIME = os.getenv("NOTIFY_TIME", "11:00")
_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {
    int(value)
    for value in _admin_raw.replace(",", " ").split()
    if value.strip().isdigit()
}
