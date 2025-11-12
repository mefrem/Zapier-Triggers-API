#!/bin/bash
# Script to run tests with correct PYTHONPATH

cd "$(dirname "$0")"
export PYTHONPATH="$PWD/src:$PYTHONPATH"
python -m pytest "$@"
