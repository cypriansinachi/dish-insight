import os
import aiomysql
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from typing import Any, Callable, Awaitable

load_dotenv()

_pool = None

async def init_pool():
    """Initialize the connection pool (call this once at startup)."""
    global _pool
    if _pool is not None:
        return
    _pool = await aiomysql.create_pool(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_DATABASE"),
        autocommit=True,
        minsize=1,
        maxsize=5,
        connect_timeout=float(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        # Recycle connections to avoid server closing idle ones
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "280")),
    )

async def close_pool():
    """Close the connection pool (call at shutdown)."""
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        
async def _recreate_pool():
    global _pool
    try:
        await close_pool()
    finally:
        await init_pool()
        
@asynccontextmanager
async def get_conn():
    """Yield a pooled connection (use inside transactions if needed)."""
    if _pool is None:
        await init_pool()
    async with _pool.acquire() as conn:
        # Ensure connection is alive; reconnect if necessary
        try:
            await conn.ping()
        except Exception:
            await _recreate_pool()
            async with _pool.acquire() as conn2:
                await conn2.ping()
                yield conn2
                return
        yield conn

async def _with_retry(coro_factory: Callable[[], Awaitable[Any]]):
    try:
        return await coro_factory()
    except aiomysql.OperationalError as e:
        # Retry on common disconnect errors
        if getattr(e, 'args', None) and e.args and e.args[0] in (2006, 2013, 2055):
            await _recreate_pool()
            return await coro_factory()
        raise

async def fetch_all(sql: str, params=()):
    """Run SELECT returning many rows."""
    async def _runner():
        async with _pool.acquire() as conn:
            try:
                await conn.ping()
            except Exception:
                await _recreate_pool()
            async with _pool.acquire() as conn2:
                async with conn2.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, params)
                    return await cur.fetchall()
    return await _with_retry(_runner)

async def fetch_one(sql: str, params=()):
    """Run SELECT returning a single row (dict)."""
    rows = await fetch_all(sql, params)
    return rows[0] if rows else None

async def execute(sql: str, params=()):
    """Run INSERT/UPDATE/DELETE (returns lastrowid if available)."""
    async def _runner():
        async with _pool.acquire() as conn:
            try:
                await conn.ping()
            except Exception:
                await _recreate_pool()
            async with _pool.acquire() as conn2:
                async with conn2.cursor() as cur:
                    await cur.execute(sql, params)
                    return cur.lastrowid
    return await _with_retry(_runner)
