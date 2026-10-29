"""Regression tests for first-admin passwords and async database URL parsing."""

import pytest
from pydantic import ValidationError

from backend.database import _async_database_url
from backend.routers.bootstrap import BootstrapAdminCreate
from backend.security import get_password_hash, verify_password


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


def test_bcrypt_password_hash_and_verification_round_trip() -> None:
    password = "LongEnough!Password42"
    password_hash = get_password_hash(password)
    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_postgres_urls_are_normalized_for_asyncpg() -> None:
    assert _async_database_url("postgres://user:pass@host/db") == (
        "postgresql+asyncpg://user:pass@host/db"
    )
    assert _async_database_url("postgresql://user:pass@host/db") == (
        "postgresql+asyncpg://user:pass@host/db"
    )


def test_postgres_sslmode_is_converted_to_asyncpg_ssl_parameter() -> None:
    assert _async_database_url(
        "postgresql://user:pass@host/db?sslmode=require"
    ) == "postgresql+asyncpg://user:pass@host/db?ssl=require"


def test_explicit_asyncpg_ssl_parameter_takes_precedence() -> None:
    assert _async_database_url(
        "postgresql://user:pass@host/db?ssl=require&sslmode=disable"
    ) == "postgresql+asyncpg://user:pass@host/db?ssl=require"
