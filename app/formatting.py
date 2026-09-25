from __future__ import annotations

from datetime import date
from html import escape

from .mai.models import DaySchedule


WEEKDAYS = [
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье",
]


def format_day(group: str, target: date, day: DaySchedule | None) -> str:
    head = (
        f"<b>{escape(group)}</b>\n"
        f"<b>{WEEKDAYS[target.weekday()]}, {target:%d.%m.%Y}</b>\n"
    )

    if day is None or not day.lessons:
        return head + "\nПар не найдено."

    chunks = [head]
    for i, lesson in enumerate(day.lessons, 1):
        title = escape(lesson.subject or "Без названия")
        typ = f" [{escape(lesson.lesson_type)}]" if lesson.lesson_type else ""
        chunks.append(f"\n<b>{i}. {escape(lesson.time) if lesson.time else 'Время не указано'}</b>")
        chunks.append(f"{title}{typ}")

        if lesson.teachers:
            chunks.append("Преподаватель: " + escape(", ".join(lesson.teachers)))
        if lesson.places:
            chunks.append("Аудитория: " + escape(", ".join(lesson.places)))
        if lesson.extra:
            chunks.append(escape(" / ".join(lesson.extra)))

    return "\n".join(chunks)


def format_week(group: str, days: list[DaySchedule], monday: date) -> str:
    sunday = monday.replace(day=monday.day)  # просто чтобы сохранить тип
    from datetime import timedelta
    sunday = monday + timedelta(days=6)

    chunks = [
        f"<b>{escape(group)}</b>",
        f"<b>{monday:%d.%m} — {sunday:%d.%m.%Y}</b>",
    ]

    by_date = {d.date: d for d in days}
    for offset in range(7):
        d = monday + timedelta(days=offset)
        schedule = by_date.get(d)
        if not schedule or not schedule.lessons:
            continue

        chunks.append(f"\n<b>{WEEKDAYS[d.weekday()]}, {d:%d.%m}</b>")
        for lesson in schedule.lessons:
            typ = f" [{escape(lesson.lesson_type)}]" if lesson.lesson_type else ""
            time_text = escape(lesson.time) if lesson.time else "—"
            chunks.append(f"{time_text} — {escape(lesson.subject)}{typ}")

            tails = []
            if lesson.teachers:
                tails.append(", ".join(lesson.teachers))
            if lesson.places:
                tails.append(", ".join(lesson.places))
            if tails:
                chunks.append(escape(" / ".join(tails)))

    if len(chunks) == 2:
        chunks.append("\nРасписание на эту неделю не найдено.")

    return "\n".join(chunks)
