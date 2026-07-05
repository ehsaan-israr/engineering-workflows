"""
Azure DevOps connection factory.

Provides authenticated client instances backed by the official azure-devops SDK.
All domain-specific logic lives in the agent scripts that use these clients.

Usage:
    from shared.azure_devops_client import get_connection, get_azure_devops_client

    # Git client only (backward-compatible)
    git_client = get_azure_devops_client("https://dev.azure.com/<org>", pat)

    # Full connection (for multiple clients)
    conn = get_connection("https://dev.azure.com/<org>", pat)
    git_client   = conn.clients.get_git_client()
    build_client = conn.clients.get_build_client()
"""

from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication


def get_connection(org_url: str, pat: str) -> Connection:
    """Return an authenticated Azure DevOps Connection."""
    credentials = BasicAuthentication("", pat)
    return Connection(base_url=org_url, creds=credentials)


def get_azure_devops_client(org_url: str, pat: str):
    """Return an authenticated Azure DevOps Git client (backward-compatible)."""
    return get_connection(org_url, pat).clients.get_git_client()
