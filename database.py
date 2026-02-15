from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from config import settings
from datetime import datetime

Base = declarative_base()

class OutageLog(Base):
    __tablename__ = "outage_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    target = Column(String)
    type = Column(String)
    error = Column(String, nullable=True)
    latency = Column(Float, nullable=True)

engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def log_outage(target: str, check_type: str, error: str = None, latency: float = None):
    async with AsyncSessionLocal() as session:
        log = OutageLog(target=target, type=check_type, error=error, latency=latency)
        session.add(log)
        await session.commit()

async def get_recent_outages(limit: int = 10):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OutageLog).order_by(OutageLog.timestamp.desc()).limit(limit)
        )
        return result.scalars().all()
