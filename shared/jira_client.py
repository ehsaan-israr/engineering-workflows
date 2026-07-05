"""
Jira client.

Wraps the official atlassian-python-api SDK with clean error handling
for common HTTP error codes.

Usage:
    from shared.env import load_env_file, require
    from shared.jira_client import get_jira_client, get_issue, get_ticket_url, JiraError

    env                      = load_env_file()
    domain, email, token     = require(env, "JIRA_DOMAIN", "JIRA_EMAIL", "JIRA_API_TOKEN")
    client                   = get_jira_client(domain, email, token)
    issue                    = get_issue(client, "PROJ-123")
    summary                  = issue["fields"]["summary"]
"""

from atlassian import Jira


class JiraError(Exception):
    """Raised when a Jira API call fails."""


def get_jira_client(domain: str, email: str, token: str) -> Jira:
    """Return an authenticated Jira client for Atlassian Cloud."""
    return Jira(url=domain, username=email, password=token, cloud=True)


def get_issue(client: Jira, ticket_key: str, fields: str = "summary,status,issuetype") -> dict:
    """
    Fetch a Jira issue by key.
    Raises JiraError with a human-readable message on failure.
    """
    try:
        return client.get_issue(ticket_key, fields=fields)
    except Exception as e:
        msg = str(e)
        if "401" in msg:
            raise JiraError("Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN.")
        if "403" in msg:
            raise JiraError(f"No permission to access ticket '{ticket_key}'.")
        if "404" in msg:
            raise JiraError(f"Ticket '{ticket_key}' not found in Jira.")
        raise JiraError(str(e))


def get_ticket_url(domain: str, ticket_key: str) -> str:
    """Return the full browse URL for a ticket."""
    return f"{domain.rstrip('/')}/browse/{ticket_key}"
