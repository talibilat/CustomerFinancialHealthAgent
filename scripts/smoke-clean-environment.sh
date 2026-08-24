#!/bin/sh

set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_directory=$(CDPATH= cd -- "$script_directory/.." && pwd)
compose_project=${SMOKE_COMPOSE_PROJECT_NAME:-cfha-clean-smoke}
backend_port=${SMOKE_BACKEND_PORT:-18001}
frontend_port=${SMOKE_FRONTEND_PORT:-15174}
temporary_directory=$(mktemp -d)

compose() {
  docker compose \
    --project-name "$compose_project" \
    --file "$repository_directory/docker-compose.yml" \
    --file "$repository_directory/docker-compose.e2e.yml" \
    "$@"
}

compose_cleanup() {
  compose down --volumes --remove-orphans
}

cleanup() {
  compose_cleanup
  rm -rf "$temporary_directory"
}

fail() {
  echo "Clean-environment smoke failed: $1" >&2
  exit 1
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

compose_cleanup

BACKEND_PORT="$backend_port" FRONTEND_PORT="$frontend_port" \
  compose up --build --detach --wait

ready_url="http://localhost:$backend_port/health/ready"
live_url="http://localhost:$backend_port/health/live"
overview_url="http://localhost:$backend_port/overview"

curl -fsS "$live_url" | grep -q '"status":"ok"' || fail "liveness did not report ok"
curl -fsS "$ready_url" > "$temporary_directory/ready.json"
grep -q '"status":"ready"' "$temporary_directory/ready.json" || fail "readiness did not report ready"
grep -q '"database":"ok"' "$temporary_directory/ready.json" || fail "database was not ready"
grep -q '"classification_suggestions":"not_configured"' "$temporary_directory/ready.json" || fail "classification unexpectedly requires Azure"
grep -q '"personalized_guidance":"not_configured"' "$temporary_directory/ready.json" || fail "guidance unexpectedly requires Azure"

curl -fsS "$overview_url" > "$temporary_directory/overview-before.json"
compose run --rm migrate
curl -fsS "$overview_url" > "$temporary_directory/overview-after-seed.json"
cmp "$temporary_directory/overview-before.json" "$temporary_directory/overview-after-seed.json" >/dev/null || fail "idempotent seed changed the fictional aggregate"

compose restart db
BACKEND_PORT="$backend_port" FRONTEND_PORT="$frontend_port" compose up --detach --wait db
compose restart backend
BACKEND_PORT="$backend_port" FRONTEND_PORT="$frontend_port" compose up --detach --wait backend
curl -fsS "$overview_url" > "$temporary_directory/overview-after-restart.json"
cmp "$temporary_directory/overview-before.json" "$temporary_directory/overview-after-restart.json" >/dev/null || fail "restart did not preserve stored data"

compose exec -T db psql -U financial_health -d financial_health \
  -c "update alembic_version set version_num = 'reviewer_schema_mismatch'" >/dev/null

status=$(curl -sS -o "$temporary_directory/mismatch.json" -w '%{http_code}' "$ready_url")
[ "$status" = "503" ] || fail "schema mismatch did not make readiness return 503"
grep -q '"database":"schema_mismatch"' "$temporary_directory/mismatch.json" || fail "schema mismatch was not identified"
curl -fsS "$live_url" | grep -q '"status":"ok"' || fail "liveness should remain independent of readiness"

if compose run --rm migrate > "$temporary_directory/expected-migration-failure.log" 2>&1; then
  fail "migration unexpectedly accepted an unknown database revision"
fi

echo "Clean-environment smoke passed."
