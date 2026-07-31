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
- UPDATE/DELETE 불가
- **INSERT는 유효한 사람별 쓰기 토큰이 있을 때만, 그 토큰이 가리키는 person_id로만** 가능

> **초안의 오류와 정정 (설계 리뷰에서 발견)**
>
> 초안은 "append-only라 UPDATE 권한이 필요 없으니 아무도 남의 기록을 못 고친다"고 했으나
> **거짓이었다.** INSERT 정책이 `with check (true)`이면 누구나 임의의 `person_id`로 행을
> 넣을 수 있고, 읽기가 "최신 승자"이므로 **그 행이 곧 권위 있는 값이 된다.** UPDATE를 막았지만
> 삽입+최신승자로 같은 능력이 재현된 것이다 — 동사만 바뀌고 권한은 그대로였다.
>
> 실제 피해 경로가 있었다: `person_id`는 공개된 `people/*.json`에 있고, `item='회고'` 행의
> payload는 `render_week_markdown`을 거쳐 **`history/`에 커밋되어 공개 저장소에 push되고
> 텔레그램 리포트로도 나간다.** 즉 익명의 누구나 대상자 이름으로 임의 텍스트를 공개
> 저장소에 남길 수 있었다.
>
> 정정: INSERT를 **사람별 쓰기 토큰**에 묶는다(§S-2.1). 정책은
> `with check (person_id = public.person_for_token())`이다.

수용하는 잔여 위험: **유효한 토큰을 가진 사람은 자기 person_id로 무엇이든 넣을 수 있다.**
크기·형식 제약(§S-3)이 개별 행을 좁히지만 행 수 자체는 제한하지 않는다. 토큰 없는 외부인은
삽입 자체가 불가하므로, 이 위험은 링크를 받은 당사자(또는 그 링크를 얻은 사람)로 한정된다.
링크가 유출되면 해당 토큰만 `revoked_at`을 채워 즉시 무효화한다.

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

### S-2.1 사람별 쓰기 토큰 — INSERT를 신원에 묶는다

C-2의 정정에 따라, INSERT는 **유효한 토큰이 가리키는 person_id로만** 허용한다.

**`person_write_tokens(token, person_id, created_at, revoked_at)`**
- `anon`에 어떤 권한도 주지 않는다 — 토큰 목록을 열거할 수 없어야 한다
- RLS를 켜되 정책을 만들지 않는다(전면 차단)

**`public.person_for_token()`** — `security definer` 함수
- 요청 헤더 `x-routine-token`을 person_id로 해석한다
- `security definer`라 함수 소유자 권한으로 실행되므로, `anon`이 토큰 표를 직접 읽지 않고도
  자기 토큰을 해석할 수 있다
- `set search_path = public, pg_temp`로 고정한다 — `security definer` 함수의 표준 주의사항
  (search_path 조작을 통한 하이재킹 방지)
- 토큰이 없거나 폐기됐으면 `NULL`을 낸다

**정책**: `with check (person_id = public.person_for_token())`
- 토큰이 없으면 `person_id = NULL`이 되어 참이 아니므로 **삽입이 거부된다**
- 즉 **토큰 없는 외부인은 아무것도 넣을 수 없다**

**토큰의 전달 경로**: 사람별 링크에 담는다 — `?person=jammy&t=<토큰>`.
저장소에 **커밋하지 않는다.** rainny가 링크로 직접 전달한다. 프론트는 `person`으로 정적 파일
경로를 만들고, `t`를 `x-routine-token` 헤더로 실어 보낸다.

이는 기존 신뢰 모델("고유 링크를 아는 사람 = 그 사람")과 정확히 같은 수준이다. 한 사람의
링크가 유출돼도 **그 사람의 쓰기 권한만** 넘어가며, 그 토큰만 `revoked_at`을 채워 즉시
무효화한다.

**부수 효과 — 용량 고갈 DoS도 함께 막힌다.** 토큰이 없으면 삽입 자체가 불가하므로, 익명
공격자가 무료 티어 500MB를 채워 서비스를 마비시키는 경로가 사라진다.

### S-3. 제약 — 토큰 보유자의 실수·남용을 좁힌다

토큰 없는 외부인은 §S-2.1에서 이미 막힌다. 아래 제약은 **유효한 토큰을 가진 쪽**의 실수나
남용 범위를 좁히는 두 번째 겹이다:

- `person_id`, `week_id`, `day`, `item`: NOT NULL + 길이 상한 (각 64자)
- `payload`: `pg_column_size(payload) <= 4096` CHECK — 거대 JSON 삽입 차단
- `payload`: `jsonb_typeof(payload) = 'object'` CHECK — 배열/스칼라 거부

**payload 내용의 스키마 검증은 DB가 할 수 없다.** 아이템의 `ruleType`은 저장소의
`catalog.json`에 있지 DB에 없기 때문이다. 내용 검증은 파이프라인 책임이고, DB는 크기·형식만
막는다.

**인덱스**: `(person_id, week_id)` — 크론의 유일한 조회 패턴.

### S-4. RLS와 권한 — 두 겹의 방어

두 테이블 모두 RLS를 **활성화**하고, `checkins`에 **INSERT 정책 하나만** 만든다.

```sql
alter table public.checkins            enable row level security;
alter table public.person_write_tokens enable row level security;

create policy checkins_insert_own
  on public.checkins for insert
  to anon
  with check (person_id = public.person_for_token());
-- SELECT / UPDATE / DELETE 정책은 만들지 않는다 → Postgres 기본 거부
-- person_write_tokens에는 어떤 정책도 만들지 않는다 → anon 전면 차단
```

- publishable 키(`sb_publishable_*`, `anon` 역할): 유효 토큰이 있을 때만 자기 person_id로 INSERT
- secret 키(`sb_secret_*`): RLS를 우회 → 크론이 전부 읽는다. **`.env`에만 두고 절대 커밋하지 않는다**

**권한(GRANT)은 RLS와 독립된 두 번째 방어선이다.** Supabase는 `public` 스키마의 새 테이블에
기본 권한을 넓게 주는 설정이 있을 수 있으므로, 먼저 전부 회수한 뒤 필요한 것만 다시 준다.
RLS가 잘못 설정돼도 GRANT가 없으면 SELECT는 막힌다 — **두 장치가 동시에 실패해야 데이터가
샌다.**

**INSERT는 컬럼 단위로 준다** — `id`와 `created_at`은 주지 않는다. `created_at`이 "최신 승자"
판정 기준이므로 클라이언트가 이 값을 지정할 수 있으면 시각을 위조해 남의 최신 기록을 덮어쓴
것처럼 만들 수 있다. 권한이 없으면 항상 서버의 `default now()`가 쓰인다.

> **유일한 사고 지점은 `enable row level security`를 빠뜨리는 것이다.** 정책을 안 만든 것이
> 곧 차단이므로, RLS 자체가 꺼져 있으면 공개 키로 전부 읽힌다. §S-6의 검증이 이걸 잡는다.

**구현 주의 — `Prefer: return=minimal`**: `anon`에 SELECT 권한이 없으므로, 클라이언트가 삽입
결과를 돌려받으려 하면(`Prefer: return=representation`, supabase-js의 `.select()` 등)
`RETURNING` 절이 거부되어 **INSERT 전체가 실패한다.** 데이터가 새는 게 아니라 안전한 실패지만,
"Supabase가 고장났다"로 오인하기 쉬운 함정이라 `docs/app.js`는 반드시 `return=minimal`로
보낸다(PostgREST 기본값이지만 명시한다).

### S-5. 나중에 읽기를 여는 경로 (지금은 만들지 않음)

브라우저가 자기 데이터를 되읽어야 할 때(기기 변경·다기기 동기화) 필요한 것은 **정책 한 줄뿐**
이다. §S-2.1에서 토큰 체계가 이미 들어갔기 때문이다:

```sql
create policy checkins_select_own
  on public.checkins for select
  to anon
  using (person_id = public.person_for_token());

grant select on table public.checkins to anon;   -- GRANT도 함께 열어야 한다(두 겹이므로)
```

테이블 추가도, 데이터 마이그레이션도, URL 형식 변경도 없다 — 토큰은 이미 링크에 실려 있다.

**단 그때 함께 검토할 것**: 읽기를 열면 §S-4의 "GRANT가 없어 SELECT가 막힌다"는 두 번째
방어선이 사라지고 RLS 단독 방어가 된다. 그리고 `Prefer: return=minimal` 제약도 풀린다.

### S-6. 검증 — RLS가 실제로 막는지 확인한다

RLS가 유일한 보안 경계이므로, "정책을 안 만들어서 막힌다"는 방식이 정말 막는지 확인 없이
믿지 않는다. 네트워크가 필요하므로 기본 스위트와 분리해 표시하고(예: `-m network`), 최초 설정
직후와 스키마 변경 시 실행한다.

| # | 검사 | 기대 | 무엇을 지키는가 |
|---|---|---|---|
| 1 | publishable 키로 SELECT | **거부** | 데이터 비공개 |
| 2 | publishable 키로 UPDATE | **거부** | 변조 방지 |
| 3 | publishable 키로 DELETE | **거부** | 삭제 방지 |
| 4 | publishable 키 + **토큰 없이** INSERT | **거부** | 익명 삽입·DoS 차단 |
| 5 | publishable 키 + **틀린 토큰**으로 INSERT | **거부** | 토큰 검증이 실제로 동작 |
| 6 | publishable 키 + **jammy 토큰**으로 `person_id='jammy'` INSERT | 성공 | 정상 경로 |
| 7 | publishable 키 + **jammy 토큰**으로 `person_id='other'` INSERT | **거부** | **타인 사칭 차단(C-2의 핵심)** |
| 8 | publishable 키로 `person_write_tokens` SELECT | **거부** | 토큰 열거 차단 |
| 9 | secret 키로 SELECT | 성공 | 크론이 읽을 수 있음 |

**7번이 이번 정정의 핵심 검사다.** 초안 설계는 이 케이스에서 성공했을 것이고, 그게 곧 C-2가
거짓이었다는 뜻이다.

**추가로 배포 후 왕복 확인**: 지금 앱은 config가 비어 조용히 localStorage 전용으로 돌고 있다.
연결 후 실제 체크인이 DB에 도달하는지 눈으로 확인한다(설정 화면의 "동기화 서버 연결" 표시가
"연결됨"으로 바뀌는지 포함).

### S-7. 무료 티어 일시정지 방지 — 일일 health check

**무료 플랜은 7일간 DB 활동이 부족하면 프로젝트를 일시정지한다.** 정지되면 읽기·쓰기·연결이
전부 막히고(데이터는 디스크에 보존), 대시보드에서 수동 복구해야 한다. 90일 넘게 방치하면
원클릭 복구가 막힌다.

**주간 크론만으로는 부족하다.** 기준이 "매일 몇 건의 요청" 수준인데 주간 리프레시는 7일에 한
번이라 정확히 경계선에 걸리고, 판정 시점과 어긋나면 정지될 수 있다. 그리고 **정지된 상태에서
크론이 돌면 주간 리프레시 자체가 실패한다** — 가장 필요한 순간에 죽는 구조다.

실사용이 있으면 자연히 해결된다(배우자가 매일 체크인하면 그게 곧 DB 활동이다). 문제는 며칠
쓰지 않는 기간이므로, **매일 도는 가벼운 health check**를 별도 크론으로 둔다.

- 하는 일: `checkins`에 대한 최소 비용 쿼리 1회(예: `select id limit 1`). secret 키로 호출한다.
- 빈도: 매일 1회. 주간 리프레시와 **별도 크론 엔트리**로 둔다(주간 작업 실패가 health check를
  같이 죽이면 안 된다).
- 실패 시: 조용히 넘기지 않고 텔레그램으로 알린다. health check 실패는 "이미 정지됐거나
  곧 정지된다"는 신호다.
- 정지된 상태를 감지하면 그 사실을 명시적으로 알린다 — 수동 복구가 필요하기 때문이다.

## 영향 범위

| 파일/영역 | 변경 |
|---|---|
| `src/routine-jammy/sheet_client.py` | 삭제 → `supabase_client.py` 신규 |
| `src/routine-jammy/weekly_refresh.py` | import 한 줄 + 호출부 |
| `docs/app.js` | POST 대상을 PostgREST로, `note`/`reflection`을 `payload`로 감싸기, `x-routine-token` 헤더 전송, **`Prefer: return=minimal` 필수**(아래) |
| `docs/config.js` | Supabase URL + publishable 키 (공개 전제 키라 커밋 안전) |
| `apps-script/` 전체 | **삭제** (`Code.gs`, `migrate-person-column.gs`, `README.md`) |
| `specs/plans/2026-07-31-sheet-migration-runbook.md` | **삭제** (마이그레이션할 시트가 없었음) |
| `.env` | `ROUTINE_APPS_SCRIPT_URL`/`ROUTINE_SHARED_SECRET` → `SUPABASE_URL`/`SUPABASE_SECRET_KEY` |
| `supabase/schema.sql` (신규) | `checkins` + `person_write_tokens` 테이블, `person_for_token()` 함수, 인덱스·CHECK·컬럼단위 GRANT·RLS·토큰 바인딩 INSERT 정책, 토큰 발급 |
| `tests/test_supabase_client.py` (신규) | 중복제거·payload 펼치기 단위 테스트 (네트워크 없음) |
| `tests/test_rls_live.py` (신규) | §S-6 RLS 검증 (네트워크 필요, 분리 표시) |
| `src/routine-jammy/health_check.py` (신규) | §S-7 일일 health check (별도 크론 엔트리) |
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
| OQ-1 | **해결** — 무료 티어 일시정지는 실질 리스크였다(주 1회 크론은 "매일 몇 건" 기준의 경계선이고, 정지 상태에서 크론이 돌면 주간 리프레시가 실패한다). §S-7의 일일 health check로 대응한다. 남은 확인: 실제 운영에서 정지가 발생하지 않는지 첫 2~3주 관찰 |
| OQ-2 | **해결** — 2025년 11월부터 **신규 프로젝트에는 레거시 키가 발급되지 않는다.** 새로 만들면 `sb_publishable_*`/`sb_secret_*`만 받으므로 선택의 여지가 없다. 새 방식은 개별 폐기가 가능하고(옛 `service_role`은 교체 시 전 세션 무효화), secret 키가 브라우저에서 오면 게이트웨이가 거부해 오용을 구조적으로 막는다 |
| OQ-3 | **해결** — 설계 리뷰에서 `with check (true)`가 변조를 전혀 막지 못한다는 것이 드러나(C-2 정정 참고), 사람별 쓰기 토큰을 **지금** 넣기로 했다(§S-2.1). 익명 삽입이 불가해지면서 용량 고갈 DoS 경로도 함께 닫혔다 |
| **OQ-4** | **신규·미해결** — 토큰 보유자가 자기 person_id로 넣을 수 있는 **행 수**에는 제한이 없다. 실수든 고의든 대량 삽입이 가능하다. 지금 제한을 걸지, 실제 문제가 관측된 뒤에 걸지 |

## 참고

- [Understanding API keys — Supabase Docs](https://supabase.com/docs/guides/getting-started/api-keys)
- [Migrating to publishable and secret API keys — Supabase Docs](https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys)
- [Upcoming changes to Supabase API Keys — Changelog](https://supabase.com/changelog/29260-upcoming-changes-to-supabase-api-keys)
- [Project Pausing — Supabase Docs](https://supabase.com/docs/guides/platform/free-project-pausing)
- [Supabase Security: Exposed Anon Keys, RLS, and Misconfigurations](https://www.stingrai.io/blog/supabase-powerful-but-one-misconfiguration-away-from-disaster)
- [AI Agents Know About Supabase. They Don't Always Use It Right. — Supabase Blog](https://supabase.com/blog/supabase-agent-skills)
- [Supabase Free Tier Guide](https://infrafree.dev/en-us/provider/supabase)
