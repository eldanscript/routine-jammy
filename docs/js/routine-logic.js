// Pure functions shared between the browser app and the Node test suite.
// No DOM access here — keep this file testable with `node --test`.

function completionRatio(responses, item) {
  const relevant = responses.filter((response) => response.item === item);
  const checkedCount = relevant.filter((response) => response.checked).length;
  return relevant.length === 0 ? 0 : checkedCount / 7;
}

function isDayComplete(dayTasks, checkedItems) {
  return dayTasks.every((task) => checkedItems.includes(task));
}

// items.json이 없거나 fetch가 실패하면(meta === null) 섹션 구분 없는 플랫 목록 하나로
// 강등한다 — km 입력·커스텀 관리는 meta에 의존하므로 이 경로에서는 함께 비활성화된다
// (app.js 쪽에서 처리).
function groupTasksBySection(tasks, customItems, meta) {
  if (!meta) {
    return [{
      id: 'all', title: '전체',
      items: tasks.map((task) => ({ id: task, label: task, isCustom: false })),
    }];
  }

  const sections = meta.sections.map((section) => ({ id: section.id, title: section.title, items: [] }));
  const sectionById = {};
  sections.forEach((section) => { sectionById[section.id] = section; });
  const fallback = sectionById.other || sections[sections.length - 1];

  tasks.forEach((task) => {
    const target = sectionById[meta.groups[task]] || fallback;
    target.items.push({ id: task, label: task, isCustom: false });
  });

  (customItems || []).forEach((custom) => {
    const target = sectionById[custom.section] || fallback;
    target.items.push({ id: custom.name, label: custom.name, isCustom: true });
  });

  return sections;
}

// metricsState: {"<day>":{"<item>":{"km":5.2}}} — 이미 특정 주로 스코프된 상태를 받는다
// (localStorage 키가 weekId를 포함하므로).
function weeklyKmTotal(metricsState) {
  let total = 0;
  Object.values(metricsState || {}).forEach((dayMetrics) => {
    Object.values(dayMetrics || {}).forEach((itemMetrics) => {
      if (itemMetrics && typeof itemMetrics.km === 'number') {
        total += itemMetrics.km;
      }
    });
  });
  return Math.round(total * 10) / 10;
}

const RESERVED_ITEM_NAMES = new Set(['아점', '저녁', '회고']);

// 유효하면 null, 무효면 사용자에게 보여줄 이유 문자열을 낸다.
// reservedSet: 이미 존재하는 tasks·suggestions·커스텀 이름 전체(중복 검사용) — 예약어
// (아점/저녁/회고)는 호출자가 아니라 이 함수가 항상 고정으로 검사한다.
function validateCustomItemName(name, reservedSet) {
  const trimmed = (name || '').trim();
  if (trimmed === '') return '이름을 입력해주세요';
  if (trimmed.length > 30) return '30자 이내로 입력해주세요';
  if (RESERVED_ITEM_NAMES.has(trimmed)) return '사용할 수 없는 이름이에요';
  if (reservedSet && reservedSet.has(trimmed)) return '이미 있는 항목이에요';
  return null;
}

// raw 입력을 파싱·검증한다. 유효하지 않으면 null — 어떤 경로로도 poison 값이
// 저장·전송되지 않도록 호출자가 null을 저장/전송 안 하고 이전 값으로 되돌린다.
function parseKmInput(raw, min, max) {
  const normalized = (raw || '').trim().replace(/,/g, '.');
  if (normalized === '') return null;
  const value = parseFloat(normalized);
  if (!Number.isFinite(value)) return null;
  if (value < min || value > max) return null;
  return Math.round(value * 10) / 10;
}

const RoutineLogic = {
  completionRatio, isDayComplete,
  groupTasksBySection, weeklyKmTotal, validateCustomItemName, parseKmInput,
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = RoutineLogic;
} else {
  window.RoutineLogic = RoutineLogic;
}
