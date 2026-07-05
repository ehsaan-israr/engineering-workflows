# engineering-workflows

A structured collection of AI agents, scripts, and shared utilities for automating engineering workflows — PR creation, branch management, Jira enrichment, and more.

## Structure

```
engineering-workflows/
├── agents/
│   └── create_azure_pr/             # Create Azure DevOps PRs with Jira enrichment
│       ├── create_azure_pr.md       # Agent definition (for Kiro/Claude)
│       └── scripts/                 # Python scripts for PR creation and Jira lookup
│           ├── fetch_jira_ticket_title.py
│           └── create_azure_devops_pr.py
├── shared/                          # Shared Python utilities
│   ├── __init__.py
│   ├── azure_devops_client.py       # Azure DevOps API wrapper
│   ├── jira_client.py               # Jira API wrapper
│   ├── git_utils.py                 # Git helpers
│   └── env.py                       # Environment/credential loader
├── setup_agents.sh                  # Symlink agents to Kiro/Claude and setup .workflow_env
├── .env.example                     # Credential template — copy to .env
└── requirements.txt                 # Python dependencies
```

## Quick start

### 1. Install Python 3.14 via uv

This project uses [uv](https://docs.astral.sh/uv/) for fast, reproducible Python environment management.

```bash
# Install uv if you don't have it
pip install uv
# or via Homebrew
brew install uv
```

### 2. Create and activate the virtual environment

```bash
# Create a venv pinned to Python 3.14
uv venv --python 3.14 .venv

# Activate it
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
uv pip install -r requirements.txt
```

### 4. Link agents to Kiro and Claude

Run the setup script to symlink agent definitions to Kiro and Claude:

```bash
chmod +x setup_agents.sh
./setup_agents.sh
```

This will:
- Create `~/.workflow_env` with repo path and Python binary
- Symlink all agents to `~/.kiro/agents/` (Kiro picks up `.md` files)
- Symlink agents to `~/.claude/agents/` (Claude Code)

### 5. Configure credentials

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:

| Variable | Used by | Related Agent |
|----------|---------|---------------|
| `JIRA_DOMAIN` | Jira client | create_azure_pull_request |
| `JIRA_EMAIL` | Jira client | create_azure_pull_request |
| `JIRA_API_TOKEN` | Jira client | create_azure_pull_request |
| `AZURE_DEVOPS_PAT` | Azure DevOps client | create_azure_pull_request |
| `AZURE_ORG` | Azure DevOps client | create_azure_pull_request |
| `DEFAULT_TARGET` | PR target branch | create_azure_pull_request |

---

## Agents

### create_azure_pull_request

Creates Azure DevOps pull requests with full pre-flight checks:
- Ensures changes are committed
- Rebases source onto target branch
- Handles merge conflicts interactively
- Builds PR description from Jira ticket and commit history

**Usage in Kiro/Claude:**
Invoke the `create_azure_pr` agent with optional inputs:
- `source_branch` — branch to create PR from (defaults to current)
- `target_branch` — branch to merge into (default: `release_candidate`)
- `comment` — commit message for uncommitted changes
- `jira_ticket_key` — explicit Jira ticket key (skips auto-detection)
- `rebase_source_with_target_branch` — whether to rebase (default: `true`)

Internally uses:
- `fetch_jira_ticket_title.py` — resolves PR title from Jira
- `create_azure_devops_pr.py` — creates the PR on Azure DevOps
