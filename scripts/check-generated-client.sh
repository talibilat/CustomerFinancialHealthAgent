#!/bin/sh

set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_directory=$(CDPATH= cd -- "$script_directory/.." && pwd)

(
  cd "$repository_directory/backend"
  PYTHONPATH=src uv run --frozen export-openapi
)

(
  cd "$repository_directory/frontend"
  npm run generate-client
)

git -C "$repository_directory" diff --exit-code -- \
  backend/openapi.json \
  frontend/src/api/generated

untracked_files=$(git -C "$repository_directory" ls-files \
  --others \
  --exclude-standard \
  -- backend/openapi.json frontend/src/api/generated)

if [ -n "$untracked_files" ]; then
  echo "Generated client contains uncommitted files:"
  echo "$untracked_files"
  exit 1
fi
