from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class Lesson:
    subject: str
    lesson_type: str = ""
    time: str = ""
    teachers: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DaySchedule:
    date: date
    lessons: list[Lesson] = field(default_factory=list)
