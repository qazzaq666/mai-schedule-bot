from __future__ import annotations

import asyncio
import re
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import aiohttp
from yarl import URL
from bs4 import BeautifulSoup

from .models import DaySchedule, Lesson


BASE = "https://mai.ru/education/studies/schedule/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

GROUP_RE = re.compile(
    r"^[А-ЯA-ZЁ]\s*(?P<dep>\d{1,2})[А-ЯA-ZЁ]*-(?P<course>\d)",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"(?P<day>\d{1,2})[.\s/-](?P<month>\d{1,2})(?:[.\s/-](?P<year>\d{2,4}))?")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}\b")
TYPE_RE = re.compile(
    r"^(ЛК|ЛР|ПЗ|ПР|СР|КП|КР|ЭКЗ|ЗАЧ|КОНС|ЛЕКЦИЯ|ПРАКТИКА|ЛАБОРАТОРНАЯ)\b[.:\-–— ]*",
    re.IGNORECASE,
)


def normalize_group(value: str) -> str:
    return re.sub(r"\s+", "", value.strip()).upper().replace("O", "О")


def infer_department_course(group: str) -> tuple[int, int] | None:
    m = GROUP_RE.match(normalize_group(group))
    if not m:
        return None
    return int(m.group("dep")), int(m.group("course"))


def _parse_date(text: str) -> date | None:
    """
    Parse MAI headings such as:
        "Вт, 01 сентября"
        "Ср, 02 сентября"

    Important: month names are matched as whole words.  The previous version
    used the substring "ма" for May, so words like "информации" could turn
    September dates into May dates.
    """
    text = " ".join(text.split())
    lower = text.lower().replace("ё", "е")

    # Numeric date, if MAI ever renders one.
    m = DATE_RE.search(lower[:30])
    if m:
        d = int(m.group("day"))
        mo = int(m.group("month"))
        y_raw = m.group("year")
        y = int(y_raw) if y_raw else date.today().year
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d)
        except ValueError:
            pass

    month_forms = {
        "января": 1,
        "февраля": 2,
        "марта": 3,
        "апреля": 4,
        "мая": 5,
        "июня": 6,
        "июля": 7,
        "августа": 8,
        "сентября": 9,
        "октября": 10,
        "ноября": 11,
        "декабря": 12,
    }

    # The heading is at the beginning of step-content, therefore take the
    # first exact "<day> <month>" occurrence from the node text.
    month_alt = "|".join(month_forms)
    m = re.search(
        rf"(?<!\d)(\d{{1,2}})\s+({month_alt})(?![а-я])",
        lower,
        re.IGNORECASE,
    )
    if not m:
        return None

    d = int(m.group(1))
    mo = month_forms[m.group(2).lower()]
    y = date.today().year

    try:
        return date(y, mo, d)
    except ValueError:
        return None



class MaiClient:
    def __init__(self, cache_ttl: int = 900, semester_start: date | None = None):
        self.cache_ttl = cache_ttl
        self.semester_start = semester_start
        self._cache: dict[str, tuple[float, str, str]] = {}
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": UA},
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, url: str) -> tuple[str, str]:
        now = time.monotonic()
        cached = self._cache.get(url)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1], cached[2]

        async with self._lock:
            cached = self._cache.get(url)
            now = time.monotonic()
            if cached and now - cached[0] < self.cache_ttl:
                return cached[1], cached[2]

            session = await self._get_session()
            async with session.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                html = await response.text()
                final_url = str(response.url)

            self._cache[url] = (time.monotonic(), html, final_url)
            return html, final_url

    async def group_exists(self, group: str) -> bool:
        group = normalize_group(group)
        inferred = infer_department_course(group)
        if inferred is None:
            return False

        dep, course = inferred
        query = urlencode({
            "department": f"Институт №{dep}",
            "course": course,
        })
        html, _ = await self._get(f"{BASE}groups.php?{query}")
        soup = BeautifulSoup(html, "html.parser")

        candidates = {
            normalize_group(a.get_text(" ", strip=True))
            for a in soup.select("a.btn-group")
        }
        return group in candidates

    async def search_groups(self, query: str, limit: int = 8) -> list[str]:
        query = normalize_group(query)
        inferred = infer_department_course(query)

        pages: list[tuple[int, int]] = []
        if inferred:
            pages.append(inferred)
        else:
            # Для неполного ввода не долбим весь сайт сотней запросов.
            return []

        dep, course = pages[0]
        qs = urlencode({"department": f"Институт №{dep}", "course": course})
        html, _ = await self._get(f"{BASE}groups.php?{qs}")
        soup = BeautifulSoup(html, "html.parser")

        groups = []
        for a in soup.select("a.btn-group"):
            name = normalize_group(a.get_text(" ", strip=True))
            if query in name:
                groups.append(name)

        return sorted(set(groups))[:limit]

    async def _prepare_group_session(self, group: str) -> str:
        """
        MAI stores the selected student group in cookies.
        A bare request to index.php?group=... can be redirected to groups.php,
        even though the schedule exists.

        We reproduce the browser flow:
        1. visit the institute/course groups page to obtain PHPSESSID;
        2. set schedule-st-group and schedule-group-cache cookies;
        3. use that groups page as Referer for the schedule request.
        """
        inferred = infer_department_course(group)
        if inferred is None:
            raise ValueError(f"Не удалось определить институт/курс из группы: {group}")

        dep, course = inferred
        referer = f"{BASE}groups.php?" + urlencode({
            "department": f"Институт №{dep}",
            "course": course,
        })

        session = await self._get_session()

        # Intentionally not cached: this request initializes/refreshes PHP session cookies.
        async with session.get(
            referer,
            allow_redirects=True,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
            },
        ) as response:
            response.raise_for_status()
            await response.read()

        session.cookie_jar.update_cookies(
            {
                "schedule-st-group": group,
                "schedule-group-cache": "2.3",
            },
            response_url=URL(BASE),
        )

        return referer

    async def get_schedule(self, group: str, week: int | None = None) -> list[DaySchedule]:
        group = normalize_group(group)
        params = {"group": group}
        if week is not None:
            params["week"] = str(week)

        referer = await self._prepare_group_session(group)
        url = f"{BASE}index.php?{urlencode(params)}"

        # Cache schedule pages, but only after the browser-like session has been prepared.
        cache_key = f"schedule::{url}"
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.cache_ttl:
            return self.parse_schedule(cached[1])

        session = await self._get_session()
        async with session.get(
            url,
            allow_redirects=True,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Referer": referer,
                "Upgrade-Insecure-Requests": "1",
            },
        ) as response:
            response.raise_for_status()
            html = await response.text()
            final_url = str(response.url)

        if "groups.php" in final_url:
            # Don't cache a failed redirect as an empty schedule.
            return []

        self._cache[cache_key] = (time.monotonic(), html, final_url)
        return self.parse_schedule(html)

    def parse_schedule(self, html: str) -> list[DaySchedule]:
        soup = BeautifulSoup(html, "html.parser")
        result: list[DaySchedule] = []

        for day_node in soup.select("div.step-content"):
            day_text = day_node.get_text(" ", strip=True)
            parsed_date = _parse_date(day_text)
            if not parsed_date:
                continue

            day = DaySchedule(date=parsed_date)

            for block in day_node.select("div.mb-4"):
                title_node = block.select_one("p.mb-2.fw-semi-bold.text-dark")
                details_node = block.select_one(
                    "ul.list-inline.list-separator.text-body.small"
                )
                if title_node is None:
                    continue

                raw_title = " ".join(title_node.get_text(" ", strip=True).split())
                lesson_type = ""
                subject = raw_title

                mt = TYPE_RE.match(raw_title)
                if mt:
                    lesson_type = mt.group(1).upper()
                    subject = raw_title[mt.end():].strip(" :-–—")

                items = []
                if details_node:
                    for li in details_node.select("li"):
                        text = " ".join(li.get_text(" ", strip=True).split())
                        if text:
                            items.append((li, text))

                lesson = Lesson(subject=subject, lesson_type=lesson_type)

                for li, text in items:
                    tm = TIME_RE.search(text)
                    if tm and not lesson.time:
                        lesson.time = tm.group(0)
                        continue

                    teacher_links = [
                        " ".join(a.get_text(" ", strip=True).split())
                        for a in li.select('a[href*="ppc.php"]')
                        if a.get_text(" ", strip=True)
                    ]
                    if teacher_links:
                        lesson.teachers.extend(teacher_links)
                        continue

                    lower = text.lower()
                    if any(x in lower for x in ("ауд.", "аудит", "корпус", "каф.", "кафедр")):
                        lesson.places.append(text)
                    elif re.search(
                        r"(?:\bГУК\s+)?(?:\d{1,2}[А-ЯA-Z]?|[А-ЯA-Z])-\d{2,4}\b",
                        text,
                        re.IGNORECASE,
                    ):
                        # Examples used by MAI: 5-111, 24Б-330, ГУК В-228, ГУК А-320.
                        lesson.places.append(text)
                    else:
                        lesson.extra.append(text)

                # Иногда преподаватель является обычной ссылкой без ppc.php.
                if details_node and not lesson.teachers:
                    for a in details_node.select("a"):
                        text = " ".join(a.get_text(" ", strip=True).split())
                        href = a.get("href", "")
                        if text and ("ppc" in href or len(text.split()) >= 2):
                            if text not in lesson.teachers:
                                lesson.teachers.append(text)

                day.lessons.append(lesson)

            result.append(day)

        # Дедуп + сортировка.
        unique = {d.date: d for d in result}
        return [unique[d] for d in sorted(unique)]

    def calc_week(self, target: date) -> int | None:
        if not self.semester_start:
            return None
        monday = self.semester_start - timedelta(days=self.semester_start.weekday())
        if target < monday:
            return None
        return ((target - monday).days // 7) + 1

    async def schedule_for_date(self, group: str, target: date) -> DaySchedule | None:
        current = await self.get_schedule(group)
        for day in current:
            if day.date == target:
                return day

        week = self.calc_week(target)
        if week and 1 <= week <= 18:
            schedule = await self.get_schedule(group, week)
            for day in schedule:
                if day.date == target:
                    return day

        return None

    async def schedule_for_week(self, group: str, target: date) -> list[DaySchedule]:
        monday = target - timedelta(days=target.weekday())
        sunday = monday + timedelta(days=6)

        current = await self.get_schedule(group)
        current_filtered = [d for d in current if monday <= d.date <= sunday]
        if current_filtered:
            return current_filtered

        week = self.calc_week(target)
        if week and 1 <= week <= 18:
            specific = await self.get_schedule(group, week)
            return [d for d in specific if monday <= d.date <= sunday]

        return []
