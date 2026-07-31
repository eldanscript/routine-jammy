/**
 * 1회용 마이그레이션: person 컬럼이 없던 시절의 기존 행에 'jammy'를 채운다.
 *
 * 실행 방법: Apps Script 편집기에서 이 파일을 추가하고 migratePersonColumn 함수를
 * 한 번 실행한다. 두 번 실행해도 안전하다(이미 채워진 행은 건드리지 않는다).
 *
 * 실행 전 반드시 스프레드시트 사본을 만들어 둘 것.
 */
function migratePersonColumn() {
  const BACKFILL_PERSON = 'jammy';
  const spreadsheet = getSpreadsheet_();
  const report = [];

  [
    { name: RESPONSES_SHEET_NAME, oldHeader: ['weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'note', 'timestamp'] },
    { name: REFLECTIONS_SHEET_NAME, oldHeader: ['weekId', 'good', 'blocker', 'change'] },
  ].forEach(function (target) {
    const sheet = spreadsheet.getSheetByName(target.name);
    if (!sheet) {
      report.push(target.name + ': 시트 없음, 건너뜀');
      return;
    }
    const values = sheet.getDataRange().getValues();
    if (values.length === 0) {
      report.push(target.name + ': 빈 시트, 건너뜀');
      return;
    }
    if (values[0][0] === 'person') {
      report.push(target.name + ': 이미 마이그레이션됨, 건너뜀');
      return;
    }

    sheet.insertColumnBefore(1);
    sheet.getRange(1, 1).setValue('person');
    const rowCount = values.length - 1;
    if (rowCount > 0) {
      const backfill = [];
      for (let i = 0; i < rowCount; i++) {
        backfill.push([BACKFILL_PERSON]);
      }
      sheet.getRange(2, 1, rowCount, 1).setValues(backfill);
    }
    report.push(target.name + ': ' + rowCount + '행에 person=' + BACKFILL_PERSON + ' 채움');
  });

  Logger.log(report.join('\n'));
  return report.join('\n');
}
