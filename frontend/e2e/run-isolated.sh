#!/bin/sh

set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_directory=$(CDPATH= cd -- "$script_directory/../.." && pwd)
compose_project=${E2E_COMPOSE_PROJECT_NAME:-cfha-e2e}
backend_port=${E2E_BACKEND_PORT:-18000}
frontend_port=${E2E_FRONTEND_PORT:-15173}

compose() {
  docker compose \
    --project-name "$compose_project" \
    --file "$repository_directory/docker-compose.yml" \
    --file "$repository_directory/docker-compose.e2e.yml" \
    "$@"
}

cleanup() {
  compose down --volumes --remove-orphans
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cleanup

BACKEND_PORT="$backend_port" FRONTEND_PORT="$frontend_port" \
  compose up --build --detach --wait

PLAYWRIGHT_BASE_URL="http://localhost:$frontend_port" \
PLAYWRIGHT_API_BASE_URL="http://localhost:$backend_port" \
  npx playwright test "$@"
