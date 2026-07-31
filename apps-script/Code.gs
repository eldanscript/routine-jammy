/**
 * routine-jammy Apps Script backend.
 * Deploy as a Web App (Execute as: Me, Who has access: Anyone with the link).
 * Before deploying, set two Script Properties (Project Settings > Script Properties):
 *   ROUTINE_SHARED_SECRET  - a random string, must match docs/config.js's sharedSecret
 *   ROUTINE_SHEET_ID       - the spreadsheet ID to write into
 */

const RESPONSES_SHEET_NAME = 'responses';
const REFLECTIONS_SHEET_NAME = 'reflections';
// 프론트가 person을 보내기 전까지의 하위 호환 기본값. 4단계에서 프론트가 항상 보내게 되면
// 그때도 이 기본값은 남겨둔다 - 옛 북마크로 들어온 요청이 조용히 사라지는 것보다 낫다.
const DEFAULT_PERSON_ = 'jammy';

function getSpreadsheet_() {
  const sheetId = PropertiesService.getScriptProperties().getProperty('ROUTINE_SHEET_ID');
  return SpreadsheetApp.openById(sheetId);
}

function getOrCreateSheet_(name, headerRow) {
  const spreadsheet = getSpreadsheet_();
  let sheet = spreadsheet.getSheetByName(name);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(name);
    sheet.appendRow(headerRow);
  }
  return sheet;
}

function checkSecret_(secret) {
  const expected = PropertiesService.getScriptProperties().getProperty('ROUTINE_SHARED_SECRET');
  return secret === expected;
}

function jsonResponse_(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse_({ ok: false, error: 'invalid request' });
  }

  if (!checkSecret_(body.secret)) {
    return jsonResponse_({ ok: false, error: 'invalid secret' });
  }

  const person = body.person || DEFAULT_PERSON_;

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = getOrCreateSheet_(RESPONSES_SHEET_NAME, [
      'person', 'weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'note', 'timestamp',
    ]);
    const data = sheet.getDataRange().getValues();
    let rowIndex = -1;
    for (let i = 1; i < data.length; i++) {
      if (data[i][0] === person && data[i][1] === body.weekId
          && data[i][2] === body.day && data[i][3] === body.item) {
        rowIndex = i + 1;
        break;
      }
    }
    const row = [
      person, body.weekId, body.day, body.item, body.checked,
      body.minutes === undefined || body.minutes === null ? '' : body.minutes,
      body.sleepHours === undefined || body.sleepHours === null ? '' : body.sleepHours,
      body.energy === undefined || body.energy === null ? '' : body.energy,
      body.note === undefined || body.note === null ? '' : body.note,
      body.timestamp,
    ];
    if (rowIndex > 0) {
      sheet.getRange(rowIndex, 1, 1, row.length).setValues([row]);
    } else {
      sheet.appendRow(row);
    }

    if (body.reflection) {
      const reflectionSheet = getOrCreateSheet_(REFLECTIONS_SHEET_NAME, ['person', 'weekId', 'good', 'blocker', 'change']);
      const reflectionData = reflectionSheet.getDataRange().getValues();
      let reflectionRow = -1;
      for (let i = 1; i < reflectionData.length; i++) {
        if (reflectionData[i][0] === person && reflectionData[i][1] === body.weekId) {
          reflectionRow = i + 1;
          break;
        }
      }
      const reflectionValues = [
        person,
        body.weekId,
        body.reflection.good === undefined || body.reflection.good === null ? '' : body.reflection.good,
        body.reflection.blocker === undefined || body.reflection.blocker === null ? '' : body.reflection.blocker,
        body.reflection.change === undefined || body.reflection.change === null ? '' : body.reflection.change,
      ];
      if (reflectionRow > 0) {
        reflectionSheet.getRange(reflectionRow, 1, 1, reflectionValues.length).setValues([reflectionValues]);
      } else {
        reflectionSheet.appendRow(reflectionValues);
      }
    }

    return jsonResponse_({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  if (!checkSecret_(e.parameter.secret)) {
    return jsonResponse_({ ok: false, error: 'invalid secret' });
  }
  const weekId = e.parameter.weekId;
  const person = e.parameter.person || DEFAULT_PERSON_;

  const sheet = getOrCreateSheet_(RESPONSES_SHEET_NAME, [
    'person', 'weekId', 'day', 'item', 'checked', 'minutes', 'sleepHours', 'energy', 'note', 'timestamp',
  ]);
  const data = sheet.getDataRange().getValues();
  const responses = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === person && data[i][1] === weekId) {
      responses.push({
        day: data[i][2],
        item: data[i][3],
        checked: data[i][4] === true || data[i][4] === 'TRUE',
        minutes: data[i][5],
        sleepHours: data[i][6],
        energy: data[i][7],
        note: data[i][8],
        timestamp: data[i][9],
      });
    }
  }

  const reflectionSheet = getOrCreateSheet_(REFLECTIONS_SHEET_NAME, ['person', 'weekId', 'good', 'blocker', 'change']);
  const reflectionData = reflectionSheet.getDataRange().getValues();
  let reflection = {};
  for (let i = 1; i < reflectionData.length; i++) {
    if (reflectionData[i][0] === person && reflectionData[i][1] === weekId) {
      reflection = { good: reflectionData[i][2], blocker: reflectionData[i][3], change: reflectionData[i][4] };
      break;
    }
  }

  return jsonResponse_({ person: person, weekId: weekId, responses: responses, reflection: reflection });
}
