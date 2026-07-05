#!/usr/bin/env python3
"""
Fetch a Jira ticket title (summary) by ticket key.

Uses the official atlassian-python-api SDK.
Install dependencies first:
    pip install -r requirements.txt

Usage:
    python fetch_jira_ticket_title.py --ticket PROJ-123
    python fetch_jira_ticket_title.py --ticket PROJ-123 --json    # print full issue as JSON

Output (default):
    PROJ-123: Fix search filters not returning results
      Type:   Story
      Status: In Progress
      URL:    https://your-org.atlassian.net/browse/PROJ-123

Exit codes:
    0  – success
    1  – ticket not found, auth error, or missing credentials
"""

import argparse
import json
import sys
import os

# Add repo root to path so `sdk` package is importable regardless of CWD
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from shared.env import load_env_file, require
from shared.jira_client import get_jira_client, get_issue, get_ticket_url, JiraError


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch a Jira ticket title by key.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--ticket", "-t", required=True, help="Jira ticket key, e.g. PROJ-123")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Print the full issue fields as JSON")
    args = parser.parse_args()

    env = load_env_file()
    domain, email, token = require(env, "JIRA_DOMAIN", "JIRA_EMAIL", "JIRA_API_TOKEN")

    try:
        client = get_jira_client(domain, email, token)
        issue  = get_issue(client, args.ticket)
    except JiraError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(issue, indent=2))
        return

    fields     = issue.get("fields", {})
    summary    = fields.get("summary", "(no summary)")
    status     = fields.get("status", {}).get("name", "Unknown")
    issue_type = fields.get("issuetype", {}).get("name", "Issue")
    ticket_url = get_ticket_url(domain, args.ticket)

    print(f"{args.ticket}: {summary}")
    print(f"  Type:   {issue_type}")
    print(f"  Status: {status}")
    print(f"  URL:    {ticket_url}")


if __name__ == "__main__":
    main()
