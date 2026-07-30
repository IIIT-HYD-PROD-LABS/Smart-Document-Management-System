#!/usr/bin/env bash
# Push backend/ subtree to Taxsync_Backend (gh-backend) staging branch.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git fetch gh-backend staging 2>/dev/null || true
BRANCH="backend-staging-export-$(date +%Y%m%d%H%M%S)"
git subtree split --prefix=backend -b "$BRANCH"
git push gh-backend "${BRANCH}:staging" --force-with-lease
git branch -D "$BRANCH"
echo "Pushed backend/ -> gh-backend staging"
