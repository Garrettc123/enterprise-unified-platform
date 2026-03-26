"""
Database Layer
==============
SQLite via `databases` for async I/O.
Includes revenue_events table for idempotent Stripe event persistence.
Swap DATABASE_URL env var to postgres:// for production.
"""
import logging
import os
from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String, Table, Text,
    create_engine,
)
from databases import Database

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./enterprise.db")

database = Database(DATABASE_URL)
metadata = MetaData()

users_table = Table(
    "users", metadata,
    Column("id", String, primary_key=True),
    Column("email", String, unique=True, nullable=False),
    Column("hashed_password", String, nullable=False),
    Column("full_name", String),
    Column("organization_id", String),
    Column("role", String, default="member"),
    Column("is_active", Integer, default=1),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

projects_table = Table(
    "projects", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("description", Text),
    Column("status", String, default="active"),
    Column("owner_id", String),
    Column("organization_id", String),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

tasks_table = Table(
    "tasks", metadata,
    Column("id", String, primary_key=True),
    Column("title", String, nullable=False),
    Column("description", Text),
    Column("status", String, default="todo"),
    Column("priority", String, default="medium"),
    Column("project_id", String),
    Column("assignee_id", String),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
    Column("due_date", DateTime),
)

organizations_table = Table(
    "organizations", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("slug", String, unique=True),
    Column("plan", String, default="free"),
    Column("created_at", DateTime),
)

audit_logs_table = Table(
    "audit_logs", metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String),
    Column("action", String),
    Column("resource_type", String),
    Column("resource_id", String),
    Column("details", Text),
    Column("ip_address", String),
    Column("created_at", DateTime),
)

# Revenue events — idempotent Stripe event log
# ON CONFLICT (stripe_event_id) DO NOTHING ensures replayed events are safe
revenue_events_table = Table(
    "revenue_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("stripe_event_id", String, unique=True, nullable=False),
    Column("event_type", String, nullable=False),
    Column("amount_cents", Integer, default=0),
    Column("customer_id", String, nullable=False),
    Column("meta", Text, default="{}"),
    Column("created_at", String),
)


async def init_db():
    """Connect to DB and create all tables including revenue_events."""
    await database.connect()
    engine = create_engine(DATABASE_URL.replace("sqlite+aiosqlite", "sqlite"))
    metadata.create_all(engine)
    logger.info("Database connected and tables created (including revenue_events)")


async def get_db():
    """FastAPI dependency — yields connected database instance."""
    yield database
