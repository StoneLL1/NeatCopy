#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}"
PYTHON="${ROOT_DIR}/.venv/bin/python"
VERSION="$("${PYTHON}" -c 'import sys; sys.path.insert(0, "src"); from version import VERSION; print(VERSION)')"
BUILD_DIR="${ROOT_DIR}/build-macos"
DIST_DIR="${ROOT_DIR}/dist-macos"
DMG_ROOT="${BUILD_DIR}/dmg-root"
OUTPUT_DIR="${ROOT_DIR}/release-macos"
DMG_PATH="${OUTPUT_DIR}/NeatCopy-${VERSION}-macOS-arm64.dmg"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Missing ${PYTHON}; create the project virtualenv and install requirements first." >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"
rm -rf "${BUILD_DIR}" "${DIST_DIR}" "${DMG_ROOT}"

"${PYTHON}" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "${DIST_DIR}" \
  --workpath "${BUILD_DIR}/pyinstaller" \
  "${ROOT_DIR}/NeatCopy-macos.spec"

# PyInstaller's default ad-hoc signature derives its designated requirement
# from the binary CDHash. That hash changes on every build and invalidates the
# user's existing Accessibility grant after an in-place update. Keep the
# outer app's designated requirement stable until a Developer ID certificate
# is available; nested frameworks are already signed by PyInstaller.
codesign \
  --force \
  --sign - \
  --identifier "com.stonell1.neatcopy" \
  --requirements '=designated => identifier "com.stonell1.neatcopy"' \
  "${DIST_DIR}/NeatCopy.app"
codesign --verify --deep --strict --verbose=2 "${DIST_DIR}/NeatCopy.app"
DESIGNATED_REQUIREMENT="$(codesign -d -r- "${DIST_DIR}/NeatCopy.app" 2>&1)"
if [[ "${DESIGNATED_REQUIREMENT}" != *'designated => identifier "com.stonell1.neatcopy"'* ]]; then
  echo "Unexpected code-signing requirement: ${DESIGNATED_REQUIREMENT}" >&2
  exit 1
fi

mkdir -p "${DMG_ROOT}"
cp -R "${DIST_DIR}/NeatCopy.app" "${DMG_ROOT}/NeatCopy.app"
ln -s /Applications "${DMG_ROOT}/Applications"

rm -f "${DMG_PATH}"
hdiutil create \
  -volname "NeatCopy ${VERSION}" \
  -srcfolder "${DMG_ROOT}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

echo "Created ${DMG_PATH}"
