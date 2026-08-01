const test = require('node:test');
const assert = require('node:assert/strict');
const {
  completionRatio, isDayComplete,
  groupTasksBySection, weeklyKmTotal, validateCustomItemName, parseKmInput,
} = require('../../docs/js/routine-logic.js');

const META = {
  sections: [
    { id: 'exercise', title: '운동' },
    { id: 'medication', title: '약/영양제' },
    { id: 'other', title: '기타' },
  ],
  groups: {
    '슬로우 조깅': 'exercise', '스쿼트': 'exercise',
    '고지혈증약': 'medication',
    '간식섭취': 'other', '바이올린': 'other',
  },
  metrics: { '슬로우 조깅': { key: 'km', unit: 'km', min: 0.1, max: 99 } },
  suggestions: { exercise: ['푸시업', '버피'], medication: [] },
};

test('completionRatio counts checked responses for one item over 7 days', () => {
  const responses = [
    { item: '슬로우 조깅', checked: true },
    { item: '슬로우 조깅', checked: true },
    { item: '슬로우 조깅', checked: false },
    { item: '물', checked: true },
  ];
  assert.equal(completionRatio(responses, '슬로우 조깅'), 2 / 7);
  assert.equal(completionRatio(responses, '물'), 1 / 7);
  assert.equal(completionRatio(responses, '바이올린'), 0);
});

test('isDayComplete is true only when every task for the day is checked', () => {
  assert.equal(isDayComplete(['슬로우 조깅', '물'], ['슬로우 조깅', '물']), true);
  assert.equal(isDayComplete(['슬로우 조깅', '물'], ['슬로우 조깅']), false);
});

test('groupTasksBySection groups tasks by items.json group and appends custom items', () => {
  const tasks = ['슬로우 조깅', '스쿼트', '고지혈증약', '간식섭취'];
  const customItems = [{ name: '오메가3', section: 'medication' }];
  const sections = groupTasksBySection(tasks, customItems, META);

  assert.deepEqual(sections.map((s) => s.id), ['exercise', 'medication', 'other']);
  assert.deepEqual(sections[0].items, [
    { id: '슬로우 조깅', label: '슬로우 조깅', isCustom: false },
    { id: '스쿼트', label: '스쿼트', isCustom: false },
  ]);
  assert.deepEqual(sections[1].items, [
    { id: '고지혈증약', label: '고지혈증약', isCustom: false },
    { id: '오메가3', label: '오메가3', isCustom: true },
  ]);
  assert.deepEqual(sections[2].items, [
    { id: '간식섭취', label: '간식섭취', isCustom: false },
  ]);
});

test('groupTasksBySection falls back to "other" for tasks missing from groups', () => {
  const sections = groupTasksBySection(['알수없는항목'], [], META);
  const other = sections.find((s) => s.id === 'other');
  assert.deepEqual(other.items, [{ id: '알수없는항목', label: '알수없는항목', isCustom: false }]);
});

test('groupTasksBySection collapses into one flat section when meta is null', () => {
  const sections = groupTasksBySection(['슬로우 조깅', '스쿼트'], [], null);
  assert.equal(sections.length, 1);
  assert.deepEqual(sections[0].items, [
    { id: '슬로우 조깅', label: '슬로우 조깅', isCustom: false },
    { id: '스쿼트', label: '스쿼트', isCustom: false },
  ]);
});

test('weeklyKmTotal sums km across all days and items, rounded to one decimal', () => {
  const metrics = {
    '월': { '슬로우 조깅': { km: 3.25 } },
    '수': { '슬로우 조깅': { km: 5.05 } },
    '금': { '슬로우 조깅': { km: 2 } },
  };
  assert.equal(weeklyKmTotal(metrics), 10.3);
});

test('weeklyKmTotal returns 0 for empty or missing metrics', () => {
  assert.equal(weeklyKmTotal({}), 0);
  assert.equal(weeklyKmTotal(undefined), 0);
});

test('validateCustomItemName rejects empty, too-long, reserved, and duplicate names', () => {
  const reserved = new Set(['스쿼트', '푸시업']);
  assert.equal(validateCustomItemName('', reserved), '이름을 입력해주세요');
  assert.equal(validateCustomItemName('   ', reserved), '이름을 입력해주세요');
  assert.equal(validateCustomItemName('가'.repeat(31), reserved), '30자 이내로 입력해주세요');
  assert.equal(validateCustomItemName('회고', reserved), '사용할 수 없는 이름이에요');
  assert.equal(validateCustomItemName('아점', reserved), '사용할 수 없는 이름이에요');
  assert.equal(validateCustomItemName('스쿼트', reserved), '이미 있는 항목이에요');
});

test('validateCustomItemName accepts a valid trimmed new name', () => {
  const reserved = new Set(['스쿼트']);
  assert.equal(validateCustomItemName('  런닝머신  ', reserved), null);
});

// Regression for a reviewer-caught bug: app.js's reservedCustomNames() used to build its
// dedup set as `[...dayTasks, ...itemsMeta.suggestions.exercise, ...customItems]`, which
// unconditionally reserved every suggestion-chip name (캐틀벨 스윙/푸시업/버피/...) even
// before the user ever added one — so clicking a suggestion chip, or typing its exact
// name, always failed as "이미 있는 항목이에요". The fix mirrors renderCustomItemManager's
// `remaining` filter: only day tasks + names the user has *actually* added are reserved.
// These two tests reproduce reservedCustomNames' (fixed) set-building logic directly,
// since it lives inside app.js's IIFE and isn't independently requireable from Node.
function reservedCustomNames(dayTasks, customItems) {
  return new Set([...dayTasks, ...customItems.map((custom) => custom.name)]);
}

test('a suggestion-list name not yet added as a custom item is accepted (not falsely reserved)', () => {
  const dayTasks = ['슬로우 조깅', '스쿼트'];
  const customItems = []; // 아직 아무 것도 추가하지 않은 상태 — suggestions는 여전히 미사용
  const reserved = reservedCustomNames(dayTasks, customItems);
  assert.equal(validateCustomItemName('푸시업', reserved), null);
});

test('a name that is already an active custom item is still rejected as duplicate', () => {
  const dayTasks = ['슬로우 조깅', '스쿼트'];
  const customItems = [{ name: '푸시업', section: 'exercise' }];
  const reserved = reservedCustomNames(dayTasks, customItems);
  assert.equal(validateCustomItemName('푸시업', reserved), '이미 있는 항목이에요');
});

test('parseKmInput accepts comma decimals within range, rounded to one decimal', () => {
  assert.equal(parseKmInput('5,25', 0.1, 99), 5.3);
  assert.equal(parseKmInput(' 3.0 ', 0.1, 99), 3);
});

test('parseKmInput rejects out-of-range, non-numeric, and empty input', () => {
  assert.equal(parseKmInput('100', 0.1, 99), null);
  assert.equal(parseKmInput('0', 0.1, 99), null);
  assert.equal(parseKmInput('abc', 0.1, 99), null);
  assert.equal(parseKmInput('', 0.1, 99), null);
  assert.equal(parseKmInput('   ', 0.1, 99), null);
});
