(function () {
  const CONFIG = {
    appsScriptUrl: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.appsScriptUrl,
    sharedSecret: window.ROUTINE_CONFIG && window.ROUTINE_CONFIG.sharedSecret,
  };
  const QUEUE_KEY = 'routine-jammy:pending-checkins';
  const STICKER_BY_EXERCISE_TYPE = {
    slowJog: 'jogging', recoveryJog: 'jogging',
    strengthA: 'squat', strengthB: 'deadlift', strengthC: 'lunge',
    recoveryReflect: 'recovery',
  };

  let staticData = null;
  let weekData = null;

  async function loadData() {
    const [staticResponse, weekResponse] = await Promise.all([
      fetch('data/routine-static.json'),
      fetch('data/current-week.json'),
    ]);
    staticData = await staticResponse.json();
    weekData = await weekResponse.json();
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

  function queueCheckin(payload) {
    const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    queue.push(payload);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  }

  async function postCheckin(payload) {
    const response = await fetch(CONFIG.appsScriptUrl, {
      method: 'POST',
      body: JSON.stringify({ ...payload, secret: CONFIG.sharedSecret }),
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
  }

  async function sendCheckin(payload) {
    if (!CONFIG.appsScriptUrl) {
      queueCheckin(payload);
      return;
    }
    try {
      await postCheckin(payload);
    } catch (error) {
      queueCheckin(payload);
    }
  }

  async function flushQueue() {
    if (!CONFIG.appsScriptUrl) return;
    while (true) {
      const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
      if (queue.length === 0) return;
      const [next, ...rest] = queue;
      try {
        await postCheckin(next);
        localStorage.setItem(QUEUE_KEY, JSON.stringify(rest));
      } catch (error) {
        return;
      }
    }
  }

  function handleCheckboxChange(day, item) {
    return (event) => {
      const checked = event.target.checked;
      setChecked(day, item, checked);
      sendCheckin({ weekId: weekData.weekId, day, item, checked, timestamp: new Date().toISOString() });
    };
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

  function renderCheckIn() {
    const checkedState = getCheckedState();
    const rows = weekData.days.map((day) => {
      const dayChecked = checkedState[day.day] || {};
      const checkboxes = day.tasks.map((task) => `
        <label class="check-item">
          <input type="checkbox" data-day="${day.day}" data-item="${task}" ${dayChecked[task] ? 'checked' : ''}>
          ${task}
        </label>
      `).join('');
      return `<div class="today-card"><strong>${day.day} ${day.date.slice(5)}</strong><div class="check-grid">${checkboxes}</div></div>`;
    }).join('');
    return `<h2>매일 체크</h2>${rows}`;
  }

  function renderHistory() {
    return `
      <h2>리포트</h2>
      <p class="muted">체크한 결과는 자동으로 동기화됩니다. 이번 주 결과를 문서로 남기고 싶으면 아래 버튼을 눌러주세요.</p>
      <button id="export-pdf" class="primary-button">이번 주 PDF로 내보내기</button>
    `;
  }

  function renderSettings() {
    return `
      <h2>설정</h2>
      <p class="muted">동기화 서버 연결: ${CONFIG.appsScriptUrl ? '연결됨' : '아직 설정되지 않음'}</p>
      <button id="clear-queue" class="primary-button">보내지 못한 체크 기록 초기화</button>
    `;
  }

  const ROUTES = {
    '/': renderHome, '/week': renderWeek, '/exercise': renderExercise, '/meals': renderMeals,
    '/check-in': renderCheckIn, '/history': renderHistory, '/settings': renderSettings,
  };

  function attachInteractions(route) {
    if (route === '/check-in') {
      document.querySelectorAll('#view input[type="checkbox"]').forEach((checkbox) => {
        checkbox.addEventListener('change', handleCheckboxChange(checkbox.dataset.day, checkbox.dataset.item));
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
