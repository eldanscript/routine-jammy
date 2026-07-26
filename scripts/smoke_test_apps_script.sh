#!/usr/bin/env bash
# Usage: ROUTINE_APPS_SCRIPT_URL=... ROUTINE_SHARED_SECRET=... ./scripts/smoke_test_apps_script.sh
set -euo pipefail

: "${ROUTINE_APPS_SCRIPT_URL:?Set ROUTINE_APPS_SCRIPT_URL first}"
: "${ROUTINE_SHARED_SECRET:?Set ROUTINE_SHARED_SECRET first}"

echo "POST 체크인 테스트..."
curl -sS -X POST "$ROUTINE_APPS_SCRIPT_URL" \
  -H 'Content-Type: application/json' \
  -d "{\"secret\":\"$ROUTINE_SHARED_SECRET\",\"weekId\":\"2026-W00\",\"day\":\"월\",\"item\":\"운동\",\"checked\":true,\"timestamp\":\"2026-01-01T00:00:00+09:00\"}"
echo
echo "GET 조회 테스트..."
curl -sS "$ROUTINE_APPS_SCRIPT_URL?secret=$ROUTINE_SHARED_SECRET&weekId=2026-W00"
echo
