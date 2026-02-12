import asyncio
from app.db.session import engine
from app.db.base import Base
import app.models

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("테이블 생성 완료")

asyncio.run(create_tables())
