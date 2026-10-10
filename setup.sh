#!/usr/bin/env bash
# One-time setup: creates .venv and installs dependencies.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
echo "Done. Activate with: source .venv/bin/activate"
