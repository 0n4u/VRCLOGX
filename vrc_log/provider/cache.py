import aiosqlite
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AsyncConnectionPool:
    def __init__(self, db_path: Path, max_size: int = 5) -> None:
        self.db_path: Path = db_path
        self.max_size: int = max_size
        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(max_size)
        self._initialized: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()

    async def _create_connection(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        await conn.commit()
        return conn

    async def initialize(self) -> None:
        async with self._lock:
            if self._initialized:
                return

            connections: list[aiosqlite.Connection] = []
            try:
                for _ in range(self.max_size):
                    conn = await self._create_connection()
                    await self._migrate(conn)
                    connections.append(conn)

                for conn in connections:
                    await self._pool.put(conn)
                self._initialized = True
            except Exception as e:
                for conn in connections:
                    await conn.close()
                raise RuntimeError(f"Connection pool init failed: {e}") from e

    async def _migrate(self, conn: aiosqlite.Connection) -> None:
        cursor = await conn.execute("PRAGMA user_version;")
        row = await cursor.fetchone()
        version = row[0] if row else 0

        if version == 0:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS avatars (
                    id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_avatars_updated_at
                ON avatars(updated_at);
            """)
            await conn.execute("PRAGMA user_version = 1;")
            await conn.commit()

    async def acquire(self) -> aiosqlite.Connection:
        if not self._initialized:
            await self.initialize()
        return await self._pool.get()

    async def release(self, conn: aiosqlite.Connection) -> None:
        try:
            await self._pool.put(conn)
        except asyncio.QueueFull:
            await conn.close()


class Cache:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        retention_days: int = 30,
        pool_size: int = 5,
    ) -> None:
        default_path = Path("vrc_log") / "data" / "avatars.sqlite"
        self.db_path: Path = default_path if db_path is None else Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_days: int = retention_days
        self.pool = AsyncConnectionPool(self.db_path, max_size=pool_size)

    async def check_avatar_id(self, avatar_id: str) -> bool:
        conn = await self.pool.acquire()
        try:
            now = datetime.now(timezone.utc)
            cutoff = int((now - timedelta(days=self.retention_days)).timestamp())

            cursor = await conn.execute(
                "SELECT 1 FROM avatars WHERE id = ? AND updated_at >= ?",
                (avatar_id, cutoff),
            )
            row = await cursor.fetchone()

            if row is None:
                timestamp = int(now.timestamp())
                await conn.execute(
                    "INSERT OR REPLACE INTO avatars (id, created_at, updated_at) "
                    "VALUES (?, ?, ?)",
                    (avatar_id, timestamp, timestamp),
                )
                await conn.commit()
                return True
            return False
        except Exception as e:
            logger.exception("Cache error: %s", e)
            return True
        finally:
            await self.pool.release(conn)
