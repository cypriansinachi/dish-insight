import os
import aiomysql
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

_pool = None

async def init_pool():
    """Initialize the connection pool (call this once at startup)."""
    global _pool
    _pool = await aiomysql.create_pool(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
        db=os.getenv("DB_DATABASE"),
        autocommit=True,  
        minsize=1,
        maxsize=5
    )

async def close_pool():
    """Close the connection pool (call at shutdown)."""
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        
@asynccontextmanager
async def get_conn():
    """Yield a pooled connection (use inside transactions if needed)."""
    async with _pool.acquire() as conn:
        yield conn

async def fetch_all(sql: str, params=()):
    """Run SELECT returning many rows."""
    async with _pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()

async def fetch_one(sql: str, params=()):
    """Run SELECT returning a single row (dict)."""
    rows = await fetch_all(sql, params)
    return rows[0] if rows else None

async def execute(sql: str, params=()):
    """Run INSERT/UPDATE/DELETE (returns lastrowid if available)."""
    async with _pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.lastrowid
