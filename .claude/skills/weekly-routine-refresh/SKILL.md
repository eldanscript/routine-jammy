---
name: weekly-routine-refresh
description: routine-jammy의 이번 주 결과를 리뷰하고 다음 주 루틴을 생성해 배포한다. 자동화된 주간 실행은 OS crontab이 직접 담당하며(Claude 세션 불필요), 이 스킬은 대화형 세션에서 강제 재실행/결과 확인/조정 논의가 필요할 때 쓴다.
---

# Weekly Routine Refresh

`routine-jammy` 프로젝트(`~/dev-out/routine-jammy`)의 주간 자동화를 실행한다.

## 자동화 방식 (참고)

매주 일요일 18:00 KST 실행은 이 스킬이나 Claude 세션과 무관하게, 순수 OS crontab 엔트리가
`python3 src/routine-jammy/weekly_refresh.py`를 직접 호출한다 (설정은
`specs/plans/operator-runbook.md` 참고). `routine_rules.py`의 채점/조정 로직은 결정적인
순수 Python이라 크론 시점에 Claude를 띄울 필요가 없다. 완료/실패 알림은 전용 Telegram
봇(`telegram_notifier.send_telegram`)으로 발송되며, `PushNotification`은 쓰지 않는다 (이
세션의 Remote Control 연결에 묶여 있어 무인 크론 잡에서 쓸 수 없기 때문).

이 스킬은 그 자동 실행을 대체하지 않는다 — rainny가 대화형 Claude Code 세션 안에서 강제로
재실행하거나, 결과를 직접 살펴보거나, 반영 전에 조정안을 상의하고 싶을 때 수동으로 쓴다.

## 실행

```bash
cd ~/dev-out/routine-jammy
source .env 2>/dev/null || true   # ROUTINE_APPS_SCRIPT_URL / ROUTINE_SHARED_SECRET / ROUTINE_TELEGRAM_* 로드
python3 src/routine-jammy/weekly_refresh.py
```

`weekly_refresh.main()`이 하는 일 (자세한 구현은 `src/routine-jammy/weekly_refresh.py`):
1. `docs/data/jammy/current-week.json`의 현재 주차를 읽는다.
2. Apps Script GET으로 그 주의 체크인 데이터를 가져온다.
3. 카테고리별 완료율을 계산하고, 2주 연속 50% 미만인 항목이 있으면 보수적인 조정을 제안한다.
4. `history/jammy/data.json`과 `history/jammy/<weekId>.md`에 이번 주 요약을 기록한다.
5. `docs/data/jammy/current-week.json`을 다음 주차로 갱신한다 (날짜만 +7일, 조정 사항이 있으면 `appliedAdjustments`로 표시).
6. 변경사항을 커밋하고 `origin/main`에 push한다 — GitHub Pages가 자동 재배포된다.
7. 성공/실패 여부와 관계없이 Telegram으로 요약/실패 메시지를 보낸다 (`execute()` 참고).

## 완료 후 알림

`execute()`가 `run()`+`commit_and_push()` 성공 시 `weekId`, 카테고리별 완료율(%),
`adjustments`(있다면), `nextWeekId`를 요약한 한국어 메시지를 `send_telegram()`으로 보낸다. 예:

> 루틴 주간 리프레시 완료 — 2026-W31
> 완료율: 운동 86%, 물 57%
> 조정 제안:
> - 물 섭취 목표를 낮춰서 부담을 줄이는 걸 제안
> 다음 주(2026-W32) 루틴이 배포되었습니다.

수동 실행 중 rainny가 대화형으로 관찰하고 있다면, 표준출력 JSON을 바탕으로 같은 내용을
대화창에서도 요약해 알려준다.

## 실패 시

`execute()`는 실패 지점과 무관하게 예외를 다시 던지기 전에 Telegram으로 실패 메시지(예외
메시지 포함)를 보낸다. 실패 지점에 따라 실제 상태가 다르므로 구분해서 대응한다:

- **`run()` 내부에서 실패** (예: Apps Script가 응답하지 않는 `SheetClientError`, 배포가 아직
  안 된 상태): `commit_and_push()`는 아예 호출되지 않으므로 아무 것도 바뀌지 않았다.
  `docs/data/jammy/current-week.json`, `history/`는 모두 이전 상태 그대로이고 이전 주 루틴이 그대로
  유지된다. 원인을 해결한 뒤 스크립트를 그냥 재실행하면 된다.
- **`commit_and_push()` 내부에서 `git push`가 실패**: `run()`은 이미 성공해서
  `docs/data/jammy/current-week.json`을 다음 주차로 갱신해 디스크에 썼고, `commit_and_push()`는
  add → commit → push 순서라 **로컬 커밋까지는 이미 만들어진 상태**다 — push만 안 됐을 뿐
  변경 사항 자체는 이미 반영되어 있다. 이 경우 스크립트를 처음부터 재실행하면 이번 주
  데이터를 또 가져와 중복 처리하게 되므로, 원인(네트워크/인증 등)을 먼저 확인한 뒤
  저장소에서 `git status`/`git log`로 로컬 커밋이 있는지 확인하고 `git push origin main`만
  수동으로 다시 실행한다.

Telegram 발송 자체가 실패해도(토큰 오류 등) 원래 예외는 그대로 전파되어 크론 로그/종료
코드에 남는다. 실패 알림을 받으면 `apps-script/README.md`의 배포 상태를 확인한다.
