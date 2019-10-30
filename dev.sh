#!/usr/bin/env bash

# Get virtual environment
old_pwd=$PWD
cd "$(dirname "$0")" || exit 1
venv=$(realpath "$(pipenv --venv)")

# Add current directory to PYTHONPATH
PYTHONPATH="$(realpath .):$PYTHONPATH"
export PYTHONPATH

# Run MLSP from original dir and within environment
# shellcheck source=/dev/null
source "$venv/bin/activate"
cd "$old_pwd" || exit 1
python -m mlsp "$@"
