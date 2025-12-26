from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'sqlite+aiosqlite:///./test.db'
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv('DEBUG', False) == 'True',
    poolclass=NullPool if 'sqlite' in DATABASE_URL else None,
    connect_args={
        'check_same_thread': False
    } if 'sqlite' in DATABASE_URL else {}
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    """Dependency for getting database session"""
    async with async_session() as session:
        yield session

async def init_db():
    """Initialize database tables"""
    from .models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)