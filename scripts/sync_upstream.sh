#!/usr/bin/env bash
# ==============================================================================
# sync_upstream.sh — Pull latest features from upstream repository (nichsedge/idx-bei)
# ==============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "=== Syncing with Upstream (nichsedge/idx-bei) ==="

# Check if upstream remote exists, otherwise add it
if ! git remote get-url upstream >/dev/null 2>&1; then
    echo "Adding upstream remote: https://github.com/nichsedge/idx-bei.git"
    git remote add upstream https://github.com/nichsedge/idx-bei.git
fi

echo "1. Fetching latest changes from upstream..."
git fetch upstream main

echo "2. Merging upstream/main into current branch..."
CURRENT_BRANCH="$(git branch --show-current)"
git merge upstream/main -m "merge: sync updates from upstream/main"

echo "3. Pushing merged updates to your origin ($CURRENT_BRANCH)..."
git push origin "$CURRENT_BRANCH"

echo "4. Syncing Python dependencies via uv..."
uv sync

echo "=== Upstream Sync Complete! Coolify CI/CD will automatically redeploy. ==="
