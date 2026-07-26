# Apps Script 배포 (최초 1회 수동)

1. https://script.google.com → 새 프로젝트
2. 기본 `Code.gs` 내용을 이 폴더의 `Code.gs`로 전부 교체
3. Google Sheets에서 새 스프레드시트를 만들고 URL의 `/d/<이 부분>/edit`에서 스프레드시트 ID 복사
4. 프로젝트 설정(톱니바퀴) → 스크립트 속성에 추가:
   - `ROUTINE_SHEET_ID` = 3에서 복사한 ID
   - `ROUTINE_SHARED_SECRET` = 임의의 긴 랜덤 문자열 (예: `openssl rand -hex 16`으로 생성)
5. 배포 → 새 배포 → 유형: 웹 앱
   - 실행 계정: 나
   - 액세스 권한: 링크가 있는 모든 사용자
6. 배포 후 나오는 웹 앱 URL을 복사해서:
   - `docs/config.js`의 `appsScriptUrl`에 붙여넣기
   - 같은 값을 `ROUTINE_APPS_SCRIPT_URL` 환경 변수로 저장(주간 자동화용)
   - `ROUTINE_SHARED_SECRET`은 `docs/config.js`의 `sharedSecret`과 4번의 스크립트 속성 두 곳에 동일하게 넣기
7. `scripts/smoke_test_apps_script.sh`로 배포 확인 (Step 3 참고)
