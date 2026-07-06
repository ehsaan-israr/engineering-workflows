#!/usr/bin/env python3
"""
Approve, complete PRs and trigger pipeline on release_candidate.

Uses the official azure-devops Python SDK (azure-devops, msrest).
Credentials are read from the repo .env file or environment variables:
    AZURE_DEVOPS_PAT  — required
    AZURE_ORG         — required

Usage:
    python merge_pr_and_trigger_pipeline.py <pr_url> [<pr_url> ...]
    python merge_pr_and_trigger_pipeline.py <url> --branch release_candidate
    python merge_pr_and_trigger_pipeline.py <url> --no-pipeline
    python merge_pr_and_trigger_pipeline.py <url> --delete-source
    python merge_pr_and_trigger_pipeline.py <url1> <url2> <url3>

Options:
    --branch BRANCH     Branch to trigger pipeline on (default: release_candidate)
    --no-pipeline       Skip pipeline trigger after merge
    --delete-source     Delete source branch after merge

Exit codes:
    0 – all PRs processed successfully
    1 – missing credentials or no valid PR URLs
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

# Add repo root to path so shared package is importable regardless of CWD
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from azure.devops.v7_1.git.models import (
    GitPullRequest,
    GitPullRequestCompletionOptions,
    IdentityRefWithVote,
)
from azure.devops.v7_1.build.models import Build, BuildDefinitionReference
from msrest.exceptions import HttpOperationError

from shared.env import load_env_file, require
from shared.azure_devops_client import get_connection


# ── URL parsing ───────────────────────────────────────────────────────────────

def parse_pr_url(url: str) -> dict | None:
    """Extract org, project, repo, pr_id from an Azure DevOps PR URL."""
    match = re.match(
        r"https://dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)/pullrequest/(\d+)", url
    )
    if not match:
        return None
    return {
        "org": match.group(1),
        "project": match.group(2),
        "repo": match.group(3),
        "pr_id": int(match.group(4)),
    }


# ── PR operations ─────────────────────────────────────────────────────────────

def get_current_user_id(connection, pat: str) -> str | None:
    """Resolve the authenticated user's identity ID via the connectionData endpoint."""
    import json
    import base64
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError

    auth = f"Basic {base64.b64encode(f':{pat}'.encode()).decode()}"
    org_url = connection.base_url.rstrip("/")
    url = f"{org_url}/_apis/connectionData"

    try:
        req = Request(url, headers={"Authorization": auth, "Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data["authenticatedUser"]["id"]
    except HTTPError as e:
        body = e.read().decode(errors="replace")
        status = e.code
        if status == 401:
            print(
                f"Error: Azure DevOps authentication failed (HTTP 401).\n"
                f"  Check that AZURE_DEVOPS_PAT is set and not expired.",
                file=sys.stderr,
            )
        elif status == 403:
            print(
                f"Error: Azure DevOps returned 403 Forbidden.\n"
                f"  The PAT may lack required permissions (Code: Read & Write, Build: Read & Execute).",
                file=sys.stderr,
            )
        else:
            print(f"Error: Azure DevOps returned HTTP {status}.\n  {body[:300]}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error: Could not connect to Azure DevOps: {e}", file=sys.stderr)
        return None


def approve_pr(git_client, project: str, repo: str, pr_id: int, user_id: str) -> bool:
    """Vote +10 (Approved) on the PR for the authenticated user."""
    try:
        reviewer = IdentityRefWithVote(id=user_id, vote=10)
        git_client.create_pull_request_reviewer(
            reviewer=reviewer,
            repository_id=repo,
            pull_request_id=pr_id,
            reviewer_id=user_id,
            project=project,
        )
        return True
    except HttpOperationError as e:
        body = e.response.text if e.response is not None else str(e)
        status = e.response.status_code if e.response is not None else 0
        if status == 401:
            print("  ✘ Authentication failed — check AZURE_DEVOPS_PAT.", file=sys.stderr)
        elif status == 403:
            print("  ✘ Permission denied — PAT needs Code (Read & Write) permission.", file=sys.stderr)
        else:
            print(f"  ✘ Approve failed (HTTP {status}): {body[:200]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ✘ Approve failed: {e}", file=sys.stderr)
        return False


def complete_pr(
    git_client, project: str, repo: str, pr_id: int, delete_source: bool
) -> tuple[bool, str]:
    """Squash-merge the PR."""
    try:
        pr: GitPullRequest = git_client.get_pull_request(
            repository_id=repo, pull_request_id=pr_id, project=project
        )
    except Exception as e:
        return False, f"Could not fetch PR: {e}"

    if pr.status == "completed":
        return True, "already completed"

    commit_id = pr.last_merge_source_commit.commit_id if pr.last_merge_source_commit else None
    if not commit_id:
        return False, "No merge source commit found"

    # Build squash merge message from PR commits
    merge_message = None
    try:
        commits = git_client.get_pull_request_commits(
            repository_id=repo, pull_request_id=pr_id, project=project
        )
        messages = [c.comment.strip() for c in commits if c.comment and c.comment.strip()]
        if messages:
            merge_message = "\n".join(f"- {m}" for m in messages)
    except Exception:
        pass

    completion_options = GitPullRequestCompletionOptions(
        delete_source_branch=delete_source,
        merge_strategy="squash",
        merge_commit_message=merge_message,
    )
    update = GitPullRequest(
        status="completed",
        last_merge_source_commit=pr.last_merge_source_commit,
        completion_options=completion_options,
    )
    try:
        git_client.update_pull_request(
            git_pull_request_to_update=update,
            repository_id=repo,
            pull_request_id=pr_id,
            project=project,
        )
        return True, "completed"
    except HttpOperationError as e:
        return False, e.response.text or str(e)
    except Exception as e:
        return False, str(e)


def wait_for_merge(
    git_client, project: str, repo: str, pr_id: int, max_wait: int = 15
) -> bool:
    """Poll until the PR status is 'completed' or timeout."""
    for _ in range(max_wait):
        try:
            pr = git_client.get_pull_request(
                repository_id=repo, pull_request_id=pr_id, project=project
            )
            if pr.status == "completed":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def trigger_pipeline(
    build_client, org_url: str, project: str, repo: str, branch: str
) -> tuple[str | None, str | None]:
    """Find the pipeline matching the repo name and queue a run on `branch`."""
    try:
        definitions: list[BuildDefinitionReference] = build_client.get_definitions(
            project=project, name=repo
        )
    except Exception as e:
        return None, f"Could not fetch pipeline definitions: {e}"

    if not definitions:
        return None, f"No pipeline named '{repo}' found in project '{project}'"

    definition = definitions[0]
    build = Build(
        definition=definition,
        source_branch=f"refs/heads/{branch}",
    )
    try:
        queued: Build = build_client.queue_build(build=build, project=project)
        run_url = f"{org_url.rstrip('/')}/{project}/_build/results?buildId={queued.id}"
        return run_url, None
    except HttpOperationError as e:
        return None, e.response.text or str(e)
    except Exception as e:
        return None, str(e)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Approve, complete PRs and trigger pipelines using the Azure DevOps SDK.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("urls", nargs="+", help="One or more Azure DevOps PR URLs")
    parser.add_argument(
        "--branch", default="release_candidate",
        help="Branch to trigger pipeline on (default: release_candidate)",
    )
    parser.add_argument("--no-pipeline", action="store_true", help="Skip pipeline trigger")
    parser.add_argument("--delete-source", action="store_true", help="Delete source branch after merge")
    args = parser.parse_args()

    # Load credentials (AZURE_ORG is required — a single connection serves all PRs)
    env = load_env_file()
    pat, org = require(env, "AZURE_DEVOPS_PAT", "AZURE_ORG")
    org_url = f"https://dev.azure.com/{org}"

    # Parse and validate PR URLs
    prs = []
    for url in args.urls:
        parsed = parse_pr_url(url.strip())
        if not parsed:
            print(f"  Skipping invalid PR URL: {url}", file=sys.stderr)
            continue
        # All PRs share one connection built from AZURE_ORG; a URL pointing at a
        # different org would be silently operated against the wrong org, so skip it.
        if parsed["org"].lower() != org.lower():
            print(
                f"  Skipping PR URL from org '{parsed['org']}' "
                f"(does not match AZURE_ORG='{org}'): {url}",
                file=sys.stderr,
            )
            continue
        prs.append(parsed)

    if not prs:
        print("Error: No valid PR URLs provided.", file=sys.stderr)
        sys.exit(1)

    # Build SDK clients (one connection per org — all PRs must share the same org)
    connection = get_connection(org_url, pat)
    git_client = connection.clients.get_git_client()
    build_client = connection.clients.get_build_client()

    user_id = get_current_user_id(connection, pat)
    if not user_id:
        print("Error: Could not retrieve authenticated user ID.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(prs)} PR(s)")
    print("=" * 60)

    triggered_pipelines: set[str] = set()

    for pr_info in prs:
        project, repo, pr_id = pr_info["project"], pr_info["repo"], pr_info["pr_id"]
        print(f"\nPR #{pr_id} — {project}/{repo}")

        # Step 1: Approve
        if approve_pr(git_client, project, repo, pr_id, user_id):
            print("  ✔ Approved")
        else:
            print("  ⚠ Approve failed (may already be approved)")

        # Step 2: Complete (squash merge)
        success, msg = complete_pr(git_client, project, repo, pr_id, args.delete_source)
        if success:
            print(f"  ✔ Completed ({msg})")
        else:
            print(f"  ✘ Complete failed: {msg}")
            continue

        # Step 3: Wait for merge
        if msg != "already completed":
            print("  … Waiting for merge to complete")
            if wait_for_merge(git_client, project, repo, pr_id):
                print("  ✔ Merged")
            else:
                print("  ⚠ Merge still in progress after timeout")

        # Step 4: Trigger pipeline (once per project/repo pair)
        pipeline_key = f"{project}/{repo}"
        if not args.no_pipeline and pipeline_key not in triggered_pipelines:
            run_url, err = trigger_pipeline(build_client, org_url, project, repo, args.branch)
            if run_url:
                print(f"  ✔ Pipeline triggered: {run_url}")
                triggered_pipelines.add(pipeline_key)
            else:
                print(f"  ✘ Pipeline trigger failed: {err}")
        elif args.no_pipeline:
            print("  – Pipeline skipped (--no-pipeline)")

    print("\n" + "=" * 60)
    print(f"Done: {len(prs)} PR(s) processed, {len(triggered_pipelines)} pipeline(s) triggered")


if __name__ == "__main__":
    main()
