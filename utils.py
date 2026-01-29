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


TEAM_EMOJI = {
    "Армада": "🛡️",
    "Кабаны": "🐗",
}


def format_team_with_emoji(team: str) -> str:
    """Форматирует название команды с эмодзи."""
    emoji = TEAM_EMOJI.get(team, "")
    if emoji:
        return f"{team} {emoji}"
    return team


def format_player_line(player: dict) -> str:
    """Форматирует строку для игрока: Фамилия (Команда 🏆) - Статус."""
    last_name = player.get("last_name", "")
    team = player.get("team")
    status = player.get("status", "")
    
    if team:
        team_with_emoji = format_team_with_emoji(team)
        return f"{last_name} ({team_with_emoji}) - {status}"
    return f"{last_name} - {status}"


def format_status_list(title: str, items: list[dict]) -> str:
    """Форматирует список игроков с нумерацией."""
    if not items:
        return f"{title}\n—"
    numbered = "\n".join(
        f"{idx}. {format_player_line(player)}" 
        for idx, player in enumerate(items, start=1)
    )
    return f"{title}\n{numbered}"


def format_team_summary(yes_players: list[dict]) -> str:
    """Форматирует саммаризацию по командам."""
    armada_count = sum(1 for p in yes_players if p.get("team") == "Армада")
    kabany_count = sum(1 for p in yes_players if p.get("team") == "Кабаны")
    
    return f'Игроков команды "Армада 🛡️" будет на игре - {armada_count}\nИгроков команды "Кабаны 🐗" будет на игре - {kabany_count}'


def format_summary_message(target_date: date, yes: list[dict], maybe: list[dict], no: list[dict]) -> str:
    header = format_summary_header(target_date)
    block_yes = format_status_list("Я буду хоккеюги", yes)
    block_maybe = format_status_list("Пока не определился", maybe)
    block_no = format_status_list("Не смогу пойти, сорри", no)
    team_summary = format_team_summary(yes)
    return "\n\n".join([header, block_yes, block_maybe, block_no, team_summary])


def parse_notify_time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(hour=int(hours), minute=int(minutes))
