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

const RoutineLogic = { completionRatio, isDayComplete };

if (typeof module !== 'undefined' && module.exports) {
  module.exports = RoutineLogic;
} else {
  window.RoutineLogic = RoutineLogic;
}
