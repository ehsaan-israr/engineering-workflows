#!/usr/bin/env python3
"""
Create an Azure DevOps Pull Request (Step 7 of the create_azure_pull_request agent workflow).

By the time this script runs, the agent has already:
  - committed any uncommitted changes   (Step 2)
  - fetched and rebased the branch      (Steps 3–4)
  - pushed the branch to origin         (Step 4)
  - resolved the PR title via Jira      (Step 5)

This script only creates the PR — it does not commit, rebase, push, or call Jira.

Uses the official azure-devops SDK.
Install dependencies first:
    pip install -r requirements.txt

Usage:
    python create_azure_devops_pr.py \\
        --title "Add caching layer for search filters" \\
        --source feature/PROJ-123 \\
        --target release_candidate \\
        --jira-ticket PROJ-123 \\
        --jira-url https://your-org.atlassian.net/browse/PROJ-123

    python create_azure_devops_pr.py --title "Fix login bug"
    python create_azure_devops_pr.py --title "Fix login bug" --draft

Arguments:
    --title         PR title — REQUIRED, resolved by agent Step 5
    --source        Source branch (default: current branch)
    --target        Target branch (default: DEFAULT_TARGET from .env)
    --jira-ticket   Jira ticket key for the description header (e.g. PROJ-123)
    --jira-url      Full Jira ticket URL for the description link
    --draft         Create as draft PR

Credentials resolved from environment variables or .env file at repo root:
    AZURE_DEVOPS_PAT, AZURE_ORG, DEFAULT_TARGET
"""

import argparse
import os
import sys

# Add repo root to path so `sdk` package is importable regardless of CWD
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from shared.env import load_env_file, require, optional
from shared.git_utils import (
    current_branch,
    get_repo_info,
    commit_log_vs_target,
)
from shared.azure_devops_client import get_azure_devops_client

from azure.devops.v7_1.git.models import GitPullRequest, GitPullRequestSearchCriteria


# ── PR helpers ────────────────────────────────────────────────────────────────

def build_pr_description(jira_ticket: str, jira_url: str, pr_title: str, commits: list) -> str:
    """Build the markdown PR description from Jira link and commit log."""
    parts = []
    if jira_ticket and jira_url:
        parts.append(f"## Jira Ticket\n[{jira_ticket}]({jira_url}) – {pr_title}")
    if commits:
        parts.append("## Changes\n" + "\n".join(f"- {c}" for c in commits))
    return "\n\n".join(parts)


def find_existing_pr(client, repo: str, project: str, source: str, target: str):
    """Return the first active PR for source → target, or None."""
    criteria = GitPullRequestSearchCriteria(
        source_ref_name=f"refs/heads/{source}",
        target_ref_name=f"refs/heads/{target}",
        status="active",
    )
    existing = client.get_pull_requests(repo, criteria, project=project)
    return existing[0] if existing else None


def create_pull_request(
    client,
    repo: str,
    project: str,
    source: str,
    target: str,
    title: str,
    description: str,
    is_draft: bool = False,
) -> GitPullRequest:
    """Create and return a new pull request."""
    pr = GitPullRequest(
        source_ref_name=f"refs/heads/{source}",
        target_ref_name=f"refs/heads/{target}",
        title=title,
        description=description,
        is_draft=is_draft,
    )
    return client.create_pull_request(pr, repo, project=project)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an Azure DevOps Pull Request (Step 7 of the create_azure_pull_request agent).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--title",       "-t", required=True, help="PR title — resolved by agent Step 5")
    parser.add_argument("--source",      "-s", default="",    help="Source branch (default: current branch)")
    parser.add_argument("--target",      "-T", default="",    help="Target branch (default: DEFAULT_TARGET from .env)")
    parser.add_argument("--jira-ticket", "-j", default="",    help="Jira ticket key for description, e.g. PROJ-123")
    parser.add_argument("--jira-url",    "-u", default="",    help="Full Jira ticket URL for description link")
    parser.add_argument("--draft",       action="store_true", help="Create as draft PR")
    parser.add_argument("--repo-path",   "-r", default="",    help="Absolute path to the project git repo (required when CWD is not the project repo)")
    args = parser.parse_args()

    env = load_env_file()

    # resolve config
    repo_path     = args.repo_path or None
    source_branch = args.source or current_branch(repo_path)
    target_branch = args.target or optional(env, "DEFAULT_TARGET", "release_candidate")
    azure_org, azure_pat = require(env, "AZURE_ORG", "AZURE_DEVOPS_PAT")
    org_url       = f"https://dev.azure.com/{azure_org}"
    project, repo = get_repo_info(repo_path)

    print(f"\n📬 Creating PR on Azure DevOps…")
    print("━" * 55)
    print(f"  Org:     {azure_org}")
    print(f"  Project: {project}")
    print(f"  Repo:    {repo}")
    print(f"  Source:  {source_branch} → {target_branch}")
    print(f"  Title:   {args.title}")
    if args.jira_ticket:
        print(f"  Jira:    {args.jira_url or args.jira_ticket}")
    if args.draft:
        print(f"  Draft:   Yes")

    commits        = commit_log_vs_target(source_branch, target_branch, repo_path)
    pr_description = build_pr_description(args.jira_ticket, args.jira_url, args.title, commits)

    try:
        git_client = get_azure_devops_client(org_url, azure_pat)

        existing = find_existing_pr(git_client, repo, project, source_branch, target_branch)
        if existing:
            pr_url = f"{org_url}/{project}/_git/{repo}/pullrequest/{existing.pull_request_id}"
            print(f"\nℹ️  PR already exists: #{existing.pull_request_id}\n   {pr_url}")
            sys.exit(0)

        created = create_pull_request(
            git_client, repo, project,
            source_branch, target_branch,
            args.title, pr_description, args.draft,
        )
        pr_url = f"{org_url}/{project}/_git/{repo}/pullrequest/{created.pull_request_id}"
        print(f"\n✅ PR created: #{created.pull_request_id}\n   {pr_url}")

    except Exception as e:
        msg  = str(e)
        hint = ""
        if "401" in msg or "203" in msg:
            hint = "\n  Hint: Check AZURE_DEVOPS_PAT in your .env file."
        elif "404" in msg:
            hint = "\n  Hint: Verify AZURE_ORG, project name, and repo name."
        print(f"\n❌ Failed to create PR: {msg}{hint}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
