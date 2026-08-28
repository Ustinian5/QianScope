#!/usr/bin/env bash

set -euo pipefail

readonly PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PRODUCT_NAME="QianScope"
readonly EXPECTED_REMOTE_URL="https://github.com/Ustinian5/QianScope.git"
readonly EXPECTED_PROJECT_NAME="swm-guizhou"
readonly PROJECT_ID="6a91407ccb6b9b31c9e67dda"
readonly ENVIRONMENT_ID="${QIANSCOPE_ENVIRONMENT_ID:-${SWM_GUIZHOU_ENVIRONMENT_ID:-6a91407c3bf3ef23ef4d4b8a}}"
readonly API_SERVICE_ID="${QIANSCOPE_API_SERVICE_ID:-${SWM_GUIZHOU_API_SERVICE_ID:-6a914f1bcb6b9b31c9e68450}}"
readonly WEB_SERVICE_ID="${QIANSCOPE_WEB_SERVICE_ID:-${SWM_GUIZHOU_WEB_SERVICE_ID:-6a915044cb6b9b31c9e684f5}}"
readonly -a LEGACY_SWM_IDS=(
  "6a8ef09a31ffc31a6c926b78"
  "6a8ef09a3bf3ef23ef4d47a0"
  "6a8ef09a7389998816aba9fe"
  "6a8ef09a7389998816aba9ff"
)
ZEABUR=(npx --yes zeabur@0.21.0)
if [[ -n "${ZEABUR_WORKSPACE:-}" ]]; then
  ZEABUR+=(--workspace "$ZEABUR_WORKSPACE")
fi
TARGET="${1:-all}"

die() {
  echo "$1" >&2
  exit 1
}

require_object_id() {
  local variable_name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    die "$variable_name is required; export it after creating the isolated $PRODUCT_NAME resource."
  fi
  if [[ ! "$value" =~ ^[0-9a-f]{24}$ ]]; then
    die "$variable_name must be a 24-character lowercase Zeabur object ID."
  fi
}

if [[ "$TARGET" != "all" && "$TARGET" != "api" && "$TARGET" != "web" ]]; then
  die "Usage: $0 [all|api|web]"
fi

require_object_id "PROJECT_ID" "$PROJECT_ID"
  require_object_id "QIANSCOPE_ENVIRONMENT_ID" "$ENVIRONMENT_ID"
if [[ "$TARGET" == "all" || "$TARGET" == "api" ]]; then
  require_object_id "QIANSCOPE_API_SERVICE_ID" "$API_SERVICE_ID"
fi
if [[ "$TARGET" == "all" || "$TARGET" == "web" ]]; then
  require_object_id "QIANSCOPE_WEB_SERVICE_ID" "$WEB_SERVICE_ID"
fi

for candidate_id in "$PROJECT_ID" "$ENVIRONMENT_ID" "$API_SERVICE_ID" "$WEB_SERVICE_ID"; do
  [[ -z "$candidate_id" ]] && continue
  for legacy_id in "${LEGACY_SWM_IDS[@]}"; do
    if [[ "$candidate_id" == "$legacy_id" ]]; then
      die "Refusing to deploy: a configured resource ID belongs to the legacy SWM project."
    fi
  done
done

if [[ -n "$API_SERVICE_ID" && -n "$WEB_SERVICE_ID" && "$API_SERVICE_ID" == "$WEB_SERVICE_ID" ]]; then
  die "API and web services must use different Zeabur service IDs."
fi

if [[ "$(git -C "$PROJECT_ROOT" branch --show-current)" != "main" ]]; then
  die "Deployment is restricted to the main branch."
fi

if [[ -n "$(git -C "$PROJECT_ROOT" status --porcelain)" ]]; then
  die "Commit or discard local changes before deployment."
fi

if REMOTE_URL="$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null)"; then
  if [[ "$REMOTE_URL" != "$EXPECTED_REMOTE_URL" ]]; then
    die "Refusing to deploy from $REMOTE_URL; origin must be $EXPECTED_REMOTE_URL."
  fi
else
  echo "No Git origin configured; deploying the committed local main snapshot."
fi

"${ZEABUR[@]}" auth status >/dev/null

PROJECT_JSON="$(
  "${ZEABUR[@]}" project get \
    --interactive=false \
    --id "$PROJECT_ID" \
    --json
)"
RESOLVED_PROJECT_ID="$(
  printf '%s\n' "$PROJECT_JSON" \
    | sed -nE 's/^[[:space:]]*"ID":[[:space:]]*"([^"]+)".*$/\1/p' \
    | head -n 1
)"
RESOLVED_PROJECT_NAME="$(
  printf '%s\n' "$PROJECT_JSON" \
    | sed -nE 's/^[[:space:]]*"Name":[[:space:]]*"([^"]+)".*$/\1/p' \
    | head -n 1
)"
if [[ "$RESOLVED_PROJECT_ID" != "$PROJECT_ID" ]]; then
  die "Zeabur returned an unexpected project ID; deployment stopped."
fi
if [[ "$RESOLVED_PROJECT_NAME" != "$EXPECTED_PROJECT_NAME" ]]; then
  die "Zeabur project name must be $EXPECTED_PROJECT_NAME, got ${RESOLVED_PROJECT_NAME:-unknown}."
fi

echo "Verified source commit: $(git -C "$PROJECT_ROOT" rev-parse --short HEAD)."
echo "Verified Zeabur destination: $EXPECTED_PROJECT_NAME ($PROJECT_ID)."

SERVICE_LIST_JSON="$(
  "${ZEABUR[@]}" service list \
    --interactive=false \
    --project-id "$PROJECT_ID" \
    --json
)"

require_service_in_project() {
  local variable_name="$1"
  local service_id="$2"
  if [[ "$SERVICE_LIST_JSON" != *"\"ID\": \"$service_id\""* ]]; then
    die "$variable_name does not belong to the verified $EXPECTED_PROJECT_NAME project."
  fi
}

if [[ "$TARGET" == "all" || "$TARGET" == "api" ]]; then
  require_service_in_project "QIANSCOPE_API_SERVICE_ID" "$API_SERVICE_ID"
fi
if [[ "$TARGET" == "all" || "$TARGET" == "web" ]]; then
  require_service_in_project "QIANSCOPE_WEB_SERVICE_ID" "$WEB_SERVICE_ID"
fi

if [[ "$TARGET" == "all" || "$TARGET" == "api" ]]; then
  echo "Deploying $PRODUCT_NAME API to Zeabur..."
  (
    cd "$PROJECT_ROOT"
    "${ZEABUR[@]}" deploy \
      --interactive=false \
      --project-id "$PROJECT_ID" \
      --environment-id "$ENVIRONMENT_ID" \
      --service-id "$API_SERVICE_ID" \
      --json
  )
fi

if [[ "$TARGET" == "all" || "$TARGET" == "web" ]]; then
  echo "Deploying $PRODUCT_NAME web to Zeabur..."
  (
    cd "$PROJECT_ROOT/frontend"
    "${ZEABUR[@]}" deploy \
      --interactive=false \
      --project-id "$PROJECT_ID" \
      --environment-id "$ENVIRONMENT_ID" \
      --service-id "$WEB_SERVICE_ID" \
      --json
  )
fi

echo "$PRODUCT_NAME Zeabur deployments submitted."
