"""Azure Key Vault integration for secretless authentication."""

from __future__ import annotations

import json
from typing import Any

try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False


class AzureKeyVaultManager:
    """Manage secrets from Azure Key Vault."""

    def __init__(self, vault_url: str) -> None:
        """Initialize Azure Key Vault client.

        Args:
            vault_url: URL of the Azure Key Vault

        Raises:
            ImportError: If azure-keyvault-secrets is not installed
        """
        if not AZURE_AVAILABLE:
            msg = "azure-keyvault-secrets and azure-identity packages not installed"
            raise ImportError(msg)
        credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=credential)
        self.vault_url = vault_url

    async def get_secret(self, secret_name: str) -> dict[str, Any]:
        """Retrieve secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret

        Returns:
            Dictionary containing secret values
        """
        secret = self.client.get_secret(secret_name)
        return json.loads(secret.value)

    async def get_database_credentials(self, secret_name: str) -> dict[str, str]:
        """Get database credentials from Azure Key Vault.

        Args:
            secret_name: Name of the database secret

        Returns:
            Dictionary with keys: username, password, host, port, database
        """
        secret = await self.get_secret(secret_name)
        return {
            "username": secret.get("username", ""),
            "password": secret.get("password", ""),
            "host": secret.get("host", "localhost"),
            "port": str(secret.get("port", "5432")),
            "database": secret.get("database", secret.get("dbname", "")),
        }

    async def create_secret(self, secret_name: str, secret_value: dict[str, Any]) -> str:
        """Create a new secret in Azure Key Vault.

        Args:
            secret_name: Name for the new secret
            secret_value: Dictionary of secret values

        Returns:
            ID of the created secret
        """
        secret = self.client.set_secret(secret_name, json.dumps(secret_value))
        return secret.id

    async def update_secret(self, secret_name: str, secret_value: dict[str, Any]) -> str:
        """Update a secret in Azure Key Vault.

        Args:
            secret_name: Name of the secret to update
            secret_value: New secret values

        Returns:
            ID of the updated secret
        """
        secret = self.client.set_secret(secret_name, json.dumps(secret_value))
        return secret.id
