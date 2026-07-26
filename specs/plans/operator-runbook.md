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

3. **Telegram 알림 봇 생성** — `raingent`의 finance_agent/tech_report_agent와 같은 패턴으로,
   routine-jammy 전용 봇을 새로 만든다 (기존 봇 재사용 안 함):
   ```
   1. Telegram에서 @BotFather에게 /newbot 전송
   2. 봇 이름/username 입력 (username은 ...bot으로 끝나야 함)
   3. 발급된 토큰을 ROUTINE_TELEGRAM_BOT_TOKEN으로 저장
   4. 그 봇과의 채팅방에서 아무 메시지나 먼저 보낸 뒤, 브라우저로
      https://api.telegram.org/bot<토큰>/getUpdates 접속 → "chat":{"id": ...} 값을 ROUTINE_TELEGRAM_CHAT_ID로 저장
   ```
   두 값을 `~/dev-out/routine-jammy/.env`에 `ROUTINE_APPS_SCRIPT_URL` / `ROUTINE_SHARED_SECRET`과
   같은 방식으로 추가한다:
   ```bash
   # ~/dev-out/routine-jammy/.env
   ROUTINE_APPS_SCRIPT_URL=...
   ROUTINE_SHARED_SECRET=...
   ROUTINE_TELEGRAM_BOT_TOKEN=...
   ROUTINE_TELEGRAM_CHAT_ID=...
   ```
   (`.env`는 `.gitignore`에 이미 포함되어 커밋되지 않는다.)

4. **GitHub Pages 배포 확인** (1번 저장 후 1-2분 뒤, 빌드가 끝나면):
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" https://eldanscript.github.io/routine-jammy/
   ```
   `200`이 나오면 정상. 아직 `404`면 1-2분 더 기다렸다 재시도.

5. **아이폰 홈 화면 추가**
   - 대상 아이폰에서 Safari로 `https://eldanscript.github.io/routine-jammy/` 접속
   - 공유 버튼 → "홈 화면에 추가"

## Task 8 자동화: crontab 등록 (아직 미설치)

`routine_rules.py`의 채점/조정 로직은 결정적 Python이라 크론 시점에 Claude 세션을 띄울
필요가 없다. Claude의 `CronCreate`는 세션 종료 시 사라지고(날짜/주 단위로 지속되지 않음),
`PushNotification`도 이 대화형 세션의 Remote Control 연결에 묶여 있어 무인 크론 잡에서 쓸 수
없다 — 그래서 이 자동화는 **순수 OS crontab 엔트리**가 `weekly_refresh.py`를 직접 호출하고,
결과 알림은 위에서 만든 전용 Telegram 봇으로 보낸다.

로그 디렉터리 준비 (최초 1회):
```bash
cd ~/dev-out/routine-jammy
mkdir -p logs
```
`logs/`는 `.gitignore`에 이미 등록되어 있어 커밋되지 않는다.

crontab 엔트리 (아직 설치 안 됨 — 이 항목이 동작을 확인한 뒤 컨트롤러가 설치 예정):
```
0 18 * * 0 cd /home/rainny/dev-out/routine-jammy && /usr/bin/env bash -lc 'source .env 2>/dev/null; python3 src/routine-jammy/weekly_refresh.py' >> /home/rainny/dev-out/routine-jammy/logs/weekly-refresh.log 2>&1
```
(매주 일요일 18:00 시스템 로컬 시간. 이 스케줄은 시스템 타임존이 이미 Asia/Seoul로 설정되어
있다고 가정한다 — `timedatectl` 등으로 확인해서 다르면 시각(`18`)을 그에 맞게 조정해야 한다.)
설치는 `crontab -e`로 위 줄을 추가하거나 `crontab -l`에 이어 붙인다.

## 매주 확인

- crontab(Task 8)이 일요일 18:00 KST에 `weekly_refresh.py`를 직접 실행하고 결과를
  전용 Telegram 봇으로 보낸다 (성공/실패 모두 알림).
- `logs/weekly-refresh.log`에서 최근 실행 로그(표준출력/표준에러)를 확인할 수 있다.
- 실패 알림이 오면 다음을 확인:
  - `apps-script/README.md`의 배포 상태
  - Apps Script 실행 기록 (script.google.com → 해당 프로젝트 → 실행 기록)
  - GitHub Pages 상태 (아래 참고)
  - `logs/weekly-refresh.log`의 예외 스택트레이스

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
- [ ] Telegram 알림 봇 생성 및 `.env`에 토큰/chat_id 저장 (위 "최초 설치" 3번) — Telegram 앱에서
      직접 BotFather와 대화해야 함
- [ ] GitHub Pages 배포 확인 curl (위 "최초 설치" 4번) — 1번 완료 후에만 의미 있음
- [ ] 아이폰에 홈 화면 아이콘 추가 (위 "최초 설치" 5번) — 물리적 기기 조작 필요
- [ ] crontab 엔트리 설치 (위 "Task 8 자동화" 참고) — 엔트포인트 동작 확인 후 컨트롤러가 설치
