#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "❌ Không tìm thấy virtualenv tại $PROJECT_DIR/.venv"
    exit 1
fi

source "$PROJECT_DIR/.venv/bin/activate"

"$PYTHON" "$PROJECT_DIR/client/main.py"
