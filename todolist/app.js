'use strict';

(() => {
  const KEYS = {
    todos: 'todolist:v1:todos',
    lastDate: 'todolist:v1:lastDate',
    settings: 'todolist:v1:settings',
  };
  const MAX_LENGTH = 100;
  const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 };
  const PRIORITY_LABEL = { high: '높음', medium: '보통', low: '낮음' };
  const NEXT_PRIORITY = { high: 'medium', medium: 'low', low: 'high' };
  const ESTIMATE_OPTIONS = [10, 15, 30, 45, 60, 90, 120, 180, 240];
  const FILTERS = ['all', 'active', 'done'];
  const SORTS = ['priority', 'manual'];
  const THEMES = ['system', 'light', 'dark'];
  const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];
  const DATE_KEY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

  // ---- date ----

  function toDateKey(date = new Date()) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function parseDateKey(key) {
    const [y, m, d] = key.split('-').map(Number);
    return new Date(y, m - 1, d);
  }

  function addDays(key, days) {
    const date = parseDateKey(key);
    date.setDate(date.getDate() + days);
    return toDateKey(date);
  }

  function formatDateKey(key) {
    const date = parseDateKey(key);
    return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 (${WEEKDAYS[date.getDay()]})`;
  }

  function formatShortDate(key) {
    const date = parseDateKey(key);
    return `${date.getMonth() + 1}월 ${date.getDate()}일(${WEEKDAYS[date.getDay()]})`;
  }

  function formatMinutes(minutes) {
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    if (!hours) return `${rest}분`;
    return rest ? `${hours}시간 ${rest}분` : `${hours}시간`;
  }

  // ---- storage ----

  // read()는 저장소를 쓸 수 없으면 undefined, 값이 없으면 null을 돌려준다.
  const storage = {
    read(key) {
      try {
        return localStorage.getItem(key);
      } catch {
        return undefined;
      }
    },
    write(key, value) {
      try {
        localStorage.setItem(key, value);
        return true;
      } catch {
        return false;
      }
    },
  };

  function isValidTodo(t) {
    return Boolean(t)
      && typeof t.id === 'string'
      && typeof t.text === 'string'
      && t.text.trim() !== ''
      && typeof t.completed === 'boolean'
      && Object.hasOwn(PRIORITY_ORDER, t.priority)
      && DATE_KEY_PATTERN.test(t.date)
      && typeof t.createdAt === 'number';
  }

  // 알려진 필드만 남겨 저장 데이터와 백업 파일을 같은 형태로 맞춘다.
  function normalizeTodo(t) {
    const todo = {
      id: t.id,
      text: t.text.trim().slice(0, MAX_LENGTH),
      completed: t.completed,
      priority: t.priority,
      date: t.date,
      createdAt: t.createdAt,
    };
    if (t.completed && typeof t.completedAt === 'number') todo.completedAt = t.completedAt;
    if (typeof t.carriedFrom === 'string') todo.carriedFrom = t.carriedFrom;
    if (ESTIMATE_OPTIONS.includes(t.estimate)) todo.estimate = t.estimate;
    if (Number.isFinite(t.order)) todo.order = t.order;
    return todo;
  }

  function loadTodos() {
    const raw = storage.read(KEYS.todos);
    if (raw === undefined) {
      return {
        todos: [],
        blocked: 'unavailable',
        notice: '이 브라우저에서는 저장소를 쓸 수 없어 새로고침하면 목록이 사라집니다.',
      };
    }
    if (raw === null) return { todos: [], blocked: null };
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) throw new TypeError('todos is not an array');
      return { todos: parsed.filter(isValidTodo).map(normalizeTodo), blocked: null };
    } catch {
      // 손상된 원본을 덮어쓰지 않도록 이번 세션은 저장하지 않는다.
      return {
        todos: [],
        blocked: 'corrupt',
        notice: '저장된 데이터를 읽지 못했습니다. 기존 데이터를 보호하기 위해 지금 목록은 저장되지 않습니다. 백업 파일이 있다면 가져와서 복구할 수 있습니다.',
      };
    }
  }

  function loadSettings() {
    const defaults = { theme: 'system', filter: 'all', sort: 'priority' };
    const raw = storage.read(KEYS.settings);
    if (!raw) return defaults;
    try {
      const parsed = JSON.parse(raw);
      return {
        theme: THEMES.includes(parsed?.theme) ? parsed.theme : defaults.theme,
        filter: FILTERS.includes(parsed?.filter) ? parsed.filter : defaults.filter,
        sort: SORTS.includes(parsed?.sort) ? parsed.sort : defaults.sort,
      };
    } catch {
      return defaults;
    }
  }

  // ---- state ----

  const loaded = loadTodos();
  let todos = loaded.todos;
  let blockReason = loaded.blocked;
  let settings = loadSettings();
  let today = toDateKey();
  let viewDate = today;
  let editingId = null;
  let statsRange = 7;
  let drag = null;

  function canPersist() {
    return blockReason === null;
  }

  function isViewingToday() {
    return viewDate === today;
  }

  function save() {
    if (!canPersist()) return;
    if (!storage.write(KEYS.todos, JSON.stringify(todos))) {
      showNotice('저장 공간이 부족하거나 저장소를 쓸 수 없어 마지막 변경이 저장되지 않았습니다. 백업을 내보내 두세요.');
    }
  }

  function saveSettings() {
    storage.write(KEYS.settings, JSON.stringify(settings));
  }

  function commit() {
    save();
    render();
  }

  function createId() {
    if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }

  function findTodo(id) {
    return todos.find((t) => t.id === id);
  }

  function nextOrder(dateKey) {
    return todos
      .filter((t) => t.date === dateKey && Number.isFinite(t.order))
      .reduce((max, t) => Math.max(max, t.order), -1) + 1;
  }

  function addTodo(text, priority, estimate) {
    const trimmed = text.trim().slice(0, MAX_LENGTH);
    if (!trimmed) return false;
    const todo = {
      id: createId(),
      text: trimmed,
      completed: false,
      priority: Object.hasOwn(PRIORITY_ORDER, priority) ? priority : 'medium',
      date: today,
      createdAt: Date.now(),
      order: nextOrder(today),
    };
    if (ESTIMATE_OPTIONS.includes(estimate)) todo.estimate = estimate;
    todos.push(todo);
    commit();
    return true;
  }

  function toggleTodo(id) {
    const todo = findTodo(id);
    if (!todo) return;
    todo.completed = !todo.completed;
    if (todo.completed) todo.completedAt = Date.now();
    else delete todo.completedAt;
    commit();
  }

  function cyclePriority(id) {
    const todo = findTodo(id);
    if (!todo) return;
    todo.priority = NEXT_PRIORITY[todo.priority];
    commit();
  }

  function editTodo(id, text, estimate) {
    const todo = findTodo(id);
    if (!todo) return;
    const trimmed = text.trim().slice(0, MAX_LENGTH);
    let changed = false;
    if (trimmed && trimmed !== todo.text) {
      todo.text = trimmed;
      changed = true;
    }
    if ((todo.estimate ?? 0) !== estimate) {
      if (ESTIMATE_OPTIONS.includes(estimate)) todo.estimate = estimate;
      else delete todo.estimate;
      changed = true;
    }
    if (changed) commit();
    else render();
  }

  function removeTodo(id) {
    todos = todos.filter((t) => t.id !== id);
    if (editingId === id) editingId = null;
    commit();
  }

  // 오늘의 완료 항목만 지운다. 지난 날짜 기록은 그대로 둔다.
  function clearCompleted() {
    const count = todos.filter((t) => t.date === today && t.completed).length;
    if (count === 0 || !window.confirm(`오늘 완료한 할 일 ${count}개를 지울까요?`)) return;
    todos = todos.filter((t) => !(t.date === today && t.completed));
    commit();
  }

  // 원본은 지난 날짜에 미완료로 남기고, 오늘 날짜로 사본을 만든다.
  function carryOver(ids) {
    const now = Date.now();
    const baseOrder = nextOrder(today);
    ids.map(findTodo).filter(Boolean).forEach((source, index) => {
      const copy = {
        id: createId(),
        text: source.text,
        completed: false,
        priority: source.priority,
        date: today,
        createdAt: now + index,
        order: baseOrder + index,
        carriedFrom: source.id,
      };
      if (source.estimate) copy.estimate = source.estimate;
      todos.push(copy);
    });
    commit();
  }

  // ids 순서대로 직접 정렬 순서를 매긴다.
  function reorder(ids) {
    ids.forEach((id, index) => {
      const todo = findTodo(id);
      if (todo) todo.order = index;
    });
    commit();
  }

  // 직접 정렬로 바꿀 때는 지금 보이던 우선순위 순서에서 시작한다.
  function adoptPriorityOrder(dateKey) {
    todos
      .filter((t) => t.date === dateKey)
      .sort(comparePriority)
      .forEach((todo, index) => {
        todo.order = index;
      });
  }

  function comparePriority(a, b) {
    return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority] || a.createdAt - b.createdAt;
  }

  // 완료 항목은 항상 아래. 그 안에서는 우선순위순 또는 직접 정한 순서.
  function compareTodos(a, b) {
    const byCompletion = Number(a.completed) - Number(b.completed);
    if (byCompletion) return byCompletion;
    if (settings.sort === 'manual') {
      const byOrder = (a.order ?? Infinity) - (b.order ?? Infinity);
      return byOrder || a.createdAt - b.createdAt;
    }
    return comparePriority(a, b);
  }

  function todosOn(dateKey) {
    return todos.filter((t) => t.date === dateKey).sort(compareTodos);
  }

  function matchesFilter(todo, filter) {
    if (filter === 'active') return !todo.completed;
    if (filter === 'done') return todo.completed;
    return true;
  }

  // ---- render ----

  const el = {
    statsOpen: document.getElementById('stats-open'),
    themeToggle: document.getElementById('theme-toggle'),
    prevDay: document.getElementById('prev-day'),
    nextDay: document.getElementById('next-day'),
    goToday: document.getElementById('go-today'),
    dateLabel: document.getElementById('date-label'),
    dateInput: document.getElementById('date-input'),
    notice: document.getElementById('notice'),
    readonlyNotice: document.getElementById('readonly-notice'),
    form: document.getElementById('add-form'),
    text: document.getElementById('new-text'),
    priority: document.getElementById('new-priority'),
    estimate: document.getElementById('new-estimate'),
    progress: document.getElementById('progress'),
    progressText: document.getElementById('progress-text'),
    progressBar: document.getElementById('progress-bar'),
    progressFill: document.getElementById('progress-fill'),
    estimateSummary: document.getElementById('estimate-summary'),
    toolbar: document.getElementById('list-toolbar'),
    filters: document.getElementById('filters'),
    sortSelect: document.getElementById('sort-select'),
    list: document.getElementById('todo-list'),
    empty: document.getElementById('empty-state'),
    footer: document.getElementById('list-footer'),
    clearCompleted: document.getElementById('clear-completed'),
    exportBackup: document.getElementById('export-backup'),
    importBackup: document.getElementById('import-backup'),
    importInput: document.getElementById('import-input'),
    carryDialog: document.getElementById('carry-dialog'),
    carryTitle: document.getElementById('carry-title'),
    carryList: document.getElementById('carry-list'),
    statsDialog: document.getElementById('stats-dialog'),
    statsClose: document.getElementById('stats-close'),
    statsRange: document.getElementById('stats-range'),
    statTiles: document.getElementById('stat-tiles'),
    chartPlot: document.getElementById('chart-plot'),
    chartBars: document.getElementById('chart-bars'),
    chartTip: document.getElementById('chart-tip'),
    chartX: document.getElementById('chart-x'),
    statsTableBody: document.getElementById('stats-table-body'),
  };

  function showNotice(message, tone = 'warn') {
    el.notice.textContent = message;
    el.notice.classList.toggle('is-info', tone === 'info');
    el.notice.hidden = false;
  }

  function fillEstimateOptions(select, noneLabel, value = 0) {
    select.replaceChildren(
      new Option(noneLabel, '0'),
      ...ESTIMATE_OPTIONS.map((minutes) => new Option(formatMinutes(minutes), String(minutes))),
    );
    select.value = String(value);
  }

  function makeButton(className, role, label) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.dataset.role = role;
    button.setAttribute('aria-label', label);
    return button;
  }

  function makeChip(priority) {
    const chip = document.createElement('span');
    chip.className = `chip chip-${priority}`;
    chip.textContent = PRIORITY_LABEL[priority];
    return chip;
  }

  function renderEditor(todo) {
    const editor = document.createElement('div');
    editor.className = 'todo-editor';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'todo-edit';
    input.maxLength = MAX_LENGTH;
    input.value = todo.text;
    input.dataset.role = 'edit-input';
    input.setAttribute('aria-label', '할 일 수정');

    const estimate = document.createElement('select');
    estimate.className = 'todo-edit-estimate';
    estimate.dataset.role = 'edit-estimate';
    estimate.setAttribute('aria-label', '예상 시간');
    fillEstimateOptions(estimate, '시간 없음', todo.estimate ?? 0);

    editor.append(input, estimate);
    return editor;
  }

  function renderBody(todo, readOnly) {
    const body = document.createElement('div');
    body.className = 'todo-body';
    const text = document.createElement('span');
    text.className = 'todo-text';
    text.textContent = todo.text;
    text.dataset.role = 'text';
    if (!readOnly) text.title = '더블클릭해서 수정';
    body.append(text);
    if (todo.estimate) {
      const meta = document.createElement('span');
      meta.className = 'todo-meta';
      meta.textContent = `⏱ ${formatMinutes(todo.estimate)}`;
      body.append(meta);
    }
    return body;
  }

  function renderItem(todo, { readOnly, draggable }) {
    const li = document.createElement('li');
    li.className = 'todo';
    li.classList.toggle('is-done', todo.completed);
    li.classList.toggle('is-readonly', readOnly);
    li.classList.toggle('is-draggable', draggable);
    li.dataset.id = todo.id;

    if (draggable) {
      const handle = makeButton('drag-handle', 'drag', `${todo.text} 순서 이동, 위아래 화살표 키로 이동`);
      handle.textContent = '⠿';
      handle.title = '끌어서 순서 변경';
      li.append(handle);
    }

    const checkLabel = document.createElement('label');
    checkLabel.className = 'todo-check';
    const check = document.createElement('input');
    check.type = 'checkbox';
    check.checked = todo.completed;
    check.disabled = readOnly;
    check.dataset.role = 'toggle';
    check.setAttribute('aria-label', `${todo.text} 완료`);
    checkLabel.append(check);

    let priority;
    if (readOnly) {
      priority = document.createElement('span');
      priority.className = 'todo-priority is-static';
    } else {
      const label = PRIORITY_LABEL[todo.priority];
      priority = makeButton('todo-priority', 'priority', `우선순위 ${label}, 눌러서 변경`);
      priority.title = '우선순위 변경';
    }
    priority.append(makeChip(todo.priority));

    const body = todo.id === editingId ? renderEditor(todo) : renderBody(todo, readOnly);

    li.append(checkLabel, priority, body);
    if (!readOnly) {
      const edit = makeButton('icon-btn', 'edit', `${todo.text} 수정`);
      edit.textContent = '✎';
      const remove = makeButton('icon-btn icon-btn-danger', 'delete', `${todo.text} 삭제`);
      remove.textContent = '×';
      li.append(edit, remove);
    }
    return li;
  }

  // 목록을 다시 그려도 키보드 포커스가 같은 항목·같은 컨트롤에 남도록 한다.
  function captureFocus() {
    const active = document.activeElement;
    const item = active instanceof Element ? active.closest('.todo') : null;
    if (!item || !el.list.contains(item)) return null;
    return { id: item.dataset.id, role: active.dataset.role };
  }

  function restoreFocus(focus) {
    if (editingId) {
      const input = el.list.querySelector('.todo-edit');
      if (input && !input.closest('.todo-editor').contains(document.activeElement)) {
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      }
      return;
    }
    if (!focus) return;
    const item = [...el.list.children].find((li) => li.dataset.id === focus.id);
    if (!item) {
      if (isViewingToday()) el.text.focus();
      return;
    }
    const role = focus.role?.startsWith('edit-') ? 'edit' : focus.role;
    item.querySelector(`[data-role="${role}"]`)?.focus();
  }

  function emptyMessage(filter, readOnly) {
    if (filter === 'active') return '진행 중인 할 일이 없어요';
    if (filter === 'done') return '완료한 할 일이 없어요';
    return readOnly ? '이 날은 기록이 없어요' : '오늘 할 일을 추가해보세요';
  }

  function render() {
    const focus = captureFocus();
    const readOnly = !isViewingToday();
    const items = todosOn(viewDate);
    const done = items.filter((t) => t.completed).length;
    const percent = items.length ? Math.round((done / items.length) * 100) : 0;
    const filter = items.length ? settings.filter : 'all';
    const visible = items.filter((t) => matchesFilter(t, filter));
    const canDrag = !readOnly && settings.sort === 'manual' && filter !== 'done';

    el.dateLabel.textContent = formatDateKey(viewDate);
    el.dateInput.value = viewDate;
    el.dateInput.max = today;
    el.nextDay.disabled = !readOnly;
    el.goToday.hidden = !readOnly;
    el.readonlyNotice.hidden = !readOnly;
    el.form.hidden = readOnly;

    el.progress.hidden = items.length === 0;
    el.progressText.textContent = `${done} / ${items.length} 완료 (${percent}%)`;
    el.progressFill.style.width = `${percent}%`;
    el.progressBar.setAttribute('aria-valuenow', String(percent));

    const estimated = items.filter((t) => t.estimate);
    el.estimateSummary.hidden = estimated.length === 0;
    if (estimated.length) {
      const total = estimated.reduce((sum, t) => sum + t.estimate, 0);
      const remaining = estimated.filter((t) => !t.completed).reduce((sum, t) => sum + t.estimate, 0);
      el.estimateSummary.textContent = `예상 시간 총 ${formatMinutes(total)} · 남은 ${formatMinutes(remaining)}`;
    }

    const counts = { all: items.length, active: items.length - done, done };
    el.toolbar.hidden = items.length === 0;
    for (const button of el.filters.querySelectorAll('[data-filter]')) {
      button.setAttribute('aria-pressed', String(button.dataset.filter === settings.filter));
      button.querySelector('.count').textContent = counts[button.dataset.filter];
    }
    el.sortSelect.value = settings.sort;

    el.list.replaceChildren(...visible.map((t) => renderItem(t, {
      readOnly,
      draggable: canDrag && !t.completed,
    })));
    el.empty.hidden = visible.length > 0;
    el.empty.textContent = emptyMessage(filter, readOnly);

    el.footer.hidden = readOnly || done === 0;
    el.clearCompleted.textContent = `완료 항목 지우기 (${done})`;

    restoreFocus(focus);
  }

  // ---- theme ----

  const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

  function effectiveTheme() {
    if (settings.theme !== 'system') return settings.theme;
    return darkQuery.matches ? 'dark' : 'light';
  }

  function applyTheme() {
    if (settings.theme === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = settings.theme;
    const isDark = effectiveTheme() === 'dark';
    el.themeToggle.textContent = isDark ? '☀️' : '🌙';
    el.themeToggle.setAttribute('aria-label', isDark ? '라이트 모드로 전환' : '다크 모드로 전환');
  }

  // ---- carry over ----

  function markVisited() {
    if (canPersist()) storage.write(KEYS.lastDate, today);
  }

  // 직전 접속일의 미완료 항목이 있으면 매번 가져올지 묻는다.
  function checkCarryOver() {
    if (el.carryDialog.open) return;
    const lastDate = canPersist() ? storage.read(KEYS.lastDate) : null;
    if (!lastDate || !DATE_KEY_PATTERN.test(lastDate) || lastDate >= today) {
      markVisited();
      return;
    }
    const alreadyCarried = new Set(todos
      .filter((t) => t.date === today && t.carriedFrom)
      .map((t) => t.carriedFrom));
    const candidates = todos
      .filter((t) => t.date === lastDate && !t.completed && !alreadyCarried.has(t.id))
      .sort(comparePriority);
    if (candidates.length === 0) {
      markVisited();
      return;
    }
    openCarryDialog(lastDate, candidates);
  }

  function openCarryDialog(fromDate, candidates) {
    const when = fromDate === addDays(today, -1) ? '어제' : `${formatShortDate(fromDate)}에`;
    el.carryTitle.textContent = `${when} 못 끝낸 일이 ${candidates.length}개 있어요.`;
    el.carryList.replaceChildren(...candidates.map((todo) => {
      const li = document.createElement('li');
      const label = document.createElement('label');
      label.className = 'carry-item';
      const check = document.createElement('input');
      check.type = 'checkbox';
      check.checked = true;
      check.value = todo.id;
      const text = document.createElement('span');
      text.className = 'carry-text';
      text.textContent = todo.text;
      label.append(check, makeChip(todo.priority), text);
      li.append(label);
      return li;
    }));
    el.carryDialog.returnValue = '';
    el.carryDialog.showModal();
  }

  // 가져오기·건너뛰기·Esc 어느 쪽이든 오늘은 다시 묻지 않는다.
  el.carryDialog.addEventListener('close', () => {
    if (el.carryDialog.returnValue === 'carry') {
      const ids = [...el.carryList.querySelectorAll('input:checked')].map((input) => input.value);
      if (ids.length) carryOver(ids);
    }
    markVisited();
    render();
  });

  // ---- backup ----

  function exportBackup() {
    const data = {
      app: 'todolist',
      version: 1,
      exportedAt: new Date().toISOString(),
      todos,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `todolist-backup-${today}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  // 백업은 기존 기록과 합친다. 같은 id는 백업 내용으로 바뀐다.
  async function importBackup(file) {
    let parsed;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      window.alert('백업 파일을 읽지 못했습니다. JSON 파일인지 확인해주세요.');
      return;
    }
    const list = Array.isArray(parsed) ? parsed : parsed?.todos;
    if (!Array.isArray(list)) {
      window.alert('파일에서 할 일 목록을 찾지 못했습니다.');
      return;
    }
    const valid = list.filter(isValidTodo).map(normalizeTodo);
    if (valid.length === 0) {
      window.alert('불러올 수 있는 할 일이 없습니다.');
      return;
    }
    const skipped = list.length - valid.length;
    const skippedNote = skipped ? ` (형식이 맞지 않는 ${skipped}개는 제외)` : '';
    const message = `백업에서 할 일 ${valid.length}개를 불러옵니다.${skippedNote}\n`
      + '같은 항목은 백업 내용으로 바뀌고, 나머지 기록은 그대로 남습니다. 계속할까요?';
    if (!window.confirm(message)) return;

    const byId = new Map(todos.map((t) => [t.id, t]));
    for (const todo of valid) byId.set(todo.id, todo);
    todos = [...byId.values()];
    editingId = null;
    // 손상된 데이터 때문에 저장을 멈췄다면, 백업으로 복구하면서 다시 저장한다.
    if (blockReason === 'corrupt') blockReason = null;
    commit();
    showNotice(`백업에서 할 일 ${valid.length}개를 불러왔습니다.`, 'info');
  }

  // ---- stats ----

  function computeStats(days) {
    const rows = Array.from({ length: days }, (_, i) => ({
      date: addDays(today, i - days + 1),
      total: 0,
      done: 0,
      doneMinutes: 0,
    }));
    const byDate = new Map(rows.map((row) => [row.date, row]));
    for (const todo of todos) {
      const row = byDate.get(todo.date);
      if (!row) continue;
      row.total += 1;
      if (todo.completed) {
        row.done += 1;
        row.doneMinutes += todo.estimate ?? 0;
      }
    }
    const sum = (key) => rows.reduce((acc, row) => acc + row[key], 0);
    return {
      rows,
      total: sum('total'),
      done: sum('done'),
      doneMinutes: sum('doneMinutes'),
      activeDays: rows.filter((row) => row.total > 0).length,
    };
  }

  function percentOf(done, total) {
    return total ? Math.round((done / total) * 100) : null;
  }

  function makeTile(label, value, sub) {
    const tile = document.createElement('div');
    tile.className = 'stat-tile';
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value;
    const small = document.createElement('span');
    small.className = 'stat-sub';
    small.textContent = sub;
    dd.append(small);
    tile.append(dt, dd);
    return tile;
  }

  function renderStats() {
    const stats = computeStats(statsRange);
    const rate = percentOf(stats.done, stats.total);

    for (const button of el.statsRange.querySelectorAll('[data-range]')) {
      button.setAttribute('aria-pressed', String(Number(button.dataset.range) === statsRange));
    }

    el.statTiles.replaceChildren(
      makeTile('완료율', rate === null ? '–' : `${rate}%`, `${stats.done} / ${stats.total}개`),
      makeTile('완료한 일', `${stats.done}개`, `하루 평균 ${(stats.done / statsRange).toFixed(1)}개`),
      makeTile('기록한 날', `${stats.activeDays}일`, `${statsRange}일 중`),
      makeTile('완료한 예상 시간', stats.doneMinutes ? formatMinutes(stats.doneMinutes) : '–', '예상 시간을 입력한 항목 기준'),
    );

    el.chartTip.hidden = true;
    el.chartBars.replaceChildren(...stats.rows.map((row) => {
      const pct = percentOf(row.done, row.total);
      const tip = `${formatShortDate(row.date)} · ${pct === null ? '기록 없음' : `${row.done}/${row.total} 완료 (${pct}%)`}`;
      const col = document.createElement('button');
      col.type = 'button';
      col.className = 'bar-col';
      col.dataset.date = row.date;
      col.dataset.tip = tip;
      col.setAttribute('aria-label', `${tip}, 눌러서 이 날짜 보기`);
      if (pct !== null) {
        const bar = document.createElement('span');
        bar.className = pct === 0 ? 'bar is-zero' : 'bar';
        if (pct > 0) bar.style.height = `${pct}%`;
        col.append(bar);
      }
      return col;
    }));

    el.chartX.classList.toggle('is-dense', statsRange > 7);
    el.chartX.replaceChildren(...stats.rows.map((row, i) => {
      const span = document.createElement('span');
      const fromEnd = stats.rows.length - 1 - i;
      if (statsRange <= 7 || fromEnd % 7 === 0) {
        const date = parseDateKey(row.date);
        span.textContent = `${date.getMonth() + 1}/${date.getDate()}`;
      }
      return span;
    }));

    el.statsTableBody.replaceChildren(...stats.rows.map((row) => {
      const tr = document.createElement('tr');
      const pct = percentOf(row.done, row.total);
      for (const value of [formatShortDate(row.date), row.done, row.total, pct === null ? '–' : `${pct}%`]) {
        const td = document.createElement('td');
        td.textContent = value;
        tr.append(td);
      }
      return tr;
    }));
  }

  function showTip(col) {
    el.chartTip.textContent = col.dataset.tip;
    el.chartTip.hidden = false;
    const half = el.chartTip.offsetWidth / 2;
    const center = col.offsetLeft + col.offsetWidth / 2;
    const left = Math.min(Math.max(center, half), el.chartPlot.clientWidth - half);
    el.chartTip.style.left = `${left}px`;
  }

  function hideTip() {
    el.chartTip.hidden = true;
  }

  // ---- events ----

  function idOf(node) {
    return node.closest('.todo')?.dataset.id;
  }

  function startEdit(id) {
    if (!isViewingToday()) return;
    editingId = id;
    render();
  }

  function finishEdit(editor, shouldSave) {
    const id = idOf(editor);
    if (!id || editingId !== id) return;
    editingId = null;
    if (shouldSave) {
      const text = editor.querySelector('.todo-edit').value;
      const estimate = Number(editor.querySelector('.todo-edit-estimate').value);
      editTodo(id, text, estimate);
    } else {
      render();
    }
  }

  function showDate(dateKey) {
    if (!DATE_KEY_PATTERN.test(dateKey)) return;
    viewDate = dateKey > today ? today : dateKey;
    editingId = null;
    render();
  }

  function draggableItems() {
    return [...el.list.querySelectorAll('.todo.is-draggable')];
  }

  function moveItem(id, delta) {
    const ids = draggableItems().map((li) => li.dataset.id);
    const from = ids.indexOf(id);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= ids.length) return;
    ids.splice(to, 0, ...ids.splice(from, 1));
    reorder(ids);
  }

  function middleOf(node) {
    const rect = node.getBoundingClientRect();
    return rect.top + rect.height / 2;
  }

  el.themeToggle.addEventListener('click', () => {
    settings.theme = effectiveTheme() === 'dark' ? 'light' : 'dark';
    saveSettings();
    applyTheme();
  });
  darkQuery.addEventListener('change', applyTheme);

  el.prevDay.addEventListener('click', () => showDate(addDays(viewDate, -1)));
  el.nextDay.addEventListener('click', () => {
    showDate(addDays(viewDate, 1));
    if (el.nextDay.disabled) el.prevDay.focus();
  });
  el.goToday.addEventListener('click', () => {
    showDate(today);
    el.text.focus();
  });
  el.dateLabel.addEventListener('click', () => {
    try {
      el.dateInput.showPicker();
    } catch {
      el.dateInput.focus();
    }
  });
  el.dateInput.addEventListener('change', () => showDate(el.dateInput.value));

  el.form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (addTodo(el.text.value, el.priority.value, Number(el.estimate.value))) {
      el.text.value = '';
      el.estimate.value = '0';
    }
    el.text.focus();
  });

  el.filters.addEventListener('click', (event) => {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    settings.filter = button.dataset.filter;
    saveSettings();
    render();
  });

  el.sortSelect.addEventListener('change', () => {
    settings.sort = SORTS.includes(el.sortSelect.value) ? el.sortSelect.value : 'priority';
    saveSettings();
    if (settings.sort === 'manual') {
      adoptPriorityOrder(today);
      commit();
    } else {
      render();
    }
  });

  el.clearCompleted.addEventListener('click', () => {
    clearCompleted();
    if (el.footer.hidden) el.text.focus();
  });

  el.list.addEventListener('change', (event) => {
    if (event.target.dataset.role === 'toggle' && isViewingToday()) toggleTodo(idOf(event.target));
  });

  el.list.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-role]');
    if (!button || !isViewingToday()) return;
    const id = idOf(button);
    if (button.dataset.role === 'priority') cyclePriority(id);
    else if (button.dataset.role === 'edit') startEdit(id);
    else if (button.dataset.role === 'delete') removeTodo(id);
  });

  el.list.addEventListener('dblclick', (event) => {
    if (event.target.dataset.role === 'text') startEdit(idOf(event.target));
  });

  el.list.addEventListener('keydown', (event) => {
    const role = event.target.dataset.role;
    if (role === 'drag' && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
      event.preventDefault();
      moveItem(idOf(event.target), event.key === 'ArrowUp' ? -1 : 1);
      return;
    }
    const editor = event.target.closest('.todo-editor');
    if (!editor || event.isComposing) return;
    if (event.key === 'Enter') {
      event.preventDefault();
      finishEdit(editor, true);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      finishEdit(editor, false);
    }
  });

  // 편집기 안에서 입력창 ↔ 시간 선택으로 옮겨갈 때는 편집을 끝내지 않는다.
  el.list.addEventListener('focusout', (event) => {
    const editor = event.target.closest('.todo-editor');
    if (!editor || editor.contains(event.relatedTarget)) return;
    finishEdit(editor, true);
  });

  // 끌어서 순서 바꾸기. 끄는 항목 자체는 DOM에서 빼지 않고 이웃 항목을 옮겨
  // 포인터 캡처가 풀리지 않게 한다.
  el.list.addEventListener('pointerdown', (event) => {
    const handle = event.target.closest('[data-role="drag"]');
    if (!handle || event.button !== 0) return;
    event.preventDefault();
    const item = handle.closest('.todo');
    handle.setPointerCapture(event.pointerId);
    item.classList.add('is-dragging');
    drag = { item, pointerId: event.pointerId };
  });

  el.list.addEventListener('pointermove', (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    const { item } = drag;
    for (;;) {
      const prev = item.previousElementSibling;
      const next = item.nextElementSibling;
      if (prev?.classList.contains('is-draggable') && event.clientY < middleOf(prev)) {
        item.after(prev);
      } else if (next?.classList.contains('is-draggable') && event.clientY > middleOf(next)) {
        item.before(next);
      } else {
        break;
      }
    }
  });

  function endDrag(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.item.classList.remove('is-dragging');
    drag = null;
    reorder(draggableItems().map((li) => li.dataset.id));
  }

  el.list.addEventListener('pointerup', endDrag);
  el.list.addEventListener('pointercancel', endDrag);

  el.exportBackup.addEventListener('click', exportBackup);
  el.importBackup.addEventListener('click', () => el.importInput.click());
  el.importInput.addEventListener('change', async () => {
    const [file] = el.importInput.files;
    el.importInput.value = '';
    if (file) await importBackup(file);
  });

  el.statsOpen.addEventListener('click', () => {
    renderStats();
    el.statsDialog.showModal();
  });
  el.statsClose.addEventListener('click', () => el.statsDialog.close());
  el.statsRange.addEventListener('click', (event) => {
    const button = event.target.closest('[data-range]');
    if (!button) return;
    statsRange = Number(button.dataset.range);
    renderStats();
  });
  el.chartBars.addEventListener('pointerover', (event) => {
    const col = event.target.closest('.bar-col');
    if (col) showTip(col);
  });
  el.chartBars.addEventListener('pointerleave', hideTip);
  el.chartBars.addEventListener('focusin', (event) => {
    const col = event.target.closest('.bar-col');
    if (col) showTip(col);
  });
  el.chartBars.addEventListener('focusout', hideTip);
  el.chartBars.addEventListener('click', (event) => {
    const col = event.target.closest('.bar-col');
    if (!col) return;
    el.statsDialog.close();
    showDate(col.dataset.date);
  });

  // 자정을 넘겨 페이지를 열어둔 경우 날짜를 다시 확인한다.
  function syncDate() {
    const now = toDateKey();
    if (now === today) return;
    const wasViewingToday = isViewingToday();
    today = now;
    if (wasViewingToday) viewDate = today;
    editingId = null;
    render();
    checkCarryOver();
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) syncDate();
  });
  setInterval(syncDate, 60 * 1000);

  // 다른 탭에서 바뀐 내용을 반영한다.
  window.addEventListener('storage', (event) => {
    if (event.key === KEYS.todos && canPersist()) {
      const next = loadTodos();
      if (next.blocked) return;
      todos = next.todos;
      editingId = null;
      render();
    } else if (event.key === KEYS.lastDate && event.newValue === today && el.carryDialog.open) {
      // 다른 탭에서 이미 이월 여부를 정했다.
      el.carryDialog.close();
    } else if (event.key === KEYS.settings) {
      settings = loadSettings();
      applyTheme();
      render();
    }
  });

  // ---- init ----

  fillEstimateOptions(el.estimate, '예상 시간');
  if (loaded.notice) showNotice(loaded.notice);
  applyTheme();
  render();
  checkCarryOver();
})();
