# routine-jammy 운영 런북

이 문서는 어떤 에이전트도 대신 수행할 수 없는(사람의 로그인·물리적 조작이 필요한) 최초 1회
수동 단계와, 이후 매주 정기적으로 확인할 사항을 한 곳에 모은다.

## 환경 제약 메모 (2026-07-26)

이 머신에는 `gh` CLI가 설치되어 있지 않고 GitHub API 토큰도 없다 (`GITHUB_TOKEN` 미설정,
`~/.config/gh` 없음, `~/.netrc` 없음). GitHub 접근은 SSH 키 전용이며 (git push/pull 정상
동작 확인됨) 이는 사용자의 의도적인 기존 방침이므로 `gh` 설치나 토큰 발급으로 우회하지
않는다. 이 때문에 GitHub Pages 활성화는 `gh api`로 자동화하지 못하고 아래 "최초 설치"
1번 단계처럼 웹 UI에서 수동으로 켜야 한다.

## 최초 설치 (1회, rainny가 직접 수행)

1. **GitHub Pages 활성화 (수동, 웹 UI)**
   - `https://github.com/eldanscript/routine-jammy/settings/pages` 접속
   - "Build and deployment" 섹션에서:
     - Source: **Deploy from a branch**
     - Branch: **main**, 폴더: **/docs**
   - **Save** 클릭
   - 참고: 이 저장소에는 `gh` CLI/API 토큰이 없어 이 단계를 명령줄로 자동화할 수 없다.
     반드시 웹 UI에서 수행한다.

2. **Apps Script 배포** — `apps-script/README.md`대로 진행:
   - script.google.com에서 새 프로젝트 생성, `apps-script/Code.gs` 내용 붙여넣기
   - Google Sheets 새 스프레드시트 생성 후 시트 ID를 스크립트 속성 `ROUTINE_SHEET_ID`에 저장
   - `ROUTINE_SHARED_SECRET` 스크립트 속성에 랜덤 문자열 저장 (`openssl rand -hex 16`)
   - 웹 앱으로 배포 (실행 계정: 나, 액세스: 링크가 있는 모든 사용자)
   - 배포된 웹 앱 URL과 시크릿을 `docs/config.js`에 채운 뒤:
     ```bash
     cd ~/dev-out/routine-jammy
     git add docs/config.js
     git commit -m "chore: fill in Apps Script config"
     git push
     ```
   - 같은 URL/시크릿을 이 서버(dev-agent-team이 도는 머신)의 환경 변수
     `ROUTINE_APPS_SCRIPT_URL` / `ROUTINE_SHARED_SECRET`으로도 저장 (Task 8 주간 자동화가 사용)
   - `apps-script/README.md`의 `scripts/smoke_test_apps_script.sh`로 배포 확인

3. **GitHub Pages 배포 확인** (1번 저장 후 1-2분 뒤, 빌드가 끝나면):
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" https://eldanscript.github.io/routine-jammy/
   ```
   `200`이 나오면 정상. 아직 `404`면 1-2분 더 기다렸다 재시도.

4. **아이폰 홈 화면 추가**
   - 대상 아이폰에서 Safari로 `https://eldanscript.github.io/routine-jammy/` 접속
   - 공유 버튼 → "홈 화면에 추가"

## 매주 확인

- 크론(Task 8)이 일요일 18:00 KST에 자동 실행되고 결과를 PushNotification으로 보낸다.
- 실패 알림이 오면 다음을 확인:
  - `apps-script/README.md`의 배포 상태
  - Apps Script 실행 기록 (script.google.com → 해당 프로젝트 → 실행 기록)
  - GitHub Pages 상태 (아래 참고)

## GitHub Pages 상태 확인

`gh` CLI가 없는 동안은 API로 상태를 조회할 수 없다. 대신 페이지가 실제로 응답하는지로
간접 확인한다:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://eldanscript.github.io/routine-jammy/
```

`200`이면 정상. `404`가 계속되면 `https://github.com/eldanscript/routine-jammy/settings/pages`
에서 Source/Branch 설정이 유지되고 있는지, 그리고 저장소의 Actions 탭(또는 커밋 상태 체크)에서
`pages build and deployment` 워크플로가 실패하지 않았는지 확인한다.

(`gh` CLI를 나중에 설치하게 되면 `gh api repos/eldanscript/routine-jammy/pages`로
`"status": "built"` 여부를 직접 조회할 수 있다.)

## 남은 수동 작업 (에이전트가 대신할 수 없음)

- [ ] GitHub Pages 활성화 (위 "최초 설치" 1번) — 웹 UI에서 수동 토글 필요
- [ ] Apps Script 배포 및 `docs/config.js` 채우기 (위 "최초 설치" 2번) — 대화형 Google 로그인 필요
- [ ] GitHub Pages 배포 확인 curl (위 "최초 설치" 3번) — 1번 완료 후에만 의미 있음
- [ ] 아이폰에 홈 화면 아이콘 추가 (위 "최초 설치" 4번) — 물리적 기기 조작 필요
