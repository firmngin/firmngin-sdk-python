#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

TARGET="${1:-pypi}"

if [[ "$TARGET" == "test" || "$TARGET" == "testpypi" ]]; then
  export TWINE_REPOSITORY=testpypi
  export TWINE_PASSWORD="${TESTPYPI_TOKEN:-${TWINE_PASSWORD:-}}"
  PYPI_INDEX="https://test.pypi.org/pypi"
else
  unset TWINE_REPOSITORY
  export TWINE_PASSWORD="${PYPI_TOKEN:-${TWINE_PASSWORD:-}}"
  PYPI_INDEX="https://pypi.org/pypi"
fi

export TWINE_USERNAME="${TWINE_USERNAME:-__token__}"

if [[ -z "${TWINE_PASSWORD:-}" ]]; then
  echo "error: set PYPI_TOKEN atau TWINE_PASSWORD di .env (TESTPYPI_TOKEN untuk test)" >&2
  exit 1
fi

for cmd in python perl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: '$cmd' tidak ditemukan" >&2
    exit 1
  fi
done

python -m pip install -q -U "build>=1.2" "twine>=6.1" "packaging>=24.2"

read_version() {
  grep -E '^version\s*=' pyproject.toml | head -1 | sed -E 's/^version\s*=\s*"([^"]+)".*/\1/'
}

sync_version() {
  local ver="$1"
  perl -pi -e "s/^version = \".*\"/version = \"${ver}\"/" pyproject.toml
  perl -pi -e "s/^__version__ = \".*\"/__version__ = \"${ver}\"/" src/firmngin/_version.py
}

validate_version() {
  local ver="$1"
  [[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][a-zA-Z0-9]+)*$ ]]
}

version_exists_on_index() {
  local ver="$1"
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "${PYPI_INDEX}/${PKG_NAME}/${ver}/json" || true)"
  [[ "$code" == "200" ]]
}

PKG_NAME="$(grep -E '^name\s*=' pyproject.toml | head -1 | sed -E 's/^name\s*=\s*"([^"]+)".*/\1/')"
PKG_VERSION="$(read_version)"
SRC_VERSION="$(grep -E '^__version__\s*=' src/firmngin/_version.py | sed -E 's/.*"([^"]+)".*/\1/')"

if [[ "$PKG_VERSION" != "$SRC_VERSION" ]]; then
  echo "peringatan: versi tidak sinkron — pyproject.toml ($PKG_VERSION) vs _version.py ($SRC_VERSION)" >&2
fi

if [[ "$TARGET" == "test" || "$TARGET" == "testpypi" ]]; then
  DEST="TestPyPI"
else
  DEST="PyPI"
fi

echo ""
echo "  Package : ${PKG_NAME}"
echo "  Versi   : ${PKG_VERSION}"
echo "  Target  : ${DEST}"
echo ""
read -r -p "Versi saat ini: ${PKG_VERSION}. Enter = pakai ini, atau ketik versi baru: " INPUT_VERSION

if [[ -n "$INPUT_VERSION" ]]; then
  if ! validate_version "$INPUT_VERSION"; then
    echo "error: format versi tidak valid (contoh: 0.0.2 atau 1.0.0rc1)" >&2
    exit 1
  fi
  if [[ "$INPUT_VERSION" != "$PKG_VERSION" ]]; then
    sync_version "$INPUT_VERSION"
    PKG_VERSION="$INPUT_VERSION"
    echo "versi disinkronkan ke pyproject.toml dan src/firmngin/_version.py"
  fi
fi

if version_exists_on_index "$PKG_VERSION"; then
  echo "error: versi ${PKG_VERSION} sudah ada di ${DEST} — bump versi dulu" >&2
  exit 1
fi

echo ""
read -r -p "Lanjut build dan upload versi ${PKG_VERSION} ke ${DEST}? [y/N] " CONFIRM
CONFIRM="$(echo "$CONFIRM" | tr '[:upper:]' '[:lower:]')"
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "ya" ]]; then
  echo "Dibatalkan."
  exit 0
fi

rm -rf dist/ build/ *.egg-info src/*.egg-info
python -m build
twine check dist/*

if [[ "$TARGET" == "test" || "$TARGET" == "testpypi" ]]; then
  echo "mengunggah ke TestPyPI..."
  twine upload --verbose --repository testpypi dist/*
else
  echo "mengunggah ke PyPI..."
  twine upload --verbose dist/*
fi

echo "selesai."
