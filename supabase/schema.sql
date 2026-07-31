-- routine-jammy — Supabase 스키마
--
-- 적용: Supabase 대시보드 > SQL Editor 에 전체를 붙여넣고 실행.
-- 여러 번 실행해도 안전하다(전부 IF NOT EXISTS / DROP IF EXISTS 사용).
--
-- 설계 근거는 specs/2026-07-31-supabase-storage-design.md 참고.
--
-- 핵심 구조:
--   브라우저는 쓰기 전용이므로 공개 키에 INSERT만 허용하고 SELECT/UPDATE/DELETE는 정책을
--   만들지 않는다(Postgres 기본 거부). 덮어쓰기 대신 append-only로 쌓고, 읽을 때
--   (person_id, week_id, day, item)별 created_at 최대 행만 취한다.
--
--   ★ 다만 "INSERT만 허용"은 그 자체로 변조를 막지 못한다. person_id에 제약이 없으면
--     누구나 남의 person_id로 새 행을 넣을 수 있고, 최신승자 규칙 때문에 그 행이 권위 있는
--     값이 되어 UPDATE와 똑같은 효과를 낸다. 그래서 INSERT를 사람별 토큰에 묶는다.

-- ---------------------------------------------------------------------------
-- 1. 사람별 쓰기 토큰
--
--    토큰은 그 사람의 고유 링크에 담겨 전달된다(?person=jammy&t=<토큰>).
--    저장소에 커밋하지 않는다. 한 사람의 링크가 유출돼도 그 사람의 쓰기 권한만 넘어가며,
--    이는 기존 신뢰 모델("고유 링크를 아는 사람 = 그 사람")과 동일한 수준이다.
-- ---------------------------------------------------------------------------

create table if not exists public.person_write_tokens (
  token       text        primary key,
  person_id   text        not null,
  created_at  timestamptz not null default now(),
  revoked_at  timestamptz
);

comment on table public.person_write_tokens is
  '사람별 쓰기 토큰. anon은 이 표를 직접 읽지 못하며, person_for_token() 함수를 통해서만 해석된다.';
comment on column public.person_write_tokens.revoked_at is
  'NULL이 아니면 폐기된 토큰. 링크가 유출됐을 때 이 값을 채우면 즉시 무효화된다.';

create index if not exists person_write_tokens_person_idx
  on public.person_write_tokens (person_id);

-- anon은 이 표에 어떤 권한도 갖지 않는다. 토큰 목록을 열거할 수 없어야 한다.
revoke all on table public.person_write_tokens from anon, authenticated;

-- ---------------------------------------------------------------------------
-- 2. 토큰 해석 함수
--
--    security definer 이므로 함수 소유자 권한으로 실행된다 — anon이 토큰 표를 직접 읽지
--    않고도 자기 토큰에 해당하는 person_id를 알아낼 수 있다.
--    search_path를 고정해 함수 하이재킹을 막는다(security definer의 표준 주의사항).
-- ---------------------------------------------------------------------------

create or replace function public.person_for_token()
returns text
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select t.person_id
    from public.person_write_tokens t
   where t.token = nullif(
           current_setting('request.headers', true)::json ->> 'x-routine-token', ''
         )
     and t.revoked_at is null
$$;

comment on function public.person_for_token() is
  '요청 헤더 x-routine-token 을 person_id로 해석한다. 토큰이 없거나 폐기됐으면 NULL을 낸다.';

revoke all on function public.person_for_token() from public;
grant execute on function public.person_for_token() to anon;

-- ---------------------------------------------------------------------------
-- 3. 체크인 테이블
-- ---------------------------------------------------------------------------

create table if not exists public.checkins (
  id          bigint generated always as identity primary key,
  person_id   text        not null,
  week_id     text        not null,
  day         text        not null,
  item        text        not null,
  checked     boolean     not null,
  payload     jsonb       not null default '{}'::jsonb,
  client_ts   timestamptz,                       -- 브라우저가 보낸 시각. 신뢰하지 않는다
  created_at  timestamptz not null default now() -- 서버 시각. "최신 승자" 판정 기준
);

comment on table public.checkins is
  'append-only 체크인 기록. 덮어쓰지 않고 매번 새 행을 넣는다. 읽을 때 (person_id, week_id, day, item)별 created_at 최대 행만 취한다.';
comment on column public.checkins.created_at is
  '서버가 찍는 시각. 최신 판정의 유일한 기준이며 클라이언트는 이 컬럼에 INSERT할 권한이 없다.';
comment on column public.checkins.client_ts is
  '브라우저가 보낸 시각. 진단용이며 판정에 쓰지 않는다(시계가 틀리거나 조작될 수 있음).';
comment on column public.checkins.payload is
  '아이템 종류별 데이터. 해석 규칙은 저장소의 catalog.json ruleType이 갖고 있다. logging→{"note":...}, 회고→{"good","blocker","change"}, binaryCheck→{}.';

-- ---------------------------------------------------------------------------
-- 4. 제약 — 유효한 토큰을 가진 사람의 실수·남용을 좁힌다
--    (토큰 없는 외부인은 3의 정책에서 이미 막힌다)
-- ---------------------------------------------------------------------------

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'checkins_person_id_len') then
    alter table public.checkins add constraint checkins_person_id_len
      check (char_length(person_id) between 1 and 64);
  end if;

  if not exists (select 1 from pg_constraint where conname = 'checkins_week_id_len') then
    alter table public.checkins add constraint checkins_week_id_len
      check (char_length(week_id) between 1 and 64);
  end if;

  if not exists (select 1 from pg_constraint where conname = 'checkins_item_len') then
    alter table public.checkins add constraint checkins_item_len
      check (char_length(item) between 1 and 64);
  end if;

  -- day는 고정 집합이다. 앱이 한국어 요일만 쓰므로 값을 못박아 쓰레기를 좁힌다.
  if not exists (select 1 from pg_constraint where conname = 'checkins_day_valid') then
    alter table public.checkins add constraint checkins_day_valid
      check (day in ('월','화','수','목','금','토','일'));
  end if;

  -- payload는 반드시 JSON 오브젝트여야 한다(배열/스칼라/null 거부).
  if not exists (select 1 from pg_constraint where conname = 'checkins_payload_object') then
    alter table public.checkins add constraint checkins_payload_object
      check (jsonb_typeof(payload) = 'object');
  end if;

  -- 거대 JSON 삽입 차단.
  if not exists (select 1 from pg_constraint where conname = 'checkins_payload_size') then
    alter table public.checkins add constraint checkins_payload_size
      check (pg_column_size(payload) <= 4096);
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- 5. 인덱스 — 크론의 유일한 조회 패턴
-- ---------------------------------------------------------------------------

create index if not exists checkins_person_week_idx
  on public.checkins (person_id, week_id);

-- ---------------------------------------------------------------------------
-- 6. 권한 (RLS와 독립된 두 번째 방어선)
--
--    Supabase는 public 스키마의 새 테이블에 기본 권한을 넓게 주는 설정이 있을 수 있으므로,
--    먼저 전부 회수한 뒤 필요한 것만 다시 준다. RLS가 잘못 설정돼도 GRANT가 없으면
--    SELECT는 막힌다 — 두 장치가 동시에 실패해야 데이터가 샌다.
--
--    ★ 컬럼 단위로 INSERT를 준다: id와 created_at은 주지 않는다.
--      created_at이 "최신 승자" 판정 기준이므로, 클라이언트가 이 값을 지정할 수 있으면
--      시각을 위조해 남의 최신 기록을 덮어쓴 것처럼 만들 수 있다.
--      권한을 주지 않으면 항상 서버의 default now()가 쓰인다.
-- ---------------------------------------------------------------------------

revoke all on table public.checkins from anon, authenticated;

grant usage on schema public to anon;
grant insert (person_id, week_id, day, item, checked, payload, client_ts)
  on table public.checkins to anon;

-- ---------------------------------------------------------------------------
-- 7. RLS — 이 설계의 핵심 보안 경계
--
--    ★ enable row level security 를 빠뜨리면 공개 키로 전부 읽힌다.
--      정책을 "안 만든 것"이 곧 차단이므로, RLS 활성화 자체가 유일한 사고 지점이다.
--      적용 후 반드시 검증(tests/test_rls_live.py)을 돌려 실제로 막히는지 확인할 것.
-- ---------------------------------------------------------------------------

alter table public.checkins            enable row level security;
alter table public.person_write_tokens enable row level security;

-- 재실행 안전성을 위해 기존 정책을 지우고 다시 만든다.
drop policy if exists checkins_insert_anon on public.checkins;

-- ★ with check (true) 가 아니다.
--   토큰이 가리키는 person_id와 일치할 때만 삽입을 허용한다. 토큰이 없거나 폐기됐으면
--   person_for_token()이 NULL을 내고, `person_id = NULL`은 참이 아니므로 삽입이 거부된다.
create policy checkins_insert_own
  on public.checkins
  for insert
  to anon
  with check (person_id = public.person_for_token());

-- SELECT / UPDATE / DELETE 정책은 의도적으로 만들지 않는다.
-- person_write_tokens에는 어떤 정책도 만들지 않는다(anon 접근 전면 차단).
-- secret 키(sb_secret_*)는 RLS를 우회하므로 주간 크론이 전부 읽는다.

-- ---------------------------------------------------------------------------
-- 8. 토큰 발급 (사람 추가 시 이 블록만 수정해 실행)
--
--    gen_random_uuid()는 pgcrypto 없이 Postgres 13+ 내장이다.
--    발급된 토큰은 이 SQL의 출력으로 한 번 보이며, 그 값을 그 사람의 링크에 넣는다.
--    저장소에 커밋하지 않는다.
-- ---------------------------------------------------------------------------

insert into public.person_write_tokens (token, person_id)
select replace(gen_random_uuid()::text, '-', ''), 'jammy'
where not exists (
  select 1 from public.person_write_tokens
   where person_id = 'jammy' and revoked_at is null
);

-- ---------------------------------------------------------------------------
-- 9. 적용 확인 — 아래 두 조회의 결과를 눈으로 확인할 것
-- ---------------------------------------------------------------------------

select
  (select count(*) from pg_policies
     where schemaname='public' and tablename='checkins')                as checkins_policies,
  (select count(*) from pg_policies
     where schemaname='public' and tablename='person_write_tokens')     as token_policies,
  (select relrowsecurity from pg_class
     where oid='public.checkins'::regclass)                             as checkins_rls,
  (select relrowsecurity from pg_class
     where oid='public.person_write_tokens'::regclass)                  as tokens_rls,
  (select count(*) from information_schema.column_privileges
     where table_schema='public' and table_name='checkins'
       and grantee='anon' and privilege_type='INSERT')                  as anon_insert_columns;
-- 기대값: checkins_policies=1, token_policies=0, checkins_rls=true,
--         tokens_rls=true, anon_insert_columns=7

-- ★ jammy의 쓰기 토큰. 이 값을 링크에 넣어 전달한다. 커밋 금지.
select person_id, token from public.person_write_tokens where revoked_at is null;
