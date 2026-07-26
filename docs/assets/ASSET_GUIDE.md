# Weekly Routine web app assets

PDF의 파스텔 색감과 운동·식단·바이올린·회복 구조를 웹앱에 맞게 정리한 자산 패키지입니다.

## 권장 메뉴

데스크톱 사이드바는 `홈 → 주간 계획 → 운동 → 식단 → 오늘 체크 → 리포트 → 설정` 순서를 사용합니다. 모바일 하단 메뉴는 `홈 · 주간 · 체크 · 리포트` 네 항목만 유지하고, 운동·식단·설정은 주간 화면 또는 더보기에서 접근하게 구성합니다.

정확한 라우트와 아이콘 매핑은 `navigation.json`에 있습니다.

## 이미지 선택

- 데스크톱 히어로: `images/hero/dashboard-hero-1536.webp`
- 태블릿 히어로: `images/hero/dashboard-hero-1200.webp`
- 작은 화면 히어로: `images/hero/dashboard-hero-768.webp`
- 모바일 세로 카드: `images/hero/dashboard-hero-mobile-800x1000.webp`
- 공유 카드: `images/hero/open-graph-1200x630.webp`
- 운동·식단 카드: `images/stickers/*.webp`

웹앱 기본 히어로는 사람이나 얼굴이 없는 오브젝트 전용 이미지입니다. PDF에 사용한 인물 표지는 보존용으로 `images/pdf-source/`에만 포함되어 있습니다.

## 반응형 이미지 예시

```html
<picture>
  <source media="(max-width: 640px)" srcset="/assets/images/hero/dashboard-hero-mobile-800x1000.webp">
  <source media="(max-width: 1024px)" srcset="/assets/images/hero/dashboard-hero-768.webp">
  <img
    src="/assets/images/hero/dashboard-hero-1536.webp"
    alt="운동, 건강한 식사, 바이올린과 체크 노트"
    width="1536"
    height="1024"
  >
</picture>
```

## SVG 아이콘

개별 SVG는 `stroke="currentColor"`를 사용하므로 CSS의 `color`로 활성·비활성 상태를 제어할 수 있습니다.

```html
<img class="routine-icon" src="/assets/icons/nav-calendar.svg" alt="">
```

인라인 스프라이트를 사용하는 경우 `icons/icon-sprite.svg`의 심볼 ID를 참조합니다. `<svg>`에 `fill="none"`, `stroke="currentColor"`, `stroke-width="1.8"`, `stroke-linecap="round"`, `stroke-linejoin="round"`를 지정하세요.

## 디자인 토큰

- `tokens.json`: JavaScript·디자인 툴에서 사용
- `tokens.css`: 웹 프로젝트에 바로 import
- 본문 기본 폰트: Pretendard → Noto Sans KR → Apple SD Gothic Neo 순서
- 카드 라운드: 18px
- 최소 터치 영역: 44px
- 메뉴 아이콘: 24px

## 파일 구성

```text
icons/          메뉴·카테고리·상태 SVG
images/hero/    반응형 히어로와 공유 이미지
images/stickers/운동·식사·회복 카드 일러스트
images/pdf-source/ PDF 원본 비주얼
pwa/            앱 아이콘
navigation.json 메뉴 구조
tokens.*        색상·간격·타이포그래피
manifest.webmanifest PWA 메타데이터
asset-manifest.json 전체 파일 목록과 해시
```
