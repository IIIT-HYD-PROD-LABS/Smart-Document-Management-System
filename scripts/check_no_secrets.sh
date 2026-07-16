#!/usr/bin/env bash
# Fail if tracked files look like they contain live secrets.
# Used by CI and as a pre-push sanity check.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

FAIL=0

# 1) Forbidden tracked paths
FORBIDDEN=(
  ".env"
  ".env.prod"
  ".env.bak"
  ".env.local"
  ".env.production"
  "docker-compose.override.yml"
  "docker-compose.override.yaml"
)
for f in "${FORBIDDEN[@]}"; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo "FAIL: tracked forbidden file: $f"
    FAIL=1
  fi
done

# 2) Build list of tracked files that may hold secrets (config/code only).
# Skip docs, notes, planning, examples, tests, binary-ish, this script.
mapfile -t CANDIDATES < <(
  git ls-files \
    | grep -E '\.(ya?ml|yml|toml|ini|cfg|env|py|ts|tsx|js|jsx|sh|json|service)$' \
    | grep -Ev '(^|/)(\.env\.example|\.env\.prod\.example)$' \
    | grep -Ev '(^|/)backend/\.env\.example$' \
    | grep -Ev '(^|/)(docs|notes|\.planning)/' \
    | grep -Ev '(^|/)backend/tests/' \
    | grep -Ev '(^|/)scripts/check_no_secrets\.sh$' \
    | grep -Ev '(^|/)\.github/workflows/' \
    || true
)

if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
  echo "Secret scan: no candidate files (unexpected)."
  exit 1
fi

# Patterns: high confidence live secrets only. Placeholders with xxxx / CHANGE_ME
# and env-interpolation ${VAR} are not matched by design.
PATTERNS=(
  'AIza[0-9A-Za-z_-]{30,}'
  're_[A-Za-z0-9]{30,}'
  'sk-[A-Za-z0-9]{32,}'
  'ghp_[A-Za-z0-9]{20,}'
  'SECRET_KEY:[[:space:]]*[A-Za-z0-9_=-]{40,}'
  'FERNET_KEY:[[:space:]]*[A-Za-z0-9_=-]{40,}'
  'SMTP_PASSWORD:[[:space:]]*[A-Za-z0-9._-]{12,}'
  'postgresql://[A-Za-z0-9_.-]+:[^@${[:space:]/"]{8,}@'
)

for pat in "${PATTERNS[@]}"; do
  # grep -n across candidate list; ignore exit 1 = no match
  if matches=$(grep -nIE "$pat" "${CANDIDATES[@]}" 2>/dev/null || true); then
    if [[ -n "${matches}" ]]; then
      # Drop obvious placeholders
      filtered=$(printf '%s\n' "$matches" | grep -Ev 'CHANGE_ME|your-|xxxx|example\.com|placeholder|\*\*\*' || true)
      if [[ -n "${filtered}" ]]; then
        echo "FAIL: pattern /$pat/ matched tracked content:"
        echo "$filtered" | head -40
        FAIL=1
      fi
    fi
  fi
done

if [[ "$FAIL" -ne 0 ]]; then
  echo ""
  echo "Secret scan FAILED. Remove secrets from the commit, put them in"
  echo "server-local .env.prod (gitignored), and see docs/security/SECRET_ROTATION_2026-07-16.md"
  exit 1
fi

echo "Secret scan OK (${#CANDIDATES[@]} files checked; no forbidden paths / live patterns)."
exit 0
