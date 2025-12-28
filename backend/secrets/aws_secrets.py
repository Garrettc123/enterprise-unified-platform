"""AWS Secrets Manager integration for secretless authentication."""

from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError


class AWSSecretsManager:
    """Manage secrets from AWS Secrets Manager."""

    def __init__(self, region_name: str = "us-east-1") -> None:
        """Initialize AWS Secrets Manager client.

        Args:
            region_name: AWS region for Secrets Manager
        """
        self.client = boto3.client("secretsmanager", region_name=region_name)
        self.region_name = region_name

    async def get_secret(self, secret_name: str) -> dict[str, Any]:
        """Retrieve secret from AWS Secrets Manager.

        Args:
            secret_name: Name of the secret in AWS Secrets Manager

        Returns:
            Dictionary containing secret values

        Raises:
            Exception: If secret cannot be retrieved
        """
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            if "SecretString" in response:
                return json.loads(response["SecretString"])
            msg = f"Secret {secret_name} does not contain SecretString"
            raise ValueError(msg)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                msg = f"Secret {secret_name} not found"
                raise ValueError(msg) from e
            if error_code == "InvalidRequestException":
                msg = f"Invalid request for secret {secret_name}"
                raise ValueError(msg) from e
            if error_code == "InvalidParameterException":
                msg = f"Invalid parameter for secret {secret_name}"
                raise ValueError(msg) from e
            raise

    async def get_database_credentials(self, secret_name: str) -> dict[str, str]:
        """Get database credentials from AWS Secrets Manager.

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
        """Create a new secret in AWS Secrets Manager.

        Args:
            secret_name: Name for the new secret
            secret_value: Dictionary of secret values

        Returns:
            ARN of the created secret
        """
        try:
            response = self.client.create_secret(
                Name=secret_name, SecretString=json.dumps(secret_value)
            )
            return response["ARN"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                msg = f"Secret {secret_name} already exists"
                raise ValueError(msg) from e
            raise

    async def update_secret(self, secret_name: str, secret_value: dict[str, Any]) -> str:
        """Update an existing secret in AWS Secrets Manager.

        Args:
            secret_name: Name of the secret to update
            secret_value: New secret values

        Returns:
            ARN of the updated secret
        """
        response = self.client.update_secret(
            SecretId=secret_name, SecretString=json.dumps(secret_value)
        )
        return response["ARN"]
