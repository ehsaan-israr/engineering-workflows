#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
REPO_AGENTS="$SCRIPT_DIR/agents"
KIRO_DIR="$HOME/.kiro/agents"
CLAUDE_DIR="$HOME/.claude/agents"

mkdir -p "$KIRO_DIR" "$CLAUDE_DIR"

# 1. Write the exact REPO_ROOT into a shared environment file
cat <<EOF > "$HOME/.workflow_env"
export WORKFLOW_REPO_ROOT="$SCRIPT_DIR"
export WORKFLOW_PYTHON="$SCRIPT_DIR/.venv/bin/python"
export PYTHONPATH="\$WORKFLOW_REPO_ROOT:\$PYTHONPATH"
EOF
echo "✔ Updated global environment file at $HOME/.workflow_env"

# 2. Link agents for Kiro and Claude
echo "Scanning $REPO_AGENTS..."
find "$REPO_AGENTS" -mindepth 2 -name "*.md" | while read -r md_file; do
  md_name=$(basename "$md_file")
  agent_name="${md_name%.md}"

  # Remove existing symlinks if they exist
  rm -f "$KIRO_DIR/$md_name" "$CLAUDE_DIR/$agent_name"

  # Use a HARD LINK for Kiro (looks like a normal file to Kiro's scanner, but syncs edits automatically)
  # If on different drives/filesystems where hard links fail, fallback to regular copy (cp -f)
  ln -f "$md_file" "$KIRO_DIR/$md_name" 2>/dev/null || cp -f "$md_file" "$KIRO_DIR/$md_name"
  echo "✔ [Kiro] Hard linked/Copied $md_name → $KIRO_DIR/$md_name"

  # Claude Code supports standard symlinks fine
  ln -sfn "$md_file" "$CLAUDE_DIR/$agent_name"
  echo "✔ [Claude] Linked $md_name → $CLAUDE_DIR/$agent_name"
done