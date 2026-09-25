#!/usr/bin/env python3
import asyncio
from app.mai.client import MaiClient

GROUP = "М4О-301БВ-24"

async def main():
    c = MaiClient(cache_ttl=0)
    try:
        days = await c.get_schedule(GROUP)
        print(f"Parsed days: {len(days)}")
        for day in days:
            print(day.date, f"lessons={len(day.lessons)}")
            for x in day.lessons:
                print(" ", x.time, x.subject, x.lesson_type, x.teachers, x.places)
    finally:
        await c.close()

asyncio.run(main())
