(function () {
  const params = new URLSearchParams(location.search);
  const CONFIG = {
    supabaseUrl: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.supabaseUrl,
    publishableKey: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.publishableKey,
    personId: params.get('person') || 'jammy',
    writeToken: params.get('t') || '',
  };
  const QUEUE_KEY = 'routine-jammy:pending-checkins';
  const CUSTOM_ITEMS_KEY = 'routine-jammy:custom-items';
  const STICKER_BY_EXERCISE_TYPE = {
    slowJog: 'jogging', recoveryJog: 'jogging',
    strengthA: 'squat', strengthB: 'deadlift', strengthC: 'lunge',
    recoveryReflect: 'recovery',
  };

  let staticData = null;
  let weekData = null;
  let exerciseStats = null;
  let nutritionStats = null;
  // items.json fetch가 실패하면 null로 남는다 — 섹션 그룹핑은 플랫 목록으로 강등되고
  // (RoutineLogic.groupTasksBySection), km 입력·커스텀 관리는 이 값에 의존하므로 함께
  // 비활성화된다(렌더 쪽에서 itemsMeta 존재 여부로 분기).
  let itemsMeta = null;

  async function loadData() {
    const [staticResponse, weekResponse, exerciseStatsResponse, nutritionStatsResponse, itemsResponse] = await Promise.all([
      fetch('data/routine-static.json'),
      fetch('data/jammy/current-week.json'),
      fetch('data/jammy/exercise-stats.json'),
      fetch('data/jammy/nutrition-stats.json'),
      fetch('data/jammy/items.json'),
    ]);
    staticData = await staticResponse.json();
    weekData = await weekResponse.json();
    exerciseStats = exerciseStatsResponse.ok ? await exerciseStatsResponse.json() : null;
    nutritionStats = nutritionStatsResponse.ok ? await nutritionStatsResponse.json() : null;
    itemsMeta = itemsResponse.ok ? await itemsResponse.json() : null;
  }

  function todayIndex() {
    const jsDay = new Date().getDay(); // 0=Sun..6=Sat
    return jsDay === 0 ? 6 : jsDay - 1; // map to 월=0..일=6
  }

  function getCheckedState() {
    const raw = localStorage.getItem(`routine-jammy:checked:${weekData.weekId}`);
    return raw ? JSON.parse(raw) : {};
  }

  function setChecked(day, item, checked) {
    const state = getCheckedState();
    state[day] = state[day] || {};
    state[day][item] = checked;
    localStorage.setItem(`routine-jammy:checked:${weekData.weekId}`, JSON.stringify(state));
  }

  function getMealState() {
    const raw = localStorage.getItem(`routine-jammy:meals:${weekData.weekId}`);
    return raw ? JSON.parse(raw) : {};
  }

  function setMealNote(day, slot, text) {
    const state = getMealState();
    state[day] = state[day] || {};
    state[day][slot] = text;
    localStorage.setItem(`routine-jammy:meals:${weekData.weekId}`, JSON.stringify(state));
  }

  function getMetricsState() {
    const raw = localStorage.getItem(`routine-jammy:metrics:${weekData.weekId}`);
    return raw ? JSON.parse(raw) : {};
  }

  function setMetric(day, item, metric) {
    const state = getMetricsState();
    state[day] = state[day] || {};
    state[day][item] = metric;
    localStorage.setItem(`routine-jammy:metrics:${weekData.weekId}`, JSON.stringify(state));
  }

  function removeMetric(day, item) {
    const state = getMetricsState();
    if (state[day]) {
      delete state[day][item];
      if (Object.keys(state[day]).length === 0) delete state[day];
    }
    localStorage.setItem(`routine-jammy:metrics:${weekData.weekId}`, JSON.stringify(state));
  }

  function getCustomItems() {
    const raw = localStorage.getItem(CUSTOM_ITEMS_KEY);
    return raw ? JSON.parse(raw) : [];
  }

  function addCustomItem(name, section) {
    const items = getCustomItems();
    items.push({ name, section });
    localStorage.setItem(CUSTOM_ITEMS_KEY, JSON.stringify(items));
  }

  function removeCustomItem(name) {
    const items = getCustomItems().filter((item) => item.name !== name);
    localStorage.setItem(CUSTOM_ITEMS_KEY, JSON.stringify(items));
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function queueCheckin(payload) {
    const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    queue.push(payload);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  }

  // 체크인 payload를 테이블 컬럼 모양으로 바꾼다.
  // note / reflection / km 은 별도 컬럼이 아니라 payload JSONB 안으로 들어간다.
  function toRow(payload) {
    const extra = {};
    if (payload.note !== undefined) extra.note = payload.note;
    if (payload.reflection !== undefined) Object.assign(extra, payload.reflection);
    if (payload.km !== undefined) extra.km = payload.km;
    return {
      person_id: CONFIG.personId,
      week_id: payload.weekId,
      day: payload.day,
      item: payload.item,
      checked: payload.checked,
      payload: extra,
      client_ts: payload.timestamp,
    };
  }

  async function postCheckin(payload) {
    const response = await fetch(`${CONFIG.supabaseUrl}/rest/v1/checkins`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        apikey: CONFIG.publishableKey,
        Authorization: `Bearer ${CONFIG.publishableKey}`,
        'x-routine-token': CONFIG.writeToken,
        // anon에 SELECT 권한이 없다. 결과를 돌려달라고 하면 INSERT 전체가 실패한다.
        Prefer: 'return=minimal',
      },
      body: JSON.stringify(toRow(payload)),
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
  }

  // 리스크: 큐에 이미 쌓인 체크인이 있는 상태에서 새 체크인을 곧바로 직송하면, 서버에는
  // 새 체크인이 먼저 도착하고 이전 체크인이 나중에 도착할 수 있다 — latest-wins 저장이라
  // 순서가 뒤바뀌면 서버 상태가 실제 클릭 순서와 달라진다. 완화책: 큐가 비어있지 않으면
  // 직송하지 않고 큐에 넣은 뒤 flushQueue로 순서를 지켜 보낸다.
  let isFlushing = false;

  async function sendCheckin(payload) {
    if (!CONFIG.supabaseUrl || !CONFIG.writeToken) {
      queueCheckin(payload);
      return;
    }
    const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    if (queue.length > 0) {
      queueCheckin(payload);
      flushQueue();
      return;
    }
    try {
      await postCheckin(payload);
    } catch (error) {
      queueCheckin(payload);
    }
  }

  async function flushQueue() {
    if (!CONFIG.supabaseUrl || !CONFIG.writeToken) return;
    if (isFlushing) return; // 빠른 연속 체크로 재진입해도 같은 행을 중복 POST하지 않는다.
    isFlushing = true;
    try {
      while (true) {
        const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
        if (queue.length === 0) return;
        const next = queue[0];
        try {
          await postCheckin(next);
        } catch (error) {
          return;
        }
        const updatedQueue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
        const sentJson = JSON.stringify(next);
        const index = updatedQueue.findIndex((item) => JSON.stringify(item) === sentJson);
        if (index !== -1) updatedQueue.splice(index, 1);
        localStorage.setItem(QUEUE_KEY, JSON.stringify(updatedQueue));
      }
    } finally {
      isFlushing = false;
    }
  }

  function handleCheckboxChange(day, item) {
    return (event) => {
      const checked = event.target.checked;
      setChecked(day, item, checked);
      const payload = { weekId: weekData.weekId, day, item, checked, timestamp: new Date().toISOString() };
      if (checked) {
        const metricsState = getMetricsState();
        const itemMetrics = metricsState[day] && metricsState[day][item];
        if (itemMetrics && itemMetrics.km !== undefined) payload.km = itemMetrics.km;
      } else {
        const metricsState = getMetricsState();
        if (metricsState[day] && metricsState[day][item] && metricsState[day][item].km !== undefined) {
          removeMetric(day, item);
          const metricInput = event.target.closest('.check-item').querySelector('input.metric-input');
          if (metricInput) metricInput.value = '';
        }
      }
      sendCheckin(payload);
    };
  }

  function handleMetricInputBlur(event) {
    const input = event.target;
    const day = input.dataset.metricDay;
    const item = input.dataset.metricItem;
    const key = input.dataset.metricKey;
    const min = parseFloat(input.dataset.metricMin);
    const max = parseFloat(input.dataset.metricMax);

    const metricsState = getMetricsState();
    const previous = metricsState[day] && metricsState[day][item] && metricsState[day][item][key];
    const value = RoutineLogic.parseKmInput(input.value, min, max);

    if (value === null) {
      input.value = previous !== undefined ? previous : '';
      return;
    }
    input.value = value;
    if (value === previous) return;

    setMetric(day, item, { [key]: value });
    setChecked(day, item, true);
    const checkbox = input.closest('.check-item').querySelector('input[type="checkbox"]');
    if (checkbox) checkbox.checked = true;
    sendCheckin({
      weekId: weekData.weekId, day, item, checked: true, km: value,
      timestamp: new Date().toISOString(),
    });
  }

  function renderHome() {
    const today = weekData.days[todayIndex()];
    const stickerName = STICKER_BY_EXERCISE_TYPE[today.exercise.type] || 'jogging';
    const adjustmentsCard = weekData.appliedAdjustments
      ? `<section class="today-card butter"><h2>이번 주 보완</h2><ul>${weekData.appliedAdjustments.map((a) => `<li>${a}</li>`).join('')}</ul></section>`
      : '';
    return `
      <section class="hero-card">
        <picture>
          <source media="(max-width: 640px)" srcset="assets/images/hero/dashboard-hero-mobile-800x1000.webp">
          <img src="assets/images/hero/dashboard-hero-768.webp" alt="운동, 건강한 식사, 바이올린과 체크 노트">
        </picture>
      </section>
      <section class="today-card mint">
        <img class="sticker" src="assets/images/stickers/${stickerName}.webp" alt="">
        <h2>오늘 (${today.day}) · ${today.exercise.label}</h2>
        <p>${today.exercise.detail}</p>
      </section>
      <section class="today-card peach">
        <img class="sticker" src="assets/images/stickers/meal.webp" alt="">
        <h2>오늘의 식단</h2>
        <p>아점: ${today.meal.breakfast}</p>
        <p>저녁: ${today.meal.dinner}</p>
      </section>
      <section class="today-card lavender">
        <img class="sticker" src="assets/images/stickers/violin.webp" alt="">
        <h2>바이올린 ${staticData.violin.targetMinutes}분</h2>
      </section>
      ${adjustmentsCard}
    `;
  }

  function renderWeek() {
    const cards = weekData.days.map((day) => `
      <li class="week-card"><strong>${day.day} ${day.date.slice(5)}</strong><span>${day.exercise.label} · ${day.exercise.detail}</span></li>
    `).join('');
    return `
      <h2>이번 주 한눈에</h2>
      <ul class="week-list">${cards}</ul>
      <div class="week-links">
        <a href="#/exercise">운동 상세 보기</a>
        <a href="#/meals">식단 상세 보기</a>
        <a href="#/settings">설정</a>
      </div>
    `;
  }

  function renderExercise() {
    const strengthCards = ['A', 'B', 'C'].map((key) => {
      const block = staticData.exercise.strength[key];
      const items = (block.items || []).map((item) => `<li>${item.name} — ${item.detail}</li>`).join('');
      return `<div class="today-card lavender"><h3>${block.title}${block.day ? ' · ' + block.day : ''}</h3><ul>${items}</ul>${block.note ? `<p class="muted">${block.note}</p>` : ''}</div>`;
    }).join('');
    return `
      <h2>운동 루틴</h2>
      <p class="muted">${staticData.exercise.slowJog.intensity}</p>
      <div class="today-card mint">
        <h3>${staticData.exercise.slowJog.title}</h3>
        <ol>${staticData.exercise.slowJog.steps.map((step) => `<li>${step}</li>`).join('')}</ol>
      </div>
      ${strengthCards}
      <p class="muted">${staticData.exercise.conditionRule}</p>
    `;
  }

  function renderMeals() {
    const rows = weekData.days.map((day) => `<tr><td>${day.day}</td><td>${day.meal.breakfast}</td><td>${day.meal.dinner}</td></tr>`).join('');
    const foods = staticData.meal.proteinFoods.map((food) => `<li>${food.food} — ${food.protein}</li>`).join('');
    return `
      <h2>식단 루틴</h2>
      <p class="muted">${staticData.meal.target}</p>
      <div class="today-card peach"><strong>한 끼 공식</strong><p>${staticData.meal.formula}</p></div>
      <table class="meal-table"><thead><tr><th>요일</th><th>아점</th><th>저녁</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="today-card blue"><strong>단백질 식품표</strong><ul>${foods}</ul></div>
      <div class="today-card mint"><strong>배고플 때</strong><p>${staticData.meal.hungryTip}</p></div>
    `;
  }

  function renderCheckInSections(day, dayChecked, dayMetrics, customItems) {
    const sections = RoutineLogic.groupTasksBySection(day.tasks, customItems, itemsMeta);
    return sections.map((section) => {
      const itemsHtml = section.items.map((item) => {
        const idAttr = item.isCustom ? escapeHtml(item.id) : item.id;
        const labelText = item.isCustom ? escapeHtml(item.label) : item.label;
        const metric = itemsMeta && itemsMeta.metrics && itemsMeta.metrics[item.id];
        const currentMetric = dayMetrics[item.id] && dayMetrics[item.id][metric && metric.key];
        const metricHtml = metric ? `
          <input type="text" inputmode="decimal" maxlength="5" class="metric-input"
            data-metric-day="${day.day}" data-metric-item="${idAttr}" data-metric-key="${metric.key}"
            data-metric-min="${metric.min}" data-metric-max="${metric.max}"
            placeholder="${metric.unit}" value="${currentMetric !== undefined ? currentMetric : ''}">
        ` : '';
        return `
          <label class="check-item">
            <input type="checkbox" data-day="${day.day}" data-item="${idAttr}" ${dayChecked[item.id] ? 'checked' : ''}>
            ${labelText}
            ${metricHtml}
          </label>
        `;
      }).join('');
      return `<div class="check-section"><h4>${section.title}</h4><div class="check-grid">${itemsHtml}</div></div>`;
    }).join('');
  }

  function renderCustomItemManager(customItems) {
    if (!itemsMeta) return '';
    const suggestions = (itemsMeta.suggestions && itemsMeta.suggestions.exercise) || [];
    const remaining = suggestions.filter((name) => !customItems.some((custom) => custom.name === name));
    const chips = remaining.map((name) => `
      <button type="button" class="chip" data-suggestion="${escapeHtml(name)}">${escapeHtml(name)}</button>
    `).join('');
    const list = customItems.map((custom) => `
      <li>${escapeHtml(custom.name)} (${custom.section === 'medication' ? '약/영양제' : '운동'})
        <button type="button" class="chip-remove" data-remove-custom="${escapeHtml(custom.name)}">삭제</button>
      </li>
    `).join('');
    return `
      <div class="today-card custom-item-card">
        <strong>내 항목 추가</strong>
        <div class="custom-item-form">
          <select id="custom-item-section">
            <option value="exercise">운동</option>
            <option value="medication">약/영양제</option>
          </select>
          <input type="text" id="custom-item-name" maxlength="30" placeholder="예: 오메가3">
          <button type="button" id="custom-item-add" class="primary-button">추가</button>
        </div>
        ${chips ? `<div class="chip-list">${chips}</div>` : ''}
        <p class="muted" id="custom-item-error"></p>
        ${list ? `<ul class="custom-item-list">${list}</ul>` : ''}
      </div>
    `;
  }

  function renderCheckIn() {
    const checkedState = getCheckedState();
    const mealState = getMealState();
    const metricsState = getMetricsState();
    const customItems = getCustomItems();
    const rows = weekData.days.map((day) => {
      const dayChecked = checkedState[day.day] || {};
      const dayMeals = mealState[day.day] || {};
      const dayMetrics = metricsState[day.day] || {};
      const sectionsHtml = renderCheckInSections(day, dayChecked, dayMetrics, customItems);
      const mealLog = `
        <div class="meal-log">
          <label>아점
            <textarea data-meal-day="${day.day}" data-meal-slot="아점" placeholder="${day.meal.breakfast}">${escapeHtml(dayMeals['아점'] || '')}</textarea>
          </label>
          <label>저녁
            <textarea data-meal-day="${day.day}" data-meal-slot="저녁" placeholder="${day.meal.dinner}">${escapeHtml(dayMeals['저녁'] || '')}</textarea>
          </label>
        </div>
      `;
      const reflectionForm = day.reflectionPrompts ? `
        <div class="reflection-form">
          <label>${day.reflectionPrompts[0]}<textarea data-reflection="good"></textarea></label>
          <label>${day.reflectionPrompts[1]}<textarea data-reflection="blocker"></textarea></label>
          <label>${day.reflectionPrompts[2]}<textarea data-reflection="change"></textarea></label>
          <button class="primary-button" id="submit-reflection" data-day="${day.day}">회고 저장</button>
        </div>
      ` : '';
      return `<div class="today-card"><strong>${day.day} ${day.date.slice(5)}</strong>${sectionsHtml}${mealLog}${reflectionForm}</div>`;
    }).join('');
    return `<h2>매일 체크</h2>${rows}${renderCustomItemManager(customItems)}`;
  }

  function buildResponsesFromLocalState() {
    const state = getCheckedState();
    const customNames = getCustomItems().map((custom) => custom.name);
    const responses = [];
    weekData.days.forEach((day) => {
      [...day.tasks, ...customNames].forEach((task) => {
        responses.push({ item: task, checked: !!(state[day.day] && state[day.day][task]) });
      });
    });
    return responses;
  }

  function renderHistory() {
    const responses = buildResponsesFromLocalState();
    const customItems = getCustomItems();
    const sections = RoutineLogic.groupTasksBySection(weekData.days[0].tasks, customItems, itemsMeta);
    const sectionsHtml = sections.map((section) => {
      const rows = section.items.map((item) => {
        const ratio = RoutineLogic.completionRatio(responses, item.id);
        const label = item.isCustom ? escapeHtml(item.label) : item.label;
        return `<li>${label}: ${Math.round(ratio * 100)}%</li>`;
      }).join('');
      return `<div class="check-section"><h4>${section.title}</h4><ul>${rows}</ul></div>`;
    }).join('');
    const kmTotal = RoutineLogic.weeklyKmTotal(getMetricsState());
    const mealState = getMealState();
    const mealRows = weekData.days.map((day) => {
      const dayMeals = mealState[day.day] || {};
      const breakfast = dayMeals['아점'] ? escapeHtml(dayMeals['아점']) : '<span class="muted">(입력 없음)</span>';
      const dinner = dayMeals['저녁'] ? escapeHtml(dayMeals['저녁']) : '<span class="muted">(입력 없음)</span>';
      return `<tr><td>${day.day}</td><td>${breakfast}</td><td>${dinner}</td></tr>`;
    }).join('');
    const exerciseStatsCard = exerciseStats
      ? `<div class="today-card mint"><strong>지난 주 운동 현황</strong><p>${exerciseStats.weekId} · ${exerciseStats.exerciseDaysThisWeek}/7일 · 연속 ${exerciseStats.exerciseStreak}일째</p>${exerciseStats.kmLastWeek !== undefined ? `<p>지난 주 달린 거리: ${exerciseStats.kmLastWeek}km</p>` : ''}</div>`
      : '';
    const nutritionCard = nutritionStats ? `
      <div class="today-card butter">
        <strong>지난 주 식단 영양 (${nutritionStats.weekId})</strong>
        <p>평균: ${Math.round(nutritionStats.weeklyAverage.kcal)}kcal · 탄 ${Math.round(nutritionStats.weeklyAverage.carb)}g · 지 ${Math.round(nutritionStats.weeklyAverage.fat)}g · 단 ${Math.round(nutritionStats.weeklyAverage.protein)}g</p>
        ${nutritionStats.recommendations.length ? `<ul>${nutritionStats.recommendations.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>` : ''}
        ${nutritionStats.unmatchedFoodItems.length ? `<p class="muted">매칭 안 된 항목: ${nutritionStats.unmatchedFoodItems.map(escapeHtml).join(', ')}</p>` : ''}
        <p class="muted">${escapeHtml(nutritionStats.disclaimer)}</p>
      </div>
    ` : '';
    return `
      <h2>리포트</h2>
      <div class="today-card blue">
        <strong>이번 주 완료율 (이 기기 기준)</strong>
        ${sectionsHtml}
        <p>이번 주 달린 거리: ${kmTotal}km</p>
      </div>
      ${exerciseStatsCard}
      ${nutritionCard}
      <div class="today-card peach">
        <strong>이번 주 식단 기록</strong>
        <table class="meal-table"><thead><tr><th>요일</th><th>아점</th><th>저녁</th></tr></thead><tbody>${mealRows}</tbody></table>
      </div>
      <p class="muted">체크한 결과는 자동으로 동기화됩니다. 이번 주 결과를 문서로 남기고 싶으면 아래 버튼을 눌러주세요.</p>
      <button id="export-pdf" class="primary-button">이번 주 PDF로 내보내기</button>
    `;
  }

  function renderSettings() {
    return `
      <h2>설정</h2>
      <p class="muted">동기화 서버 연결: ${CONFIG.supabaseUrl && CONFIG.writeToken ? '연결됨' : '아직 설정되지 않음 (링크에 토큰이 없습니다)'}</p>
      <button id="clear-queue" class="primary-button">보내지 못한 체크 기록 초기화</button>
    `;
  }

  const ROUTES = {
    '/': renderHome, '/week': renderWeek, '/exercise': renderExercise, '/meals': renderMeals,
    '/check-in': renderCheckIn, '/history': renderHistory, '/settings': renderSettings,
  };

  function reservedCustomNames(customItems) {
    const suggestions = (itemsMeta && itemsMeta.suggestions && itemsMeta.suggestions.exercise) || [];
    return new Set([...weekData.days[0].tasks, ...suggestions, ...customItems.map((custom) => custom.name)]);
  }

  function addCustomItemFlow(name, section) {
    const customItems = getCustomItems();
    const error = RoutineLogic.validateCustomItemName(name, reservedCustomNames(customItems));
    const errorEl = document.getElementById('custom-item-error');
    if (error) {
      if (errorEl) errorEl.textContent = error;
      return;
    }
    addCustomItem(name.trim(), section);
    render();
  }

  function attachInteractions(route) {
    if (route === '/check-in') {
      document.querySelectorAll('#view input[type="checkbox"]').forEach((checkbox) => {
        checkbox.addEventListener('change', handleCheckboxChange(checkbox.dataset.day, checkbox.dataset.item));
      });
      document.querySelectorAll('#view input.metric-input').forEach((input) => {
        input.addEventListener('blur', handleMetricInputBlur);
      });
      const addButton = document.getElementById('custom-item-add');
      if (addButton) {
        addButton.addEventListener('click', () => {
          const nameInput = document.getElementById('custom-item-name');
          const sectionSelect = document.getElementById('custom-item-section');
          addCustomItemFlow(nameInput.value, sectionSelect.value);
        });
      }
      document.querySelectorAll('#view [data-suggestion]').forEach((chip) => {
        chip.addEventListener('click', () => addCustomItemFlow(chip.dataset.suggestion, 'exercise'));
      });
      document.querySelectorAll('#view [data-remove-custom]').forEach((button) => {
        button.addEventListener('click', () => {
          removeCustomItem(button.dataset.removeCustom);
          render();
        });
      });
      const reflectionButton = document.getElementById('submit-reflection');
      if (reflectionButton) {
        reflectionButton.addEventListener('click', () => {
          const day = reflectionButton.dataset.day;
          const good = document.querySelector('[data-reflection="good"]').value;
          const blocker = document.querySelector('[data-reflection="blocker"]').value;
          const change = document.querySelector('[data-reflection="change"]').value;
          sendCheckin({
            weekId: weekData.weekId, day, item: '회고', checked: true,
            reflection: { good, blocker, change },
            timestamp: new Date().toISOString(),
          });
        });
      }
      document.querySelectorAll('#view textarea[data-meal-day]').forEach((textarea) => {
        textarea.addEventListener('blur', () => {
          const day = textarea.dataset.mealDay;
          const slot = textarea.dataset.mealSlot;
          const text = textarea.value;
          setMealNote(day, slot, text);
          if (text.trim() === '') return;
          sendCheckin({
            weekId: weekData.weekId, day, item: slot, checked: true, note: text,
            timestamp: new Date().toISOString(),
          });
        });
      });
    }
    if (route === '/history') {
      const exportButton = document.getElementById('export-pdf');
      if (exportButton) exportButton.addEventListener('click', () => window.print());
    }
    if (route === '/settings') {
      const clearButton = document.getElementById('clear-queue');
      if (clearButton) clearButton.addEventListener('click', () => localStorage.removeItem(QUEUE_KEY));
    }
  }

  function render() {
    const route = location.hash.replace('#', '') || '/';
    const renderFn = ROUTES[route] || renderHome;
    document.getElementById('view').innerHTML = renderFn();
    document.querySelectorAll('.bottom-nav a').forEach((link) => {
      const isActive = link.dataset.route === route;
      link.classList.toggle('active', isActive);
      link.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
    attachInteractions(route);
  }

  window.addEventListener('hashchange', render);
  window.addEventListener('online', flushQueue);

  loadData().then(() => {
    render();
    flushQueue();
  });
})();
