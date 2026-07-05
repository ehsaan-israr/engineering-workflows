"""
Environment / credential helpers.

All scripts in this repo resolve configuration in the same order:
    environment variable  >  .env file at repo root  >  explicit fallback

Usage:
    from shared.env import load_env_file, require, optional

    env    = load_env_file()
    [pat]  = require(env, "AZURE_DEVOPS_PAT")
    target = optional(env, "DEFAULT_TARGET", "release_candidate")
"""

import os
import sys

# Repo root is one level up from shared/
_SHARED_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.normpath(os.path.join(_SHARED_DIR, ".."))
ENV_FILE    = os.path.join(REPO_ROOT, ".env")


def load_env_file(path: str = ENV_FILE) -> dict:
    """Parse KEY=VALUE pairs from an env file; ignores blank lines and comments."""
    env: dict = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                # Strip inline comments (e.g. VALUE=foo  # comment → foo)
                value = value.split("#")[0].strip()
                env[key.strip()] = value
    return env


def require(env: dict, *names: str) -> list:
    """
    Return values for the given env var names (env vars take precedence over .env).
    Prints an error and exits if any are missing.
    """
    values, missing = [], []
    for name in names:
        val = os.environ.get(name) or env.get(name)
        if not val:
            missing.append(name)
        values.append(val)
    if missing:
        for name in missing:
            print(
                f"Error: {name} not found.\n"
                f"  Set it in {ENV_FILE} or export {name}=<value>",
                file=sys.stderr,
            )
        sys.exit(1)
    return values


def optional(env: dict, name: str, fallback: str = "") -> str:
    """Return the value for name from env vars or .env, with an optional fallback."""
    return os.environ.get(name) or env.get(name) or fallback
