"""UTC calendar dates, preserving PostgreSQL's clamped month-end semantics."""

import calendar
import re
from datetime import date, timedelta


def advance(day: date, interval: str) -> date:
    match = re.fullmatch(r"P([1-9][0-9]{0,2}|1000)([DWMY])", interval)
    if match is None:
        raise ValueError("Use 1–1000 whole days, weeks, months or years")
    amount, unit = int(match[1]), match[2]
    if unit in {"D", "W"}:
        return day + timedelta(days=amount * (7 if unit == "W" else 1))
    month = day.year * 12 + day.month - 1 + amount * (12 if unit == "Y" else 1)
    year, month = divmod(month, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
