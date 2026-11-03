(() => {
  'use strict';

  const root = document.documentElement;
  const LINK_LABELS = { github: 'GitHub', demo: 'Demo', appstore: 'App Store' };
  const THUMB_LABELS = { python: 'Py', web: '</>', ios: 'iOS' };

  let projects = [];

  const escapeHtml = (str) =>
    String(str).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ===== Theme =====
  function initTheme() {
    const btn = document.querySelector('.theme-toggle');
    btn.addEventListener('click', () => {
      const isDark = root.dataset.theme
        ? root.dataset.theme === 'dark'
        : window.matchMedia('(prefers-color-scheme: dark)').matches;
      const next = isDark ? 'light' : 'dark';
      root.dataset.theme = next;
      try { localStorage.setItem('theme', next); } catch (e) {}
    });
  }

  // ===== Mobile nav =====
  function initNav() {
    const toggle = document.querySelector('.nav-toggle');
    const menu = document.getElementById('nav-menu');
    const setOpen = (open) => {
      menu.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
    };
    toggle.addEventListener('click', () => setOpen(!menu.classList.contains('open')));
    menu.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => setOpen(false)));

    // 현재 보고 있는 섹션을 메뉴에 표시
    const links = [...menu.querySelectorAll('a[href^="#"]')];
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((l) => l.classList.toggle('active', l.getAttribute('href') === `#${entry.target.id}`));
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    links.forEach((l) => {
      const section = document.querySelector(l.getAttribute('href'));
      if (section) observer.observe(section);
    });
  }

  // ===== Projects =====
  function renderProjects(filter = 'all') {
    const grid = document.getElementById('projects-grid');
    const list = filter === 'all' ? projects : projects.filter((p) => p.category === filter);
    grid.innerHTML = list.map((p) => `
      <article class="project-card">
        <div class="project-thumb ${p.category}" aria-hidden="true">${escapeHtml(THUMB_LABELS[p.category] || '')}</div>
        <div class="project-body">
          <h3>${escapeHtml(p.title)}</h3>
          <p>${escapeHtml(p.summary)}</p>
          <ul class="tags">${p.tags.map((t) => `<li>${escapeHtml(t)}</li>`).join('')}</ul>
          <div class="project-actions">
            <div class="project-links">${renderLinks(p.links)}</div>
            <button class="btn btn-small" type="button" data-project="${escapeHtml(p.id)}">자세히</button>
          </div>
        </div>
      </article>`).join('');
  }

  function renderLinks(links = {}) {
    return Object.entries(links)
      .map(([key, url]) => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${LINK_LABELS[key] || key}</a>`)
      .join('');
  }

  function initFilters() {
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        buttons.forEach((b) => {
          b.classList.toggle('active', b === btn);
          b.setAttribute('aria-pressed', String(b === btn));
        });
        renderProjects(btn.dataset.filter);
      });
    });
  }

  // ===== Modal =====
  function initModal() {
    const modal = document.getElementById('project-modal');
    const body = document.getElementById('modal-body');

    document.getElementById('projects-grid').addEventListener('click', (e) => {
      const btn = e.target.closest('[data-project]');
      if (!btn) return;
      const p = projects.find((x) => x.id === btn.dataset.project);
      if (!p) return;
      body.innerHTML = `
        <h3 id="modal-title">${escapeHtml(p.title)}</h3>
        <ul class="tags">${p.tags.map((t) => `<li>${escapeHtml(t)}</li>`).join('')}</ul>
        <h4>문제</h4><p>${escapeHtml(p.problem)}</p>
        <h4>역할</h4><p>${escapeHtml(p.role)}</p>
        <h4>해결 방법</h4><p>${escapeHtml(p.solution)}</p>
        <h4>결과</h4><p>${escapeHtml(p.result)}</p>
        <div class="project-links" style="margin-top:24px">${renderLinks(p.links)}</div>`;
      modal.showModal();
    });

    modal.querySelector('.modal-close').addEventListener('click', () => modal.close());
    // 바깥(backdrop) 클릭 시 닫기
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.close(); });
  }

  // ===== Experience =====
  function renderExperience(items) {
    document.getElementById('timeline').innerHTML = items.map((it) => `
      <li class="timeline-item">
        <span class="timeline-period">${escapeHtml(it.period)}</span>
        <h3>${escapeHtml(it.org)}</h3>
        <p class="timeline-role">${escapeHtml(it.role)}</p>
        <ul>${it.highlights.map((h) => `<li>${escapeHtml(h)}</li>`).join('')}</ul>
      </li>`).join('');
  }

  // ===== Copy email =====
  function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toast.classList.remove('show'), 1800);
  }

  function initCopy() {
    document.querySelectorAll('[data-copy]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(btn.dataset.copy);
          showToast('이메일 주소를 복사했습니다');
        } catch (e) {
          showToast('복사에 실패했습니다. 직접 선택해 주세요');
        }
      });
    });
  }

  // ===== Reveal on scroll =====
  function initReveal() {
    const targets = document.querySelectorAll('.section .container');
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    targets.forEach((t) => { t.classList.add('reveal'); observer.observe(t); });
  }

  // ===== Data loading =====
  async function loadJson(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`${path}: ${res.status}`);
    return res.json();
  }

  async function loadData() {
    try {
      const [projectData, experienceData] = await Promise.all([
        loadJson('data/projects.json'),
        loadJson('data/experience.json'),
      ]);
      projects = projectData;
      renderProjects();
      renderExperience(experienceData);
    } catch (err) {
      console.error(err);
      const msg = '<p class="load-error">데이터를 불러오지 못했습니다. 로컬에서는 <code>python -m http.server</code>로 실행해 주세요.</p>';
      document.getElementById('projects-grid').innerHTML = msg;
      document.getElementById('timeline').innerHTML = msg;
    }
  }

  document.getElementById('year').textContent = new Date().getFullYear();
  initTheme();
  initNav();
  initFilters();
  initModal();
  initCopy();
  initReveal();
  loadData();
})();
