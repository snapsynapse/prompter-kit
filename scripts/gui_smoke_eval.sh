#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-5057}"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/prompterkit-gui-eval.XXXXXX")"
SERVER_LOG="${WORK_DIR}/server.log"
EXPORT_ZIP="${WORK_DIR}/export.zip"

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        kill "${SERVER_PID}" 2>/dev/null || true
        wait "${SERVER_PID}" 2>/dev/null || true
    fi
    rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

cp "${ROOT_DIR}/tests/fixtures/camerahub/current/AppSettings.json" "${WORK_DIR}/"
cp -R "${ROOT_DIR}/tests/fixtures/camerahub/current/Texts" "${WORK_DIR}/"

echo "Starting GUI against fixture copy: ${WORK_DIR}"
PROMPTERKIT_BASE_DIR="${WORK_DIR}" \
PROMPTERKIT_OPEN_BROWSER=0 \
PORT="${PORT}" \
"${PYTHON_BIN}" "${ROOT_DIR}/prompter_kit_gui.py" >"${SERVER_LOG}" 2>&1 &
SERVER_PID="$!"

for _ in {1..30}; do
    if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

curl -fsS "http://127.0.0.1:${PORT}/" | grep -q "Fixture Alpha"
curl -fsS "http://127.0.0.1:${PORT}/" | grep -q "Fixture Beta"
curl -fsS "http://127.0.0.1:${PORT}/export-all" -o "${EXPORT_ZIP}"

"${PYTHON_BIN}" - "${EXPORT_ZIP}" <<'PY'
import sys
import zipfile

archive = sys.argv[1]
with zipfile.ZipFile(archive) as zf:
    names = sorted(zf.namelist())
    assert names == ["Fixture_Alpha.txt", "Fixture_Beta.txt"], names
    assert zf.read("Fixture_Alpha.txt").decode("utf-8") == "Alpha line one\nAlpha line two\n"
    assert zf.read("Fixture_Beta.txt").decode("utf-8") == "Beta line one\n"
PY

echo "GUI smoke eval passed on http://127.0.0.1:${PORT}"
