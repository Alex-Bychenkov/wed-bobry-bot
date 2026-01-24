from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


STATUS_YES = "YES"
STATUS_MAYBE = "MAYBE"
STATUS_NO = "NO"
ALL_STATUSES = (STATUS_YES, STATUS_MAYBE, STATUS_NO)


@dataclass(frozen=True)
class WeekSession:
    target_date: date
    close_time: time


def get_now(tz_name: str) -> datetime:
    return datetime.now(tz=ZoneInfo(tz_name))


def next_wednesday(now: datetime) -> date:
    weekday = now.weekday()
    target_weekday = 2  # Wednesday
    days_ahead = (target_weekday - weekday) % 7
    if weekday == target_weekday and now.time() >= time(hour=23, minute=30):
        days_ahead = 7
    return (now.date() + timedelta(days=days_ahead))


def session_close_dt(target_date: date, tz_name: str) -> datetime:
    return datetime.combine(target_date, time(hour=23, minute=30), tzinfo=ZoneInfo(tz_name))


def format_summary_header(target_date: date) -> str:
    return f"Среда бобры 🦫 {target_date.isoformat()} 20:30 ❗️❗️❗️❗️❗️❗️"


def format_status_list(title: str, items: list[str]) -> str:
    if not items:
        return f"{title}\n—"
    numbered = "\n".join(f"{idx}. {value}" for idx, value in enumerate(items, start=1))
    return f"{title}\n{numbered}"


def format_summary_message(target_date: date, yes: list[str], maybe: list[str], no: list[str]) -> str:
    header = format_summary_header(target_date)
    block_yes = format_status_list("Я буду хоккеюги", yes)
    block_maybe = format_status_list("Пока не определился", maybe)
    block_no = format_status_list("Не смогу пойти, сорри", no)
    return "\n\n".join([header, block_yes, block_maybe, block_no])


def parse_notify_time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(hour=int(hours), minute=int(minutes))
