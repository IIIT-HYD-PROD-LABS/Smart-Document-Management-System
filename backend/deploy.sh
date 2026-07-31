#!/usr/bin/env bash
# Campus autotrigger entrypoint (Jenkins Stage_Taxsync_BE post-build).
# Builds image (optional), then starts smartdocs-backend with --env-file .env.
#
# Jenkins env (typical):
#   BUILD_NUMBER=42
#   DOCKER_IMAGE=tt0docker/stage_taxsync_be
# Optional:
#   SKIP_DOCKER_BUILD=1   — image already built in prior stage
#   SKIP_DOCKER_PULL=0    — set 1 if image was built locally on this host
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

TAG="${BUILD_NUMBER:-latest}"
IMAGE="${DOCKER_IMAGE:-tt0docker/stage_taxsync_be}:${TAG}"

if [[ ! -f .env ]]; then
  echo "ERROR: $ROOT/.env not found. Checkout Taxsync_Backend staging (tracked .env)." >&2
  exit 1
fi

if ! grep -q '^SECRET_KEY=.' .env || ! grep -q '^DATABASE_URL=.' .env; then
  echo "ERROR: .env must define SECRET_KEY and DATABASE_URL." >&2
  exit 1
fi

if [[ "${SKIP_DOCKER_BUILD:-0}" != "1" ]]; then
  echo "Building $IMAGE ..."
  docker build -t "$IMAGE" .
fi

if [[ "${SKIP_DOCKER_PULL:-0}" != "1" ]] && [[ "${SKIP_DOCKER_BUILD:-0}" == "1" ]]; then
  echo "Pulling $IMAGE ..."
  docker pull "$IMAGE"
fi

chmod +x scripts/run-backend-campus.sh
exec ./scripts/run-backend-campus.sh "$IMAGE"
