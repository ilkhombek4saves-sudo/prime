#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PRIME_INSTALL_BASE_URL:-https://wgrbojeweoginrb234.duckdns.org}"
BIN_URL="${PRIME_BIN_URL:-${BASE_URL%/}/prime}"
INSTALL_DIR="${PRIME_INSTALL_DIR:-$HOME/.local/bin}"
BIN_NAME="${PRIME_BIN_NAME:-prime}"
CURL_CONNECT_TIMEOUT="${PRIME_CURL_CONNECT_TIMEOUT:-10}"
CURL_MAX_TIME="${PRIME_CURL_MAX_TIME:-30}"
CURL_RETRY="${PRIME_CURL_RETRY:-2}"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/prime"
CONFIG_FILE="$CONFIG_DIR/config"

green() { printf '\033[92m%s\033[0m\n' "$*"; }
yellow() { printf '\033[93m%s\033[0m\n' "$*"; }
red() { printf '\033[91m%s\033[0m\n' "$*"; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    red "Missing required command: $1"
    exit 1
  fi
}

is_project_root() {
  local dir="$1"
  [ -f "$dir/docker-compose.yml" ] && [ -f "$dir/scripts/onboard.py" ]
}

write_prime_home_if_known() {
  local project_root="${PRIME_HOME:-}"
  if [ -z "$project_root" ] && is_project_root "$PWD"; then
    project_root="$PWD"
  fi
  if [ -z "$project_root" ]; then
    return 0
  fi
  mkdir -p "$CONFIG_DIR"
  printf 'PRIME_HOME=%s\n' "$project_root" > "$CONFIG_FILE"
  green "Configured PRIME_HOME=$project_root"
}

main() {
  require_cmd curl
  require_cmd bash

  mkdir -p "$INSTALL_DIR"

  TMP_FILE="$(mktemp)"
  trap 'rm -f "${TMP_FILE:-}"' EXIT

  echo "Downloading ${BIN_NAME} from ${BIN_URL}..."
  if ! curl \
      --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      --max-time "$CURL_MAX_TIME" \
      --retry "$CURL_RETRY" \
      --retry-delay 1 \
      --retry-connrefused \
      -fsSL "$BIN_URL" \
      -o "$TMP_FILE"; then
    red "Failed to download CLI from ${BIN_URL}"
    yellow "Check DNS/firewall/TLS for ${BASE_URL} and retry."
    yellow "You can override timeouts: PRIME_CURL_CONNECT_TIMEOUT=10 PRIME_CURL_MAX_TIME=30"
    exit 1
  fi

  chmod +x "$TMP_FILE"
  mv "$TMP_FILE" "$INSTALL_DIR/$BIN_NAME"
  TMP_FILE=""
  green "Installed: $INSTALL_DIR/$BIN_NAME"

  write_prime_home_if_known

  if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    yellow "Add this to your shell profile:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
  fi

  echo
  green "Done."
  echo "Try:"
  echo "  $BIN_NAME help"
  echo "  $BIN_NAME status"
}

main "$@"
