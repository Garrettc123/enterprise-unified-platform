import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
import asyncio

from backend.main import app
from backend.database import get_db
from backend.models import Base, User, UserProfile
from backend.security import get_password_hash
from backend.schemas import UserProfileCreate, UserProfileUpdate, UserProfileResponse

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_db():
    """Create test database with all tables."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield session_factory

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_teardown())
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestUserProfileModel:
    """Tests for the UserProfile SQLAlchemy model."""

    def test_create_user_profile(self, setup_db):
        """Test creating a UserProfile linked to a User."""
        session_factory = setup_db

        async def _test():
            async with session_factory() as session:
                user = User(
                    username="profileuser",
                    email="profile@example.com",
                    hashed_password=get_password_hash("testpass123"),
                    full_name="Profile User",
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                profile = UserProfile(
                    user_id=user.id,
                    phone_number="+1234567890",
                    location="New York, NY",
                    job_title="Software Engineer",
                    department="Engineering",
                    timezone="America/New_York",
                    language="en",
                    linkedin_url="https://linkedin.com/in/profileuser",
                    github_url="https://github.com/profileuser",
                    profile_visibility="public",
                )
                session.add(profile)
                await session.commit()
                await session.refresh(profile)

                assert profile.id is not None
                assert profile.user_id == user.id
                assert profile.phone_number == "+1234567890"
                assert profile.location == "New York, NY"
                assert profile.job_title == "Software Engineer"
                assert profile.department == "Engineering"
                assert profile.timezone == "America/New_York"
                assert profile.language == "en"
                assert profile.profile_visibility == "public"

        asyncio.run(_test())

    def test_user_profile_relationship(self, setup_db):
        """Test User-UserProfile one-to-one relationship."""
        session_factory = setup_db

        async def _test():
            async with session_factory() as session:
                user = User(
                    username="reluser",
                    email="rel@example.com",
                    hashed_password=get_password_hash("testpass123"),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                profile = UserProfile(
                    user_id=user.id,
                    job_title="Manager",
                    department="Operations",
                )
                session.add(profile)
                await session.commit()

                # Query profile by user_id
                result = await session.execute(
                    select(UserProfile).where(UserProfile.user_id == user.id)
                )
                fetched_profile = result.scalar_one_or_none()
                assert fetched_profile is not None
                assert fetched_profile.job_title == "Manager"
                assert fetched_profile.department == "Operations"

        asyncio.run(_test())

    def test_user_profile_defaults(self, setup_db):
        """Test UserProfile default values."""
        session_factory = setup_db

        async def _test():
            async with session_factory() as session:
                user = User(
                    username="defaultuser",
                    email="default@example.com",
                    hashed_password=get_password_hash("testpass123"),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                profile = UserProfile(user_id=user.id)
                session.add(profile)
                await session.commit()
                await session.refresh(profile)

                assert profile.timezone == "UTC"
                assert profile.language == "en"
                assert profile.profile_visibility == "public"
                assert profile.phone_number is None
                assert profile.location is None
                assert profile.job_title is None

        asyncio.run(_test())

    def test_user_profile_cascade_delete(self, setup_db):
        """Test that UserProfile is deleted when User is deleted."""
        session_factory = setup_db

        async def _test():
            async with session_factory() as session:
                user = User(
                    username="cascadeuser",
                    email="cascade@example.com",
                    hashed_password=get_password_hash("testpass123"),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = user.id

                profile = UserProfile(
                    user_id=user.id,
                    job_title="To Be Deleted",
                )
                session.add(profile)
                await session.commit()

                # Delete the user
                await session.delete(user)
                await session.commit()

                # Verify profile is also deleted
                result = await session.execute(
                    select(UserProfile).where(UserProfile.user_id == user_id)
                )
                assert result.scalar_one_or_none() is None

        asyncio.run(_test())

    def test_user_profile_update(self, setup_db):
        """Test updating a UserProfile."""
        session_factory = setup_db

        async def _test():
            async with session_factory() as session:
                user = User(
                    username="updateuser",
                    email="update@example.com",
                    hashed_password=get_password_hash("testpass123"),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                profile = UserProfile(
                    user_id=user.id,
                    job_title="Junior Developer",
                    location="San Francisco, CA",
                )
                session.add(profile)
                await session.commit()
                await session.refresh(profile)

                # Update profile
                profile.job_title = "Senior Developer"
                profile.location = "Remote"
                await session.commit()
                await session.refresh(profile)

                assert profile.job_title == "Senior Developer"
                assert profile.location == "Remote"

        asyncio.run(_test())


class TestUserProfileSchema:
    """Tests for UserProfile Pydantic schemas."""

    def test_user_profile_create_schema(self):
        """Test UserProfileCreate schema validation."""
        profile_data = UserProfileCreate(
            phone_number="+1234567890",
            location="New York, NY",
            job_title="Engineer",
        )
        assert profile_data.phone_number == "+1234567890"
        assert profile_data.timezone == "UTC"
        assert profile_data.language == "en"

    def test_user_profile_create_defaults(self):
        """Test UserProfileCreate schema default values."""
        profile_data = UserProfileCreate()
        assert profile_data.timezone == "UTC"
        assert profile_data.language == "en"
        assert profile_data.profile_visibility == "public"
        assert profile_data.phone_number is None

    def test_user_profile_update_schema(self):
        """Test UserProfileUpdate schema allows partial updates."""
        update_data = UserProfileUpdate(job_title="Lead Engineer")
        assert update_data.job_title == "Lead Engineer"
        assert update_data.phone_number is None

    def test_user_profile_response_schema(self):
        """Test UserProfileResponse schema."""
        from datetime import datetime

        now = datetime.utcnow()
        profile_resp = UserProfileResponse(
            id=1,
            user_id=1,
            phone_number="+1234567890",
            location="NYC",
            job_title="Dev",
            department="Eng",
            timezone="UTC",
            language="en",
            profile_visibility="public",
            created_at=now,
            updated_at=now,
        )
        assert profile_resp.id == 1
        assert profile_resp.user_id == 1


class TestMigrationFile:
    """Tests to verify the migration file structure."""

    def test_migration_file_exists(self):
        """Test that migration file exists."""
        import os

        versions_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "backend", "alembic", "versions",
        )
        migration_files = [
            f for f in os.listdir(versions_dir)
            if f.endswith(".py") and "user_profile" in f
        ]
        assert len(migration_files) == 1

    def test_migration_has_upgrade_and_downgrade(self):
        """Test that migration has upgrade and downgrade functions."""
        import importlib
        import os
        import sys

        versions_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "backend", "alembic", "versions",
        )
        migration_files = [
            f for f in os.listdir(versions_dir)
            if f.endswith(".py") and "user_profile" in f
        ]
        assert len(migration_files) == 1

        # Import the migration module
        migration_path = os.path.join(versions_dir, migration_files[0])
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        assert hasattr(migration, "upgrade")
        assert hasattr(migration, "downgrade")
        assert callable(migration.upgrade)
        assert callable(migration.downgrade)
