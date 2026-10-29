"""Regression tests for the first-admin password policy and database URL parsing."""

import pytest
from pydantic import ValidationError

from backend.database import _async_database_url
from backend.routers.bootstrap import BootstrapAdminCreate


def _payload(password: str) -> dict[str, str]:
    return {
        "username": "owner-admin",
        "email": "Gwc2780@gmail.com",
        "full_name": "Garcar Enterprise Owner",
        "password": password,
    }


def test_bootstrap_requires_at_least_twelve_password_characters() -> None:
    with pytest.raises(ValidationError):
        BootstrapAdminCreate(**_payload("ShortPass1"))


def test_bootstrap_accepts_a_password_at_the_minimum_length() -> None:
    user = BootstrapAdminCreate(**_payload("12CharsLong!"))
    assert user.password == "12CharsLong!"


def test_bootstrap_rejects_passwords_over_bcrypt_character_limit() -> None:
    with pytest.raises(ValidationError):
        BootstrapAdminCreate(**_payload("x" * 73))


def test_postgres_urls_are_normalized_for_asyncpg() -> None:
    assert _async_database_url("postgres://user:pass@host/db") == (
        "postgresql+asyncpg://user:pass@host/db"
    )
    assert _async_database_url("postgresql://user:pass@host/db") == (
        "postgresql+asyncpg://user:pass@host/db"
    )
