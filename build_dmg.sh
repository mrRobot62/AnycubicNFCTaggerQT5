#!/usr/bin/env bash
# build_dmg.sh — Clean build a macOS .app via cx_Freeze and create a DMG via dmgbuild.

set -euo pipefail

# --- Configuration ------------------------------------------------------------
PYTHON_BIN="${PYTHON_BIN:-python}"   # allow override: PYTHON_BIN=/usr/bin/python3 ./build_dmg.sh
DMG_NAME="${DMG_NAME:-AnycubicNFCTaggerQT5}"
DMG_SETTINGS="${DMG_SETTINGS:-packaging/macos/dmg_settings.py}"   # your existing settings file
APP_BUNDLE_NAME="${APP_BUNDLE_NAME:-AnycubicNFCTaggerQT5.app}"    # final name after build (we’ll auto-detect if different)
# Try to read version from pyproject; falls back to 0.3.0
VERSION="${VERSION:-$(${PYTHON_BIN} - <<'PY' || true
import tomllib, sys, pathlib
try:
    data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
    print(data.get("project", {}).get("version", "0.3.0"))
except Exception:
    print("0.3.0")
PY
)}"
DIST_DIR="dist"
BUILD_DIR="build"
DMG_OUT="${DIST_DIR}/${DMG_NAME}-${VERSION}-arm64.dmg"

# --- Helpers -----------------------------------------------------------------

function info()  { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
function warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
function error() { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*" >&2; }

# --- Aggressive directory removal (handles locked files, attributes) ---------
force_remove_dir() {
  local dir="$1"
  if [[ ! -d "$dir" ]]; then
    return 0
  fi
  info "Attempting to remove '$dir' (aggressive)…"
  # Show first few lock holders (best-effort)
  command -v lsof >/dev/null 2>&1 && lsof +D "$dir" | head -n 50 || true
  # Release potential locks & attributes
  qlmanage -r cache >/dev/null 2>&1 || true
  xattr -rc "$dir" 2>/dev/null || true
  chmod -R u+w "$dir" 2>/dev/null || true
  chflags -R nouchg "$dir" 2>/dev/null || true
  # Retry loop for stubborn removals
  for i in {1..3}; do
    rm -rf "$dir" 2>/dev/null && return 0
    warn "rm -rf failed (attempt $i). Killing possible holders and retrying…"
    pkill -f AnycubicNFCTaggerQT5 >/dev/null 2>&1 || true
    sleep 0.5
  done
  # Fallback: rename then delete
  local tomb="${dir}._to_delete.$(date +%s)"
  mv "$dir" "$tomb" 2>/dev/null || true
  rm -rf "$tomb" 2>/dev/null || true
}

# --- Checks ------------------------------------------------------------------
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  error "Python not found (PYTHON_BIN=${PYTHON_BIN})."
  exit 1
fi
if ! ${PYTHON_BIN} -c "import cx_Freeze" >/dev/null 2>&1; then
  error "cx_Freeze is not installed in this Python environment."
  echo "Try: ${PYTHON_BIN} -m pip install -U cx_Freeze"
  exit 1
fi
if ! ${PYTHON_BIN} -c "import dmgbuild" >/dev/null 2>&1; then
  error "dmgbuild is not installed in this Python environment."
  echo "Try: ${PYTHON_BIN} -m pip install -U dmgbuild"
  exit 1
fi
if [[ ! -f "${DMG_SETTINGS}" ]]; then
  warn "DMG settings file not found at '${DMG_SETTINGS}'. The script will still try to run if settings auto-detect the .app."
fi

# --- Quit running app & release locks ---------------------------------------
info "Closing running app (if any) and releasing QuickLook cache…"
osascript -e 'quit app "AnycubicNFCTaggerQT5"' >/dev/null 2>&1 || true
pkill -f AnycubicNFCTaggerQT5 >/dev/null 2>&1 || true
qlmanage -r cache >/dev/null 2>&1 || true

# --- Clean build/ ------------------------------------------------------------
if [[ -d "${BUILD_DIR}" ]]; then
  info "Removing existing '${BUILD_DIR}'…"
  force_remove_dir "${BUILD_DIR}"
fi

# --- Build .app --------------------------------------------------------------
info "Building .app via cx_Freeze (bdist_mac)…"
${PYTHON_BIN} freeze_setup.py bdist_mac

# Detect produced .app name under build/
if [[ -d "${BUILD_DIR}" ]]; then
  # Prefer a properly cased app if present; otherwise pick first *.app
  if [[ -d "${BUILD_DIR}/${APP_BUNDLE_NAME}" ]]; then
    APP_PATH="${BUILD_DIR}/${APP_BUNDLE_NAME}"
  else
    # shellcheck disable=SC2012
    APP_CANDIDATE="$(cd "${BUILD_DIR}"; ls -1d *.app 2>/dev/null | head -n1 || true)"
    if [[ -z "${APP_CANDIDATE}" ]]; then
      error "No .app bundle found under '${BUILD_DIR}'. Build may have failed."
      exit 1
    fi
    APP_PATH="${BUILD_DIR}/${APP_CANDIDATE}"
  fi
else
  error "Build directory '${BUILD_DIR}' not found."
  exit 1
fi

info "Found app bundle: ${APP_PATH}"

# --- Prepare dist/ -----------------------------------------------------------
mkdir -p "${DIST_DIR}"

# --- Optional: codesign (commented out) --------------------------------------
# Uncomment and set your Developer ID to enable signing before DMG creation.
# IDENTITY="Developer ID Application: Your Name (TEAMID)"
# info "Codesigning app (deep)…"
# codesign --force --deep --options runtime --sign "${IDENTITY}" "${APP_PATH}"
# codesign --verify --deep --strict --verbose=2 "${APP_PATH}" || { error "Codesign verification failed"; exit 1; }

# --- Create DMG via dmgbuild -------------------------------------------------
info "Creating DMG via dmgbuild…"
${PYTHON_BIN} -m dmgbuild -s "${DMG_SETTINGS}" "${DMG_NAME}" "${DMG_OUT}"

info "DMG created at: ${DMG_OUT}"

# --- Optional: notarization (commented out) ----------------------------------
# AC_PROFILE: stored once via `xcrun notarytool store-credentials`
# info "Submitting for notarization…"
# xcrun notarytool submit "${DMG_OUT}" --keychain-profile "AC_PROFILE" --wait
# info "Stapling notarization ticket…"
# xcrun stapler staple "${DMG_OUT}"

info "Done. You can attach the DMG with:"
echo "  hdiutil attach \"${DMG_OUT}\""