#!/bin/bash
# Unix/Linux/macOS script to run the Forensic Triage Agent
# Usage: ./run.sh [--dry-run|--sample|--input FILE|--output FILE]

# Activate virtual environment
source venv/bin/activate

# Run the agent
python main.py "$@"

# Deactivate on exit
deactivate
