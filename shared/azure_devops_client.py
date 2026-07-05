"""
Azure DevOps connection factory.

Provides a single authenticated client instance backed by the official
azure-devops SDK. All PR-specific logic lives in the agent script that uses it.

Usage:
    from shared.azure_devops_client import get_azure_devops_client

    client = get_azure_devops_client("https://dev.azure.com/<org>", pat)
"""

from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication


def get_azure_devops_client(org_url: str, pat: str):
    """Return an authenticated Azure DevOps Git client."""
    credentials = BasicAuthentication("", pat)
    connection  = Connection(base_url=org_url, creds=credentials)
    return connection.clients.get_git_client()
