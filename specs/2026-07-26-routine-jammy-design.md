# routine-jammy 설계 스펙

- 작성일: 2026-07-26
- 상태: 사용자 검토 대기

## 1. 목표

배우자/친구(제3자, Claude를 직접 쓰지 않음)가 아이폰 홈 화면에서 여는 파스텔톤 주간 루틴
앱을 만든다. 운동·식단·바이올린·회복을 요일별로 체크하고, 체크 결과는 자동으로 동기화되어
dev-agent-team이 매주 일요일 18:00(KST)에 지난주를 리뷰하고 다음 주 루틴을 갱신해 같은
URL에 배포한다. 오퍼레이터(rainny)는 그 사람의 아이폰을 직접 만질 수 있는 관계이며, 최초
설치(홈 화면 추가)만 도와주면 이후로는 자동으로 돌아간다.

## 2. 입력 자료

- `docx` 원본 템플릿: 단백질/섬유질 원칙, 월수금 조깅 + 화목토 근력 골격.
- 사용자가 제공한 샘플 PDF(`specs/reference/sample-weekly-routine.pdf`): 위 골격을 이미
  한 단계 더 다듬은 버전 — 조깅을 월(슬로우)/수(슬로우)/금(회복 조깅)으로 세분화하고, 근력을
  A(화)/B(목)/C(토, 가벼운 버전)로 나누고, 일요일을 "회복+회고"로 명시. **이 PDF의 구조를
  v1 루틴의 기준으로 채택한다** — docx보다 더 완성도 높은 버전이므로.
- 사용자가 제공한 디자인 자산 kit(`docs/assets/`): 파스텔 팔레트(tokens.css), 7개 라우트
  내비게이션 구조(navigation.json), 카테고리 스티커·아이콘, PWA 매니페스트/아이콘.

## 3. 보완한 항목 (요구사항 1번)

PDF 샘플이 이미 수면 시간·에너지(1-5) 기록란을 포함하고 있어 대부분의 보완이 되어 있었다.
남은 공백 하나만 추가한다:

- **물 섭취 체크** — 자산 kit에 이미 `water` 카테고리 아이콘/스티커가 준비되어 있었는데
  PDF 체크표에는 항목이 없었다. 하루 체크 항목에 6번째로 추가한다 (운동/단백질/채소/간식계획/
  바이올린/**물**).

스트레칭·워밍업은 PDF처럼 "슬로우 조깅" 항목 설명 안에 포함시키고 별도 체크박스로 쪼개지
않는다 (PDF의 스타일을 따름 — 체크 항목을 늘리면 오히려 부담이 됨).

## 4. 아키텍처

```
[배우자/친구 아이폰 Safari, 홈 화면에 1회 추가]
   └─ GitHub Pages 정적 PWA (eldanscript/routine-jammy, docs/ 소스)
        ├─ docs/index.html + app.js + style.css   ← 최초 구현 후 거의 불변인 "앱 셸"
        ├─ docs/data/current-week.json            ← 매주 자동 교체되는 유일한 콘텐츠
        └─ 체크 탭 → fetch POST → Google Apps Script 웹앱 → Google Sheet 기록

[Linux PC / dev-agent-team]
   └─ CronCreate: 매주 일요일 18:00 Asia/Seoul
        1. Apps Script GET으로 지난주 시트 데이터 조회
        2. 완료율 계산, 2주 연속 50% 미만 항목 플래그
        3. .claude/skills/weekly-routine-refresh 스킬 실행:
           - history/data.json, history/YYYY-Www.md 기록
           - 보수적 규칙 기반 미세 조정만 자동 적용 (예: 반복 저조 항목 대체 제안 수준).
             더 큰 변경(요일 골격 자체를 바꾸는 등)은 자동 적용하지 않고 알림에 제안만 담는다.
           - docs/data/current-week.json 재생성 (다음 주차, 체크 상태 초기화)
           - (선택 기능) 지난주 결과 요약 PDF 렌더링 → history/pdf/YYYY-Www.pdf
        4. git commit & push → GitHub Pages 자동 배포 (같은 URL, 앱 셸은 그대로)
        5. PushNotification으로 rainny에게 요약 + 제안 사항 전달
```

**핵심 설계 결정**: 매주 HTML을 통째로 재생성하지 않고, 정적 앱 셸(HTML/JS/CSS)은 최초
구현 시 한 번만 만들고 이후 고정한다. 매주 바뀌는 건 `docs/data/current-week.json` 하나뿐이다.
이렇게 하면 매주 실행되는 자동화가 실수로 레이아웃을 깨뜨릴 위험이 사라지고, "스킬"의 책임이
데이터 생성으로 좁아져 재사용성이 높아진다.

## 5. 프런트엔드 (docs/)

자산 kit의 `navigation.json` 구조를 그대로 쓰되, 무거운 SPA 프레임워크 없이 Vanilla JS로
섹션을 전환한다 (해시 라우팅, 예: `#/week`, `#/exercise`).

| 라우트 | 내용 |
|---|---|
| 홈 | 오늘의 운동/식단/바이올린/회복 카드 (dashboardCards, 스티커 사용) |
| 주간 계획 | 월~일 7일 카드, PDF 2페이지 "이번 주 한눈에" 스타일 |
| 운동 | 슬로우조깅 3단계 설명 + 근력 A/B/C 상세 (PDF 3페이지 내용) |
| 식단 | 단백질 공식 + 요일별 아점/저녁 표 (PDF 4페이지 내용) |
| 오늘 체크 | 요일별 체크박스 6종 + 분/수면/에너지 입력 (모바일 하단 내비 primaryAction) |
| 리포트 | 주간 완료율, 회고 3문항 입력, **"이번 주 PDF로 내보내기" 버튼** |
| 설정 | 앱 버전/최근 동기화 시각 표시, 로컬 큐 초기화 버튼 정도 (최소 기능, 비밀키는 화면에 노출하지 않음) |

디자인은 `docs/assets/tokens.css`의 팔레트(민트/피치/라벤더/버터/블루)를 그대로 쓰고, 터치
영역 44px 이상, 카드 라운드 18px 등 자산 가이드 기준을 따른다. 오프라인 캐싱을 위한 Service
Worker는 두지 않는다 (최신 주차 콘텐츠가 항상 즉시 보여야 하므로 오히려 방해가 됨) — `manifest.
webmanifest`와 `apple-mobile-web-app-capable` 메타 태그만으로 홈 화면 추가를 지원한다.

## 6. 데이터 모델 & Apps Script 계약

**체크인 이벤트 (POST)**
```json
{
  "secret": "<shared-secret>",
  "weekId": "2026-W31",
  "day": "월",
  "item": "운동|단백질|채소|간식|바이올린|물",
  "checked": true,
  "minutes": 25,
  "sleepHours": 7.5,
  "energy": 4,
  "timestamp": "2026-07-27T21:03:00+09:00"
}
```
Apps Script는 Google Sheet의 `responses` 탭에 한 행씩 append/upsert(같은 weekId+day+item
키는 갱신)한다.

**주간 요약 조회 (GET, Claude 전용)**
`?secret=...&weekId=2026-W31` → 요일별 항목 체크 여부, 평균 수면/에너지, 회고 텍스트(있으면)
를 JSON으로 반환.

**history/data.json (로컬 미러, 감사용)**
```json
{
  "weeks": {
    "2026-W31": {
      "completionByCategory": {"운동": 0.86, "근력": 1.0, "식단": 1.0, "바이올린": 0.71, "물": 0.57},
      "adjustmentsApplied": ["물 목표를 8잔→6잔으로 완화 (2주 연속 50% 미만)"],
      "reflection": {"good": "...", "blocker": "...", "change": "..."}
    }
  }
}
```

## 7. 에러 처리 / 엣지 케이스

- 오프라인 체크: `app.js`가 로컬 큐(localStorage)에 먼저 쓰고 POST, 실패 시 다음 앱 실행 때
  재전송. 체크 표시 자체는 네트워크 상태와 무관하게 즉시 반영.
- 첫 주(이력 없음): 규칙 기반 조정을 건너뛰고 PDF 기준 초기 루틴 그대로 배포.
- Apps Script 응답 없음(할당량 초과 등): 크론 작업은 "데이터 조회 실패"로 표시하고 조정 없이
  다음 주도 이전 주 데이터를 재사용 + rainny에게 알림으로 수동 확인 요청.
- 시트/앱스크립트 배포가 아직 안 된 상태에서 앱이 열리는 경우: POST 실패해도 화면은 정상
  동작(로컬 큐에만 쌓임).

## 8. 프라이버시/보안

- `eldanscript/routine-jammy`는 private repo, GitHub Pages는 그 상태로도 배포 가능 (URL을
  아는 사람만 접근하는 수준의 보호).
- Apps Script 공유 비밀키는 클라이언트 JS에 노출되지만, 저장 데이터가 루틴 체크 수준이라
  리스크는 낮다고 판단.
- 체중 등 더 민감할 수 있는 수치가 추가된다면 Sheet에만 남기고 앱 화면/커밋에는 노출하지 않는다.

## 9. 테스트 전략

- `tests/`: 주간 리프레시 로직(완료율 계산, 조정 규칙, history 갱신)의 유닛 테스트 — Python.
- 프런트엔드는 수동 스모크 테스트(로컬 서버로 열어 체크/네비게이션 확인) + reviewer 에이전트의
  정적 리뷰. 별도 E2E 프레임워크는 이 규모에 과함(YAGNI).

## 10. 남은 오픈 아이템 (구현 단계에서 확정)

- PDF 내보내기 렌더링 방식(WeasyPrint vs 헤드리스 브라우저) — architect가 구현 계획 단계에서
  가용 라이브러리를 확인 후 결정.
- Apps Script 최초 배포는 사용자가 script.google.com에서 직접 진행 (코드는 `apps-script/
  Code.gs`로 미리 준비해서 복붙만 하면 되게 함).
- GitHub Pages 활성화(Settings → Pages → `main`/`docs`)는 devops 에이전트가 안내.

## 11. 다음 단계

이 스펙 승인 후 `writing-plans` 스킬로 구현 계획을 작성하고, architect → frontend-developer /
backend-developer → devops → reviewer 순으로 진행한다.
