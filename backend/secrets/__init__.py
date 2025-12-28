"""Secrets management package for secretless authentication."""

from __future__ import annotations

import os
from enum import Enum
from typing import Any

from .aws_secrets import AWSSecretsManager
from .azure_secrets import AZURE_AVAILABLE, AzureKeyVaultManager
from .gcp_secrets import GCP_AVAILABLE, GCPSecretsManager

__all__ = [
    "AWSSecretsManager",
    "AzureKeyVaultManager",
    "GCPSecretsManager",
    "SecretsProvider",
    "get_secrets_manager",
    "get_database_url_from_secrets",
]


class SecretsProvider(str, Enum):
    """Supported secrets providers."""

    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    ENV = "env"


def get_secrets_manager(
    provider: SecretsProvider | str | None = None,
    **kwargs: Any,
) -> AWSSecretsManager | GCPSecretsManager | AzureKeyVaultManager:
    """Get appropriate secrets manager based on provider.

    Args:
        provider: Secrets provider to use (aws, gcp, azure)
        **kwargs: Provider-specific arguments

    Returns:
        Initialized secrets manager instance

    Raises:
        ValueError: If provider is not supported or required packages not installed
    """
    if provider is None:
        provider = os.getenv("SECRETS_PROVIDER", "env")

    provider_str = provider if isinstance(provider, str) else provider.value
    provider_str = provider_str.lower()

    if provider_str == "aws":
        region = kwargs.get("region", os.getenv("AWS_REGION", "us-east-1"))
        return AWSSecretsManager(region_name=region)

    if provider_str == "gcp":
        if not GCP_AVAILABLE:
            msg = "GCP secrets requires google-cloud-secret-manager package"
            raise ValueError(msg)
        project_id = kwargs.get("project_id", os.getenv("GCP_PROJECT_ID"))
        if not project_id:
            msg = "GCP project_id is required"
            raise ValueError(msg)
        return GCPSecretsManager(project_id=project_id)

    if provider_str == "azure":
        if not AZURE_AVAILABLE:
            msg = "Azure secrets requires azure-keyvault-secrets package"
            raise ValueError(msg)
        vault_url = kwargs.get("vault_url", os.getenv("AZURE_KEY_VAULT_URL"))
        if not vault_url:
            msg = "Azure vault_url is required"
            raise ValueError(msg)
        return AzureKeyVaultManager(vault_url=vault_url)

    if provider_str == "env":
        msg = "Using environment variables for secrets"
        raise ValueError(msg)

    msg = f"Unknown secrets provider: {provider_str}"
    raise ValueError(msg)


async def get_database_url_from_secrets(
    provider: SecretsProvider | str | None = None,
    secret_name: str | None = None,
    **kwargs: Any,
) -> str:
    """Get database URL from secrets manager.

    Args:
        provider: Secrets provider (aws, gcp, azure, env)
        secret_name: Name of the secret containing database credentials
        **kwargs: Provider-specific arguments

    Returns:
        PostgreSQL database URL

    Raises:
        ValueError: If provider not supported or credentials incomplete
    """
    if provider is None:
        provider = os.getenv("SECRETS_PROVIDER", "env")

    provider_str = provider if isinstance(provider, str) else provider.value
    provider_str = provider_str.lower()

    # Use environment variables as fallback
    if provider_str == "env" or not secret_name:
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "enterprise_db")
        username = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")
        return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"

    # Get credentials from secrets manager
    secrets_manager = get_secrets_manager(provider, **kwargs)
    credentials = await secrets_manager.get_database_credentials(secret_name)

    username = credentials["username"]
    password = credentials["password"]
    host = credentials["host"]
    port = credentials["port"]
    database = credentials["database"]

    if not all([username, password, host, database]):
        msg = "Incomplete database credentials in secret"
        raise ValueError(msg)

    return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"
