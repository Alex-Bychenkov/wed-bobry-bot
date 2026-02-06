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

GOALIE_EMOJI = "🥅"


def format_team_with_emoji(team: str) -> str:
    """Форматирует название команды с эмодзи."""
    emoji = TEAM_EMOJI.get(team, "")
    if emoji:
        return f"{team} {emoji}"
    return team


def format_player_line(player) -> str:
    """Форматирует строку для игрока: Фамилия (Команда 🏆) - Статус [- ВРАТАРЬ 🥅]."""
    last_name = player.last_name if hasattr(player, 'last_name') else player.get("last_name", "")
    team = player.team if hasattr(player, 'team') else player.get("team")
    status = player.status if hasattr(player, 'status') else player.get("status", "")
    is_goalie = player.is_goalie if hasattr(player, 'is_goalie') else player.get("is_goalie", False)
    
    goalie_suffix = f" - ВРАТАРЬ {GOALIE_EMOJI}" if is_goalie else ""
    
    if team:
        team_with_emoji = format_team_with_emoji(team)
        return f"{last_name} ({team_with_emoji}) - {status}{goalie_suffix}"
    return f"{last_name} - {status}{goalie_suffix}"


def format_status_list(title: str, items: list, exclude_goalies: bool = False) -> str:
    """Форматирует список игроков с нумерацией.
    
    Args:
        title: Заголовок списка
        items: Список игроков
        exclude_goalies: Если True, вратари не включаются в список
    """
    # Фильтруем вратарей если нужно
    if exclude_goalies:
        items = [p for p in items if not (p.is_goalie if hasattr(p, 'is_goalie') else p.get("is_goalie", False))]
    
    if not items:
        return f"{title}\n—"
    numbered = "\n".join(
        f"{idx}. {format_player_line(player)}" 
        for idx, player in enumerate(items, start=1)
    )
    return f"{title}\n{numbered}"


def format_team_summary(yes_players: list) -> str:
    """Форматирует саммаризацию по командам (без учета вратарей)."""
    # Исключаем вратарей из подсчета
    non_goalie_players = [p for p in yes_players if not (p.is_goalie if hasattr(p, 'is_goalie') else p.get("is_goalie", False))]
    
    armada_count = sum(1 for p in non_goalie_players if (p.team if hasattr(p, 'team') else p.get("team")) == "Армада")
    kabany_count = sum(1 for p in non_goalie_players if (p.team if hasattr(p, 'team') else p.get("team")) == "Кабаны")
    
    return f'Игроков команды "Армада 🛡️" будет на игре - {armada_count}\nИгроков команды "Кабаны 🐗" будет на игре - {kabany_count}'


def format_goalies_list(yes_players: list) -> str:
    """Форматирует список вратарей из игроков со статусом YES."""
    goalies = [p for p in yes_players if (p.is_goalie if hasattr(p, 'is_goalie') else p.get("is_goalie", False))]
    
    if not goalies:
        return f"Вратари {GOALIE_EMOJI}:\n—"
    
    lines = []
    for idx, goalie in enumerate(goalies, start=1):
        last_name = goalie.last_name if hasattr(goalie, 'last_name') else goalie.get("last_name", "")
        team = goalie.team if hasattr(goalie, 'team') else goalie.get("team")
        if team:
            team_with_emoji = format_team_with_emoji(team)
            lines.append(f"{idx}. {last_name} ({team_with_emoji})")
        else:
            lines.append(f"{idx}. {last_name}")
    
    return f"Вратари {GOALIE_EMOJI}:\n" + "\n".join(lines)


def format_summary_message(target_date: date, yes: list, maybe: list, no: list) -> str:
    header = format_summary_header(target_date)
    block_yes = format_status_list("Я буду хоккеюги", yes, exclude_goalies=True)
    block_maybe = format_status_list("Пока не определился", maybe)
    block_no = format_status_list("Не смогу пойти, сорри", no)
    team_summary = format_team_summary(yes)
    goalies_list = format_goalies_list(yes)
    return "\n\n".join([header, block_yes, block_maybe, block_no, team_summary, goalies_list])


def parse_notify_time(value: str) -> time:
    hours, minutes = value.split(":")
    return time(hour=int(hours), minute=int(minutes))
