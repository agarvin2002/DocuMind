#!/bin/sh
# Copy the pre-push hook into the local .git/hooks/ directory.
# Run once after cloning: sh scripts/install-hooks.sh
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_SRC="$REPO_ROOT/scripts/pre-push.sh"
HOOK_DST="$REPO_ROOT/.git/hooks/pre-push"

cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"

echo "✓ pre-push hook installed at $HOOK_DST"
