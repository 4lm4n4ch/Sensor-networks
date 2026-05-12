#!/usr/bin/env bash
set -euo pipefail

# run_tests.sh - Run the project's test suite using the project's virtualenv if present.
# Usage: ./run_tests.sh [pytest-args]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$ROOT_DIR/.venv/bin/python"

if [ -x "$VENV_PY" ]; then
  PYTHON="$VENV_PY"
else
  PYTHON="$(command -v python3 || command -v python)"
fi

echo "Using Python: $PYTHON"
exec "$PYTHON" -m pytest -q "$@"
