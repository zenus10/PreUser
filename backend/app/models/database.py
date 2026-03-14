"""SQLAlchemy database models and session management."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, BigInteger, Float, DateTime, Text, JSON, ARRAY
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    filename = Column(String, nullable=False, default="")
    status = Column(String, default="processing")
    doc_text = Column(Text, default="")
    page_count = Column(Integer, default=0)
    context = Column(JSON, default=None)  # v2.0: user-provided background info
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, nullable=False)
    version = Column(Integer, default=1)
    status = Column(String, default="pending")  # v2.0: pending/running/completed/failed
    skeleton = Column(JSON, default=None)
    graph = Column(JSON, default=None)
    personas = Column(JSON, default=None)
    simulations = Column(JSON, default=None)
    report = Column(JSON, default=None)
    checkpoints = Column(JSON, default=None)  # v2.0: checkpoint state per stage
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class StageOutput(Base):
    """v2.0: Each chain's output stored independently for checkpoint/recovery."""
    __tablename__ = "stage_outputs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, nullable=False)
    stage = Column(String, nullable=False)  # skeleton/graph/personas/simulations/report
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ActionLog(Base):
    """v2.0: Structured simulation action logs (MiroFish-inspired)."""
    __tablename__ = "action_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id = Column(String, nullable=False)
    persona_id = Column(String, nullable=False)
    step = Column(Integer, nullable=False)
    scene = Column(String, default=None)  # first_use/deep_use/competitor/churn
    action = Column(String, nullable=False)
    target = Column(String, default=None)
    emotion = Column(Float, default=None)
    thought = Column(Text, default=None)
    friction = Column(JSON, default=None)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Conversation(Base):
    """v2.0: Conversation records for deep interaction system."""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, nullable=False)
    mode = Column(String, nullable=False)  # interview/focus_group/report_qa
    persona_ids = Column(JSON, default=None)  # list of persona IDs
    topic = Column(Text, default=None)
    messages = Column(JSON, nullable=False, default=list)  # full conversation history
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# Database engine and session factory

_engine = None
_session_factory = None


def _migrate_schema(conn):
    """遍历所有模型表，自动补齐数据库中缺失的列。"""
    from sqlalchemy import text, inspect
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing_cols:
                col_type = column.type.compile(conn.dialect)
                conn.execute(text(
                    f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}'
                ))



async def init_db():
    """Initialize database engine and create tables."""
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, echo=settings.app_debug)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 自动补齐新增字段，避免因 create_all 不会 ALTER 已有表导致列缺失
        await conn.run_sync(_migrate_schema)


async def close_db():
    """Close database engine."""
    global _engine
    if _engine:
        await _engine.dispose()


async def get_db() -> AsyncSession:
    """Get a database session."""
    async with _session_factory() as session:
        yield session
