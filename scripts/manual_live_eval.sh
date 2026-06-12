#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
STAMP="$(date +%Y%m%d_%H%M%S)"
SAFE_STAMP="${STAMP//_/}"
WORK_DIR="${TMPDIR:-/tmp}/prompterkit-live-eval-${STAMP}"
SCRIPT_FILE="${WORK_DIR}/live-eval-script.txt"
PULLED_FILE="${WORK_DIR}/pulled.txt"
BACKUP_FILE="${WORK_DIR}/backup.zip"
SCRIPT_NAME="PrompterKit Live Eval ${SAFE_STAMP}"

mkdir -p "${WORK_DIR}"
cat > "${SCRIPT_FILE}" <<EOF
PrompterKit live eval line one ${SAFE_STAMP}
PrompterKit live eval line two ${SAFE_STAMP}
EOF

echo "Working directory: ${WORK_DIR}"
echo "1. Running doctor before live mutation."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" doctor

echo "2. Backing up live Camera Hub data."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" backup --output "${BACKUP_FILE}"

echo "3. Pushing timestamped script with Camera Hub restart."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" push "${SCRIPT_FILE}" --name "${SCRIPT_NAME}" --restart

echo "4. Pulling the script back by name."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" pull --name "${SCRIPT_NAME}" --output "${PULLED_FILE}"

echo "5. Comparing pushed and pulled text."
cmp "${SCRIPT_FILE}" "${PULLED_FILE}"

echo "6. Stopping Camera Hub before cleanup delete."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" camerahub stop

echo "7. Deleting the live eval script."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" delete "${SCRIPT_NAME}"

echo "8. Running doctor after cleanup."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" doctor

echo "9. Restarting Camera Hub after live eval."
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit.py" camerahub start

echo "Live eval passed. Backup: ${BACKUP_FILE}"
