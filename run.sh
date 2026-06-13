#!/bin/bash
# ──────────────────────────────────────────────
# Smart Recycling Bin - Launch Script
# Usage:
#   Terminal: bash run.sh
#   GUI double-click: grant execute permission first
#     (once: chmod +x run.sh)
# ──────────────────────────────────────────────

# Move to the directory where this script is located
cd "$(dirname "$0")"

VENV_PATH="./venv/bin/activate"
PYTHON_SCRIPT="test_cam.py"

# Check if virtual environment exists
if [ ! -f "$VENV_PATH" ]; then
    echo "[ERROR] Virtual environment not found: $VENV_PATH"
    echo "        Create one first: python3 -m venv venv"
    read -p "Press Enter to close..."
    exit 1
fi

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "[ERROR] Script not found: $PYTHON_SCRIPT"
    read -p "Press Enter to close..."
    exit 1
fi

echo "========================================="
echo "  Smart Recycling Bin - Starting"
echo "========================================="
echo "[VENV]   Activating $VENV_PATH ..."

# Activate virtual environment
source "$VENV_PATH"

echo "[PYTHON] $(python --version)"
echo "[RUN]    $PYTHON_SCRIPT"
echo "-----------------------------------------"

# Run the main script
python "$PYTHON_SCRIPT"

EXIT_CODE=$?

echo "-----------------------------------------"
if [ $EXIT_CODE -eq 0 ]; then
    echo "[DONE] Program exited normally."
else
    echo "[ERROR] Program exited abnormally. (exit code: $EXIT_CODE)"
fi

# Prevent terminal from closing immediately on GUI double-click
read -p "Press Enter to close..."
