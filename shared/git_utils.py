"""
Git utilities.

Thin wrappers around git CLI commands for reading repo state.
All functions are read-only — no commits, pushes, or rebases here.

Usage:
    from shared.git_utils import current_branch, get_repo_info, commit_log_vs_target

    branch        = current_branch()
    project, repo = get_repo_info()
    commits       = commit_log_vs_target(branch, "release_candidate")
"""

import subprocess
import sys


def _git_out(*args) -> str:
    """Run a git command and return stdout stripped of whitespace."""
    result = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    return result.stdout.strip()


def current_branch() -> str:
    """Return the currently checked-out branch name. Exits on detached HEAD."""
    branch = _git_out("rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD":
        print("Error: Could not determine current branch (detached HEAD?).", file=sys.stderr)
        sys.exit(1)
    return branch


def get_repo_info() -> tuple:
    """
    Extract (project, repo) from the git remote 'origin' URL.
    Supports both SSH and HTTPS Azure DevOps remote formats:
      SSH  : git@ssh.dev.azure.com:v3/ORG/{Project}/{Repo}
      HTTPS: https://dev.azure.com/ORG/{Project}/_git/{Repo}
    """
    remote = _git_out("remote", "get-url", "origin")
    if not remote:
        print("Error: Not in a git repo or 'origin' remote not set.", file=sys.stderr)
        sys.exit(1)
    if "ssh.dev.azure.com" in remote:
        parts = remote.split("/")
        return parts[-2], parts[-1]
    if "dev.azure.com" in remote:
        parts = remote.split("/")
        if "_git" in parts:
            git_idx = parts.index("_git")
            return parts[git_idx - 1], parts[git_idx + 1]
        return parts[4], parts[-1]
    print(f"Error: Unrecognised remote URL format: {remote}", file=sys.stderr)
    sys.exit(1)


def commit_log_vs_target(source: str, target: str) -> list:
    """Return one-line commit messages on source that are not in origin/target."""
    log = _git_out("log", f"origin/{target}..{source}", "--oneline")
    return log.splitlines() if log else []
