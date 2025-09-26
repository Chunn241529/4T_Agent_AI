#!/bin/bash

# Lấy đường dẫn thư mục gốc dự án (nơi đặt script)
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Tìm Python trong .venv
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "❌ Không tìm thấy virtualenv tại $PROJECT_DIR/.venv"
    exit 1
fi

# Kích hoạt venv
source "$PROJECT_DIR/.venv/bin/activate"

# Chạy backend
"$PYTHON" "$PROJECT_DIR/backend/run.py"
