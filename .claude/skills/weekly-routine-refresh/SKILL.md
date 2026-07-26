---
name: weekly-routine-refresh
description: routine-jammy의 이번 주 결과를 리뷰하고 다음 주 루틴을 생성해 배포한다. 매주 일요일 18:00 KST 크론이 호출하거나, 필요할 때 수동으로 실행한다.
---

# Weekly Routine Refresh

`routine-jammy` 프로젝트(`~/dev-out/routine-jammy`)의 주간 자동화를 실행한다.

## 실행

```bash
cd ~/dev-out/routine-jammy
source .env 2>/dev/null || true   # ROUTINE_APPS_SCRIPT_URL / ROUTINE_SHARED_SECRET 로드
python3 src/routine-jammy/weekly_refresh.py
```

`weekly_refresh.main()`이 하는 일 (자세한 구현은 `src/routine-jammy/weekly_refresh.py`):
1. `docs/data/current-week.json`의 현재 주차를 읽는다.
2. Apps Script GET으로 그 주의 체크인 데이터를 가져온다.
3. 카테고리별 완료율을 계산하고, 2주 연속 50% 미만인 항목이 있으면 보수적인 조정을 제안한다.
4. `history/data.json`과 `history/<weekId>.md`에 이번 주 요약을 기록한다.
5. `docs/data/current-week.json`을 다음 주차로 갱신한다 (날짜만 +7일, 조정 사항이 있으면 `appliedAdjustments`로 표시).
6. 변경사항을 커밋하고 `origin/main`에 push한다 — GitHub Pages가 자동 재배포된다.

## 완료 후 알림

스크립트가 표준출력으로 찍는 JSON(`weekId`, `rates`, `adjustments`, `nextWeekId`)을 요약해서
PushNotification으로 사용자에게 전달한다. 예:

> 이번 주(2026-W31) 완료율 — 운동 86%, 물 57%. 물 섭취 목표를 낮추는 걸 제안했어요.
> 다음 주(2026-W32) 루틴이 배포됐습니다.

## 실패 시

Apps Script가 응답하지 않거나(`SheetClientError`) 배포가 아직 안 된 상태라면, 스크립트가
예외로 종료된다 — 이 경우 `docs/data/current-week.json`은 변경되지 않으므로 이전 주 루틴이
그대로 유지된다. 사용자에게 실패 사실과 원인을 알리고, `apps-script/README.md`의 배포 상태를
확인하도록 안내한다.
