#!/usr/bin/env bash
set -e

# Determine the repo root (this script lives in the root)
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Run the launcher script directly in this terminal
cd "$ROOT"
./scripts/launch-train-graph.sh
