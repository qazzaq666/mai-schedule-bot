from __future__ import annotations

import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                group_name TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def get_group(self, telegram_id: int) -> str | None:
        assert self.conn
        async with self.conn.execute(
            "SELECT group_name FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def set_group(self, telegram_id: int, group_name: str):
        assert self.conn
        await self.conn.execute(
            '''
            INSERT INTO users (telegram_id, group_name, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                group_name = excluded.group_name,
                updated_at = CURRENT_TIMESTAMP
            ''',
            (telegram_id, group_name),
        )
        await self.conn.commit()
