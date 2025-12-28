"""Google Cloud Secret Manager integration for secretless authentication."""

from __future__ import annotations

import json
from typing import Any

try:
    from google.cloud import secretmanager

    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False


class GCPSecretsManager:
    """Manage secrets from Google Cloud Secret Manager."""

    def __init__(self, project_id: str) -> None:
        """Initialize Google Cloud Secret Manager client.

        Args:
            project_id: GCP project ID

        Raises:
            ImportError: If google-cloud-secret-manager is not installed
        """
        if not GCP_AVAILABLE:
            msg = "google-cloud-secret-manager package not installed"
            raise ImportError(msg)
        self.client = secretmanager.SecretManagerServiceClient()
        self.project_id = project_id

    async def get_secret(self, secret_id: str, version: str = "latest") -> dict[str, Any]:
        """Retrieve secret from Google Cloud Secret Manager.

        Args:
            secret_id: ID of the secret
            version: Version of the secret (default: "latest")

        Returns:
            Dictionary containing secret values
        """
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version}"
        response = self.client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("UTF-8")
        return json.loads(payload)

    async def get_database_credentials(self, secret_id: str) -> dict[str, str]:
        """Get database credentials from Google Cloud Secret Manager.

        Args:
            secret_id: ID of the database secret

        Returns:
            Dictionary with keys: username, password, host, port, database
        """
        secret = await self.get_secret(secret_id)
        return {
            "username": secret.get("username", ""),
            "password": secret.get("password", ""),
            "host": secret.get("host", "localhost"),
            "port": str(secret.get("port", "5432")),
            "database": secret.get("database", secret.get("dbname", "")),
        }

    async def create_secret(self, secret_id: str, secret_value: dict[str, Any]) -> str:
        """Create a new secret in Google Cloud Secret Manager.

        Args:
            secret_id: ID for the new secret
            secret_value: Dictionary of secret values

        Returns:
            Resource name of the created secret
        """
        parent = f"projects/{self.project_id}"
        secret = self.client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )

        # Add secret version with data
        payload = json.dumps(secret_value).encode("UTF-8")
        version = self.client.add_secret_version(
            request={"parent": secret.name, "payload": {"data": payload}}
        )
        return version.name

    async def update_secret(self, secret_id: str, secret_value: dict[str, Any]) -> str:
        """Update a secret in Google Cloud Secret Manager (adds new version).

        Args:
            secret_id: ID of the secret to update
            secret_value: New secret values

        Returns:
            Resource name of the new secret version
        """
        parent = f"projects/{self.project_id}/secrets/{secret_id}"
        payload = json.dumps(secret_value).encode("UTF-8")
        version = self.client.add_secret_version(
            request={"parent": parent, "payload": {"data": payload}}
        )
        return version.name
