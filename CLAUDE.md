# routine-jammy — 배우자/친구를 위한 파스텔톤 주간 루틴 관리 PWA

## Project Overview
아이폰에서 홈 화면에 추가해 쓰는 정적 PWA. 운동·식단·바이올린·회복 루틴을 요일별로 보여주고
체크인하면 Supabase로 자동 동기화된다. 매주 일요일 18:00 KST에 dev-agent-team이
지난주 결과를 리뷰하고, 루틴을 미세 보완하고, 다음 주 페이지를 다시 생성해 같은 GitHub
Pages URL에 배포한다. 대상 사용자는 Claude를 직접 쓰지 않는 제3자(배우자/친구)이며, 오퍼레이터
(rainny)가 그 사람의 아이폰을 직접 만질 수 있는 관계다.

## Tech Stack
| 항목 | 기술 |
|---|---|
| 프런트엔드 | 정적 HTML + Vanilla JS (빌드 도구 없음), `docs/`가 GitHub Pages 소스 |
| 배포 | GitHub Pages (public repo, `eldanscript/routine-jammy`) |
| 데이터 동기화 | Supabase (Postgres + PostgREST). 공개 키는 RLS 하에 INSERT만, 서버는 secret 키로 읽는다 |
| 자동화 | OS crontab (일요일 18:00 KST, `weekly_refresh.py` 직접 실행) + Telegram 봇 알림. dev-agent-team의 CronCreate/PushNotification은 세션 종속적이라 부적합해 채택하지 않음 |
| 자동화 로직 | Python (`src/routine-jammy/`) |
| 디자인 자산 | `docs/assets/` (아이콘·스티커·히어로 이미지·tokens.css, 사용자 제공 kit) |

## Agent 구성
| Agent | 기능 | 상태 |
|---|---|---|
| architect | 초기 상세 설계(라우팅, 데이터 모델, API 계약) | 완료 |
| frontend-developer | `docs/` 정적 PWA 구현 | 완료 |
| backend-developer | Supabase 연동, 주간 리프레시 파이썬 스크립트, Telegram 알림 | 완료 |
| devops | GitHub Pages 활성화, 운영 런북 작성 | 완료 |
| reviewer | 태스크별 + 전체 브랜치 리뷰 | 완료 |

## Project Structure
```
routine-jammy/
  CLAUDE.md
  specs/                          # 브레인스토밍 설계 문서 (스펙)
    reference/sample-weekly-routine.pdf   # 사용자가 제공한 비주얼/콘텐츠 레퍼런스
  src/routine-jammy/               # 주간 리프레시 자동화 로직 (Python)
  tests/
  docs/                            # GitHub Pages 배포 소스 (정적 PWA)
    index.html, app.js, style.css
    assets/                        # 아이콘, 스티커, 히어로 이미지, tokens.css, PWA 아이콘
    manifest.webmanifest
  supabase/
    schema.sql                     # Supabase 테이블·RLS 정의
  history/
    data.json                      # 주차별 이력 로컬 미러
    YYYY-Www.md                    # 주차별 요약/회고
  .claude/
    skills/weekly-routine-refresh/SKILL.md   # 재사용 가능한 주간 생성 스킬
    agents/                        # 프로젝트 전용 override (현재 없음)
  requirements.txt
```

## Authentication
- GitHub: SSH 키 기반 (SSH-only, HTTPS 토큰 사용 안 함).
- **Supabase**: publishable 키는 `docs/config.js`에 커밋한다(공개 전제 키). secret 키와
  사람별 쓰기 토큰은 `.env`에만 두고 커밋하지 않는다. 접근 통제는 DB의 RLS가 한다 —
  스키마는 `supabase/schema.sql`, 근거는 `specs/2026-07-31-supabase-storage-design.md`.

---

## Knowledge Base (optional)
없음.

---

## 개발 환경 — dev-agent-team

이 프로젝트는 `~/.claude/agents/`의 글로벌 sub-agent 로스터(architect, design-reviewer,
developer, backend-developer, frontend-developer, ui-designer, devops, test-author, tester,
reviewer)와 글로벌 커맨드(`/feature`, `/new-project`)를 그대로 상속한다. 로컬
`.claude/agents/`에는 이 프로젝트만의 override(있다면)만 둔다.

원격(Slack 등)에서 이 프로젝트를 다루려면 `~/dev-agent-team/registry.json`에 짧은 이름 →
이 프로젝트 절대경로를 등록한다.

## 금지 사항 (프로젝트 특화)
- `docs/`는 GitHub Pages 배포 소스다 — 여기에 스펙/문서를 섞지 않는다(스펙은 `specs/`에).
- 대상 사용자(배우자/친구)의 실제 신체 정보(체중 등 민감할 수 있는 수치)를 커밋 메시지나
  공개 레포 내용에 노출하지 않는다. 필요한 수치는 Supabase(RLS로 접근 제어)에만 둔다.
