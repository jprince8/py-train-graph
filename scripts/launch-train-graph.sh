#!/usr/bin/env bash
set -e

# Always run from repo root, even if launched from GUI
cd "$(dirname "$0")/.." || exit 1

VENV_DIR=".venv"

# 1. Create venv if needed and install package
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install -e .
else
  source "$VENV_DIR/bin/activate"
fi

# 2. Forward all args to CLI
py-train-graph "$@"
