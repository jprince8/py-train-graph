#!/usr/bin/env bash

# Variables
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PYTHON_CMD="python3"
VENV_DIR=".venv"

# Create and activate a Python virtual environment if it doesn't exist
if [[ ! -d "$SCRIPT_DIR/$VENV_DIR" ]]; then
  $PYTHON_CMD -m venv "$SCRIPT_DIR/$VENV_DIR"
fi

# Activate the virtual environment
source "$SCRIPT_DIR/$VENV_DIR/bin/activate"

# Check if the source command was successful
if [[ $? -ne 0 ]]; then
  echo "Failed to activate the virtual environment."
  exit 1
fi

# Install necessary packages if requirements.txt exists
if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
  pip install -r "$SCRIPT_DIR/requirements.txt" 2>&1 | grep -v 'Requirement already satisfied'
fi

# Get the script name and remove .py extension if present
PYTHON_SCRIPT="py_train_graph.py"
shift

# Check if the specified script exists with or without the .py extension
if [[ -f "$SCRIPT_DIR/$PYTHON_SCRIPT" ]]; then
  FULL_SCRIPT_PATH="$SCRIPT_DIR/$PYTHON_SCRIPT"
elif [[ -f "$SCRIPT_DIR/$PYTHON_SCRIPT.py" ]]; then
  FULL_SCRIPT_PATH="$SCRIPT_DIR/$PYTHON_SCRIPT.py"
else
  echo "Error: Script '$PYTHON_SCRIPT' not found in $SCRIPT_DIR"
  exit 1
fi

# Run the specified Python script with any additional arguments passed to this script
$PYTHON_CMD "$FULL_SCRIPT_PATH" "$@"
