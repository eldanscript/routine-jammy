const test = require('node:test');
const assert = require('node:assert/strict');
const { completionRatio, isDayComplete } = require('../../docs/js/routine-logic.js');

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
