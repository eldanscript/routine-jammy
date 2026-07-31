# routine-jammy — 저장소를 Google Sheets에서 Supabase로 교체

Date: 2026-07-31
Status: 설계 확정 (구현 계획 수립 대기)

## 왜 바꾸는가

앱은 GitHub Pages로 배포되고, **저장소가 public이다**(Free 플랜에서 Pages를 쓰려면 그래야 한다).
기존 Apps Script 방식은 `docs/config.js`에 `sharedSecret`을 넣어야 하는데, 그 파일은 공개
저장소에 커밋되고 브라우저로도 그대로 서빙된다. 그 시크릿은 **읽기·쓰기 양쪽을 모두 여는**
열쇠라 공개되면 누구나 데이터를 읽고 변조할 수 있다.

Supabase는 이 문제를 정면으로 해결한 백엔드다: publishable 키는 **애초에 클라이언트에
노출되는 것을 전제로** 설계됐고, 실제 접근 통제는 DB의 Row Level Security가 서버에서
강제한다.

### 착수 전 확인된 사실

- **스프레드시트는 만들어진 적이 없다.** `docs/config.js`가 빈 값이고 커밋 이후 한 번도
  변경되지 않았다. `app.js`의 `flushQueue()`는 `if (!CONFIG.appsScriptUrl) return;`으로 조용히
  반환한다. 즉 **배우자의 체크인은 처음부터 localStorage에만 쌓였고 시트로 간 적이 없다.**
  `history/`가 비어 있는 것도 같은 이유다(주간 리프레시가 읽을 데이터가 없었다).
- 따라서 **마이그레이션할 기존 데이터가 없다.** `specs/plans/2026-07-31-sheet-migration-runbook.md`
  는 목적을 잃었다.
- 앱 자체는 살아 있다: https://eldanscript.github.io/routine-jammy/ (HTTP 200), 직전 병합의
  `docs/data/jammy/` 경로 변경도 이미 배포 반영됐다.
- **브라우저는 쓰기 전용이다.** 백엔드에 POST만 하고 GET은 하지 않는다. 화면에 보이는 값은
  전부 저장소의 정적 JSON(`docs/data/<personId>/*.json`, 주간 크론이 생성·커밋)에서 읽는다.

## 목표 / 비목표

**목표**: 공개 저장소에 커밋해도 안전한 키만 클라이언트에 두고, 체크인·회고를 서버에 영속
저장한다. 주간 자동화(완료율·조정 제안·운동 통계·영양분석·텔레그램 리포트)를 되살린다.

**비목표**:
- 로그인/회원가입 도입 — 신뢰 모델은 기존과 동일하게 "고유 링크를 아는 사람 = 그 사람"
- 브라우저에서 백엔드 읽기 — 이번에는 넣지 않는다(§S-5에 확장 경로만 남긴다)
- 호스팅 변경 — GitHub Pages 유지

## 확정된 제약

### C-1. 백엔드 무관 모듈은 건드리지 않는다

직전 v2 작업으로 다음 8개 파이썬 모듈이 저장소 종류와 무관해졌다:
`catalog.py`, `person.py`, `routine_rules.py`, `exercise_stats.py`, `history_store.py`,
`nutrition_lookup.py`, `telegram_notifier.py`, `next_week_builder.py`.
`tests/test_characterization.py`(13개, 기존 사용자 동작 고정)도 마찬가지다.

**이번 교체는 저장소 계층만 갈아끼운다.** 위 모듈과 특성화 테스트의 기대값은 변경 금지.

### C-2. 공개 키로는 읽을 수도, 고칠 수도 없어야 한다

이것이 이 설계의 존재 이유다. publishable 키가 공개 저장소에 있어도:
- SELECT 불가 (누구도 데이터를 읽지 못함)
- UPDATE/DELETE 불가 (누구도 남의 기록을 변조하지 못함)
- INSERT만 가능

수용하는 잔여 위험: **모르는 사람이 쓰레기 행을 삽입할 수 있다.** 크기·형식 제약(§S-3)으로
피해를 제한하고, 알 수 없는 `person_id`의 행은 크론이 필터링해 자연히 무시한다.

### C-3. 새 의존성을 추가하지 않는다

- 파이썬: PostgREST는 HTTP이므로 기존 `requests`로 충분하다. `supabase-py`를 넣지 않는다.
- 프론트: 이 앱은 의도적으로 빌드 도구가 없다. `supabase-js` CDN 대신 `fetch`를 쓴다.

## 설계

### S-1. 쓰기 모델 — append-only

기존 시트는 같은 `(사람, 주차, 요일, 항목)` 행을 찾아 **덮어썼다**. Postgres에서 이는
upsert이고 **UPDATE 권한이 필요**한데, 신원이 없는 상태에서 UPDATE를 열면 아무나 남의 행을
고칠 수 있어 C-2가 무너진다.

따라서 **덮어쓰지 않고 매번 새 행을 추가**하고, 읽을 때 `(사람, 주차, 요일, 항목)`별로
**가장 최근 행만** 취한다.

- 공개 키는 INSERT만 필요 → C-2 성립
- 변경 이력이 남는다(언제 체크했다 풀었는지)
- 행 수 증가는 미미하다: 9항목 × 7일 × 주 + 재체크분. 무료 티어 Postgres 500MB에 한참 못 미침

**"가장 최근"의 판정은 서버가 찍는 `created_at`으로 한다.** 브라우저 시계는 틀리거나 조작될
수 있고, append-only에서 최신 판정은 곧 데이터의 진실이므로 클라이언트 값을 신뢰하면 안 된다.
브라우저가 보낸 시각은 `client_ts`에 진단용으로 남긴다.

### S-2. 스키마 — 단일 테이블 + payload JSONB

**테이블은 `checkins` 하나다.** 회고는 별도 테이블이 아니다 — 프론트가 이미
`sendCheckin({item: '회고', reflection: {...}})`로 같은 경로로 보내고 있고, Apps Script가
받아서 별도 시트로 분기했던 것뿐이다. 그 분기는 시트의 한계였지 도메인의 구조가 아니다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | bigint GENERATED ALWAYS AS IDENTITY PK | |
| `person_id` | text NOT NULL | `people/*.json`의 personId (`jammy` 등) |
| `week_id` | text NOT NULL | `2026-W31` |
| `day` | text NOT NULL | `월`~`일` |
| `item` | text NOT NULL | 카탈로그 아이템 id (한글 문자열 그대로) |
| `checked` | boolean NOT NULL | 모든 아이템 종류가 공유하는 유일한 필드 |
| `payload` | jsonb NOT NULL DEFAULT `'{}'::jsonb` | 아이템 종류별 데이터 |
| `client_ts` | timestamptz | 브라우저가 보낸 시각 (진단용, 신뢰하지 않음) |
| `created_at` | timestamptz NOT NULL DEFAULT now() | **최신 판정 기준** |

**`payload`가 담는 것** — 해석 규칙은 카탈로그의 `ruleType`이 이미 갖고 있다:

| ruleType | 예시 아이템 | payload |
|---|---|---|
| `binaryCheck` | 스쿼트 | `{}` |
| `logging` | 아점 / 저녁 | `{"note": "달걀 2 + 그릭요거트"}` |
| `timedPractice` | 바이올린 | `{"minutes": 20}` *(향후)* |
| (회고) | 회고 | `{"good": "...", "blocker": "...", "change": "..."}` |

**왜 고정 컬럼이 아니라 JSONB인가**: 기존 시트 스키마에는 `minutes`·`sleepHours`·`energy`
컬럼이 있었는데 **파이썬 어디에서도 읽지 않는 잔재**였다. 최초 설계에서 "혹시 몰라" 넣어둔
것이 1년 뒤 검증 없이 그대로 복제될 뻔했다. 아이템 종류가 늘 때마다 컬럼을 추가하는 대신
payload에 담으면 스키마 변경 없이 확장된다.

**`people` 테이블은 만들지 않는다.** 사람 명단의 진실은 저장소의 `people/*.json`이고, DB에
복제하면 동기화 부담만 생긴다. `person_id`는 검증 없는 텍스트로 두되, 크론이 자기가 아는
personId로 필터하므로 모르는 값의 행은 자동으로 무시된다.

**중복 제거는 파이썬에서 한다.** 크론이 해당 주차 행을 전부 받아 `(day, item)`별 `created_at`
최대값만 취한다. Postgres 뷰를 쓰지 않는 이유: 주당 행이 수십 개라 부담이 없고, 로직이
파이썬에 있으면 나머지처럼 단위 테스트가 붙으며, **뷰에 RLS를 거는 것은 알려진 함정**이다
(`security_invoker` 누락 시 우회 가능).

### S-3. 제약 — 공개 INSERT를 감안한 방어

INSERT가 열려 있으므로 DB 레벨에서 쓰레기의 크기와 형식을 제한한다:

- `person_id`, `week_id`, `day`, `item`: NOT NULL + 길이 상한 (각 64자)
- `payload`: `pg_column_size(payload) <= 4096` CHECK — 거대 JSON 삽입 차단
- `payload`: `jsonb_typeof(payload) = 'object'` CHECK — 배열/스칼라 거부

**payload 내용의 스키마 검증은 DB가 할 수 없다.** 아이템의 `ruleType`은 저장소의
`catalog.json`에 있지 DB에 없기 때문이다. 내용 검증은 파이프라인 책임이고, DB는 크기·형식만
막는다.

**인덱스**: `(person_id, week_id)` — 크론의 유일한 조회 패턴.

### S-4. RLS — 이 설계의 유일한 보안 경계

`checkins`에 RLS를 **활성화**하고, **INSERT 정책만** 만든다.

```sql
alter table public.checkins enable row level security;

create policy checkins_insert_anon
  on public.checkins for insert
  to anon
  with check (true);
-- SELECT / UPDATE / DELETE 정책은 만들지 않는다 → Postgres 기본 거부
```

- publishable 키(`sb_publishable_*`, `anon` 역할): INSERT만 통과
- secret 키(`sb_secret_*`): RLS를 우회 → 크론이 전부 읽는다. **`.env`에만 두고 절대 커밋하지 않는다**

> **유일한 사고 지점은 `enable row level security`를 빠뜨리는 것이다.** 정책을 안 만든 것이
> 곧 차단이므로, RLS 자체가 꺼져 있으면 공개 키로 전부 읽힌다. §S-6의 검증이 이걸 잡는다.

### S-5. 나중에 읽기를 여는 경로 (지금은 만들지 않음)

브라우저가 자기 데이터를 되읽어야 할 때(기기 변경·다기기 동기화):

1. `person_tokens(person_id, token_hash, created_at)` 테이블 추가
2. 사람별 URL에 무작위 토큰 부여
3. 토큰을 검증하는 "자기 행만 SELECT" 정책 추가

**지금 스키마에 이미 `person_id`가 있으므로 데이터 마이그레이션 없이 정책·테이블만 추가하면
된다.**

### S-6. 검증 — RLS가 실제로 막는지 확인한다

RLS가 유일한 보안 경계이므로, "정책을 안 만들어서 막힌다"는 방식이 정말 막는지 확인 없이
믿지 않는다. 네트워크가 필요하므로 기본 스위트와 분리해 표시하고(예: `-m network`), 최초 설정
직후와 스키마 변경 시 실행한다.

| 검사 | 기대 |
|---|---|
| publishable 키로 SELECT | **거부** |
| publishable 키로 UPDATE | **거부** |
| publishable 키로 DELETE | **거부** |
| publishable 키로 INSERT | 성공 |
| secret 키로 SELECT | 성공 |

**추가로 배포 후 왕복 확인**: 지금 앱은 config가 비어 조용히 localStorage 전용으로 돌고 있다.
연결 후 실제 체크인이 DB에 도달하는지 눈으로 확인한다(설정 화면의 "동기화 서버 연결" 표시가
"연결됨"으로 바뀌는지 포함).

## 영향 범위

| 파일/영역 | 변경 |
|---|---|
| `src/routine-jammy/sheet_client.py` | 삭제 → `supabase_client.py` 신규 |
| `src/routine-jammy/weekly_refresh.py` | import 한 줄 + 호출부 |
| `docs/app.js` | POST 대상을 PostgREST로, `note`/`reflection`을 `payload`로 감싸기 |
| `docs/config.js` | Supabase URL + publishable 키 (공개 전제 키라 커밋 안전) |
| `apps-script/` 전체 | **삭제** (`Code.gs`, `migrate-person-column.gs`, `README.md`) |
| `specs/plans/2026-07-31-sheet-migration-runbook.md` | **삭제** (마이그레이션할 시트가 없었음) |
| `.env` | `ROUTINE_APPS_SCRIPT_URL`/`ROUTINE_SHARED_SECRET` → `SUPABASE_URL`/`SUPABASE_SECRET_KEY` |
| `supabase/schema.sql` (신규) | 테이블·인덱스·CHECK·RLS·INSERT 정책 |
| `tests/test_supabase_client.py` (신규) | 중복제거·payload 펼치기 단위 테스트 (네트워크 없음) |
| `tests/test_rls_live.py` (신규) | §S-6 RLS 검증 (네트워크 필요, 분리 표시) |
| 최초 설정 안내문 (신규) | Supabase 프로젝트 생성 → SQL 실행 → 키 배치 |
| 위 C-1의 8개 모듈 + `test_characterization.py` | **변경 없음** |

## 저장소 계층의 계약

`supabase_client.fetch_week(week_id, person)`은 **기존 `sheet_client.fetch_week`와 동일한
모양**을 반환한다. 그래야 C-1이 지켜진다.

```python
{"responses": [ {...}, ... ], "reflection": {...}}
```

각 response는 payload를 최상위로 펼친 dict다:

```python
row = {**payload, "day": ..., "item": ..., "checked": ...}   # 코어 필드가 payload를 이긴다
```

payload를 먼저 펼치고 코어 필드를 나중에 씌우는 순서가 중요하다 — 그래야 조작된 payload가
`checked` 같은 코어 값을 덮어쓸 수 없다. 이 순서 덕분에 기존 모듈이 쓰는
`response.get("note")`가 그대로 동작하고, 나중에 `minutes`가 생겨도 자연스럽게 읽힌다.

`item='회고'` 행은 `responses`에 넣지 않고 `reflection`으로 뽑아 반환한다(기존 계약과 동일).

## 미해결 질문

| # | 내용 |
|---|---|
| OQ-1 | Supabase 프로젝트를 아직 만들지 않았다. 무료 티어는 **1주일 미사용 시 일시정지**되는데, 주 1회 크론이 도므로 문제없을 것으로 보이나 실제 동작 확인 필요 |
| OQ-2 | 기존 anon/service_role 키는 2026년 말 폐기 예정이고 `sb_publishable_*`/`sb_secret_*`로 대체 중이다. 신규 프로젝트 생성 시 어느 쪽이 기본으로 발급되는지 확인 후 그에 맞춰 문서화 |
| OQ-3 | 쓰레기 INSERT에 대한 추가 완화(사람별 토큰 컬럼, rate limit)를 지금 넣을지, 실제 남용이 관측된 뒤에 넣을지 |

## 참고

- [Understanding API keys — Supabase Docs](https://supabase.com/docs/guides/getting-started/api-keys)
- [Supabase Security: Exposed Anon Keys, RLS, and Misconfigurations](https://www.stingrai.io/blog/supabase-powerful-but-one-misconfiguration-away-from-disaster)
- [Supabase Free Tier Guide](https://infrafree.dev/en-us/provider/supabase)
