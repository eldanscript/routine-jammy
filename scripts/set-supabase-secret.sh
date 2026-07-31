#!/usr/bin/env bash
# Supabase secret 키를 .env에 안전하게 넣는다.
#
# 사용법:  ./scripts/set-supabase-secret.sh
#
# - 키를 화면에 표시하지 않는다(입력이 가려짐)
# - 형식을 검증한다 (sb_secret_ 로 시작해야 함)
# - 실수로 publishable 키를 넣으면 거부한다
# - 기존 .env를 백업한 뒤 해당 줄만 교체한다
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
  echo "오류: $ENV_FILE 이 없습니다. 저장소 루트에서 실행하세요." >&2
  exit 1
fi

echo "Supabase secret 키를 붙여넣고 Enter를 누르세요."
echo "(입력은 화면에 보이지 않습니다. 대시보드 > Project Settings > API Keys > Secret keys)"
printf '키: '
read -rs KEY
echo

if [ -z "$KEY" ]; then
  echo "오류: 아무것도 입력되지 않았습니다." >&2
  exit 1
fi

case "$KEY" in
  sb_publishable_*)
    echo "오류: 이건 publishable 키입니다. secret 키가 필요합니다." >&2
    echo "      publishable 키는 브라우저용이고 .env에 넣지 않습니다." >&2
    exit 1
    ;;
  sb_secret_*)
    ;;
  *)
    echo "오류: sb_secret_ 로 시작하지 않습니다. 잘못 복사했는지 확인하세요." >&2
    exit 1
    ;;
esac

BACKUP="${ENV_FILE}.bak-$(date +%Y%m%d-%H%M%S)"
cp "$ENV_FILE" "$BACKUP"

# 값에 특수문자가 있어도 안전하도록 sed 대신 파이썬으로 교체한다
KEY="$KEY" python3 - "$ENV_FILE" <<'PY'
import os, sys, pathlib
path = pathlib.Path(sys.argv[1])
key = os.environ["KEY"]
lines = path.read_text(encoding="utf-8").splitlines()
found = False
for i, line in enumerate(lines):
    if line.startswith("SUPABASE_SECRET_KEY="):
        lines[i] = f"SUPABASE_SECRET_KEY={key}"
        found = True
        break
if not found:
    lines.append(f"SUPABASE_SECRET_KEY={key}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

if grep -q '^SUPABASE_SECRET_KEY=sb_secret_' "$ENV_FILE"; then
  echo "완료: .env에 secret 키를 넣었습니다. (백업: $BACKUP)"
  echo "확인: $(grep -c '^SUPABASE_SECRET_KEY=sb_secret_' "$ENV_FILE") (1이면 정상)"
else
  echo "실패: 쓰기 후 검증에 실패했습니다. 백업 $BACKUP 을 확인하세요." >&2
  exit 1
fi
