const test = require('node:test');
const assert = require('node:assert/strict');
const { completionRatio, isDayComplete } = require('../../docs/js/routine-logic.js');

test('completionRatio counts checked responses for one item over 7 days', () => {
  const responses = [
    { item: '운동', checked: true },
    { item: '운동', checked: true },
    { item: '운동', checked: false },
    { item: '물', checked: true },
  ];
  assert.equal(completionRatio(responses, '운동'), 2 / 7);
  assert.equal(completionRatio(responses, '물'), 1 / 7);
  assert.equal(completionRatio(responses, '바이올린'), 0);
});

test('isDayComplete is true only when every task for the day is checked', () => {
  assert.equal(isDayComplete(['운동', '물'], ['운동', '물']), true);
  assert.equal(isDayComplete(['운동', '물'], ['운동']), false);
});
