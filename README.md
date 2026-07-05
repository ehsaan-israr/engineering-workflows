# engineering-workflows

A structured collection of AI agents, scripts, and shared utilities for automating engineering workflows — PR creation, Jira tracking, deployment pipelines, and more.

## Structure

```
engineering-workflows/
├── agents/
│   ├── create_azure_pr/                    # Create Azure DevOps PRs with Jira enrichment
│   │   ├── create_azure_pr.md              # Agent definition (for Kiro/Claude)
│   │   └── scripts/
│   │       ├── fetch_jira_ticket_title.py  # Resolves PR title from Jira ticket
│   │       └── create_azure_devops_pr.py   # Creates the PR on Azure DevOps
│   ├── list_assigned_jira_tickets/         # List and spotlight Jira tickets by user
│   │   ├── list_assigned_jira_tickets.md   # Agent definition (for Kiro/Claude)
│   │   └── scripts/
│   │       └── list_assigned_jira_tickets.py
│   └── merge_pr_and_trigger_pipeline/      # Merge PRs and trigger release pipeline
│       ├── merge_pr_and_trigger_pipeline.md # Agent definition (for Kiro/Claude)
│       └── scripts/
│           └── merge_pr_and_trigger_pipeline.py
├── shared/                                 # Shared Python utilities
│   ├── __init__.py
│   ├── azure_devops_client.py              # Azure DevOps API wrapper
│   ├── jira_client.py                      # Jira API wrapper
│   ├── git_utils.py                        # Git helpers
│   └── env.py                              # Environment/credential loader
├── setup_agents.sh                         # Link agents to Kiro/Claude and write .workflow_env
├── .env.example                            # Credential template — copy to .env
└── requirements.txt                        # Python dependencies
```

## Quick start

### 1. Install Python via uv

This project uses [uv](https://docs.astral.sh/uv/) for fast, reproducible Python environment management.

```bash
# Install uv if you don't have it
pip install uv
# or via Homebrew
brew install uv
```

### 2. Create and activate the virtual environment

```bash
# Create a venv (Python 3.9+)
uv venv .venv

# Activate it
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
uv pip install -r requirements.txt
```

### 4. Link agents to Kiro and Claude

Run the setup script once to hard-link agent definitions and write the shared `~/.workflow_env` file:

```bash
chmod +x setup_agents.sh
./setup_agents.sh
```

This will:
- Write `~/.workflow_env` with `WORKFLOW_REPO_ROOT` and `WORKFLOW_PYTHON` pointing at this repo's venv
- Hard-link all agent `.md` files to `~/.kiro/agents/` (Kiro picks up `.md` files automatically)
- Symlink all agent `.md` files to `~/.claude/agents/` (Claude Code)

Re-run `setup_agents.sh` whenever you add a new agent or move the repo.

### 5. Configure credentials

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:

| Variable | Used by | Related agents |
|---|---|---|
| `JIRA_DOMAIN` | Jira client | create_azure_pull_request, list_assigned_jira_tickets |
| `JIRA_EMAIL` | Jira client | create_azure_pull_request, list_assigned_jira_tickets |
| `JIRA_API_TOKEN` | Jira client | create_azure_pull_request, list_assigned_jira_tickets |
| `AZURE_DEVOPS_PAT` | Azure DevOps client | create_azure_pull_request, merge_pr_and_trigger_pipeline |
| `AZURE_ORG` | Azure DevOps client | create_azure_pull_request, merge_pr_and_trigger_pipeline |
| `DEFAULT_TARGET` | PR target branch | create_azure_pull_request |

---

## Agents

### create_azure_pull_request

Creates Azure DevOps pull requests with full pre-flight checks:
- Ensures changes are committed (auto-commits if needed)
- Rebases source onto the target branch
- Handles merge conflicts interactively (choose ours / theirs / manual per file)
- Builds a rich PR description from Jira ticket info and commit history

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `source_branch` | No | current branch | Branch to create the PR from |
| `target_branch` | No | `release_candidate` | Branch to merge into |
| `comment` | No | — | Commit message for uncommitted changes and fallback PR title |
| `jira_ticket_key` | No | auto-detected | Explicit Jira ticket key (e.g. `PROJ-123`) — skips branch/log scan |
| `rebase_source_with_target_branch` | No | `true` | Rebase source onto `origin/<target_branch>` before pushing |

---

### list_assigned_jira_tickets

Lists Jira tickets assigned to one or more users, grouped by **User → Project**, sorted by priority. Includes a dedicated spotlight section at the bottom highlighting tickets updated within a configurable recent window.

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `days` | No | `30` | How many days back to look for tickets |
| `highlight_days` | No | `1` | Spotlight window for recently updated tickets (default: last 24 h) |
| `user` | No | `currentUser()` | Space-separated user emails / IDs |
| `status` | No | `"To Do" "In Progress"` | Space-separated statuses. Pass `all` to skip filtering |
| `project` | No | all projects | Space-separated Jira project keys (e.g. `PROJ INFRA`) |

Natural-language time expressions are supported — e.g. *"last 2 weeks"* maps to `--days 14`.

**Output format:** a two-level table (User → Project → Tickets) followed by a `⚡ RECENT ACTIVITY SPOTLIGHT` section. Output is printed verbatim from the script — no summarising or reformatting.

---

### merge_pr_and_trigger_pipeline

Approves and squash-merges one or more Azure DevOps pull requests, then triggers the release pipeline — all in a single automated run.

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `pr_urls` | **Yes** | — | One or more space-separated Azure DevOps PR URLs |
| `branch` | No | `release_candidate` | Pipeline trigger branch after merge |
| `no_pipeline` | No | `false` | Skip the pipeline trigger (e.g. *"just merge"*) |
| `delete_source` | No | `false` | Delete the source branch after merge (e.g. *"clean up branch"*) |

Natural-language intent is supported — e.g. *"just merge, don't trigger pipeline, and clean up the branch"* maps to `--no-pipeline --delete-source`.

---

## Shared utilities

All agents share the same Python utilities under `shared/`:

| Module | Purpose |
|---|---|
| `azure_devops_client.py` | Azure DevOps REST API wrapper (PRs, pipelines) |
| `jira_client.py` | Jira Atlassian Cloud REST API wrapper |
| `git_utils.py` | Git helpers (branch detection, rebase, push) |
| `env.py` | Credential loader — env var > `.env` file > fallback |

Credentials are resolved in this order: **environment variable → `.env` file → explicit fallback**. No script will prompt for credentials.
