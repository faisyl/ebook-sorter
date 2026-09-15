/* ============================================================================
   app.js — guided flow (direction B) shell + hash router + auth.
   Renders header, vertical stepper, screen container. Wires nav.
   ========================================================================== */
(function () {
  const STEPS = [
    { id: 'select',     label: 'Select',     desc: 'Pick folders' },
    { id: 'configure',  label: 'Configure',  desc: 'Options' },
    { id: 'preview',    label: 'Preview',    desc: 'Review matches' },
    { id: 'review',     label: 'Review',     desc: 'Fix & apply' },
  ];

  const app = document.getElementById('app');
  let currentStep = 0;
  let screenNodes = {};

  function renderShell() {
    app.innerHTML = `
      <header class="app-header">
        <div class="app-header__brand">
          <div class="app-header__logo" aria-hidden="true">E</div>
          <h1>Ebook Sorter</h1>
        </div>
        <div class="app-header__user">
          <span class="text-sm muted" data-username></span>
          <button class="btn btn--ghost btn--sm" data-logout>Sign out</button>
        </div>
      </header>
      <div class="app-shell">
        <nav aria-label="Progress">
          <ol class="stepper" data-stepper></ol>
        </nav>
        <main id="main" tabindex="-1" data-main></main>
      </div>`;

    const stepper = app.querySelector('[data-stepper]');
    STEPS.forEach((step, i) => {
      const li = document.createElement('li');
      li.className = 'stepper__item';
      li.setAttribute('role', 'button');
      li.setAttribute('tabindex', '0');
      li.dataset.step = step.id;
      li.innerHTML = `
        <span class="stepper__num">${i + 1}</span>
        <span>
          <span class="stepper__label">${step.label}</span>
          <span class="stepper__desc">${step.desc}</span>
        </span>`;
      li.addEventListener('click', () => goToStep(i));
      li.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToStep(i); }
      });
      stepper.append(li);
    });

    app.querySelector('[data-logout]').addEventListener('click', logout);
    const usernameEl = app.querySelector('[data-username]');
    API.auth.me().then((u) => {
      usernameEl.textContent = 'Signed in as ' + (u.user || 'admin');
    }).catch(() => {
      usernameEl.textContent = '';
    });
  }

  function updateStepper() {
    const items = app.querySelectorAll('.stepper__item');
    items.forEach((li, i) => {
      li.removeAttribute('aria-current');
      li.removeAttribute('data-state');
      if (i < currentStep) li.dataset.state = 'done';
      if (i === currentStep) li.setAttribute('aria-current', 'step');
    });
  }

  function renderScreenStep(stepId) {
    const main = app.querySelector('[data-main]');
    // leave current
    if (screenNodes[stepId]) {
      // already built — show it
    } else {
      const factory = window.Screens[stepId];
      if (!factory) { main.innerHTML = '<p>Screen not found.</p>'; return; }
      const node = factory(main);
      node.classList.add('screen');
      node.dataset.screen = stepId;
      screenNodes[stepId] = node;
      main.append(node);
    }

    // hide all, show current
    Object.entries(screenNodes).forEach(([id, node]) => {
      node.setAttribute('aria-current', id === stepId ? 'true' : 'false');
    });

    // prev/next nav
    let nav = main.querySelector('.screen-nav');
    if (!nav) {
      nav = document.createElement('div');
      nav.className = 'screen-nav';
      main.append(nav);
    }
    nav.innerHTML = '';
    if (currentStep > 0) {
      const prevBtn = document.createElement('button');
      prevBtn.className = 'btn';
      prevBtn.textContent = '← ' + STEPS[currentStep - 1].label;
      prevBtn.addEventListener('click', () => goToStep(currentStep - 1));
      nav.append(prevBtn);
    }
    if (currentStep < STEPS.length - 1) {
      const nextBtn = document.createElement('button');
      nextBtn.className = 'btn btn--primary screen-nav__next';
      nextBtn.textContent = STEPS[currentStep + 1].label + ' →';
      nextBtn.addEventListener('click', () => {
        const cur = screenNodes[STEPS[currentStep].id];
        if (cur && cur.api && cur.api.canAdvance && !cur.api.canAdvance()) {
          UI.toast('Complete this step before continuing.', 'warning');
          return;
        }
        goToStep(currentStep + 1);
      });
      nav.append(nextBtn);
    }

    // onEnter hook
    const active = screenNodes[stepId];
    if (active && active.api && active.api.onEnter) active.api.onEnter();
  }

  function goToStep(i) {
    if (i < 0 || i >= STEPS.length) return;
    // leave old
    const prevNode = screenNodes[STEPS[currentStep].id];
    if (prevNode && prevNode.api && prevNode.api.onLeave) prevNode.api.onLeave();

    currentStep = i;
    updateStepper();
    renderScreenStep(STEPS[i].id);

    // main focus for screen readers
    const main = app.querySelector('[data-main]');
    main.focus({ preventScroll: true });
  }

  /* ---- Auth ---------------------------------------------------------- */
  async function ensureAuth() {
    try {
      await API.auth.me();
      return true;
    } catch {
      return false;
    }
  }

  async function logout() {
    try { await API.auth.logout(); } catch {}
    document.cookie = 'session=; Max-Age=0; path=/';
    location.reload();
  }

  function showLogin() {
    app.innerHTML = `
      <div class="login-shell">
        <form class="card login-card" data-login-form>
          <div class="login-card__head">
            <div class="login-card__logo" aria-hidden="true">E</div>
            <h1>Ebook Sorter</h1>
            <p class="muted">Sign in to organize your library.</p>
          </div>
          <div class="login-error" data-login-error role="alert" aria-hidden="true"></div>
          <div class="field">
            <label for="username">Username</label>
            <input type="text" id="username" name="username" autocomplete="username" required autofocus />
          </div>
          <div class="field">
            <label for="password">Password</label>
            <input type="password" id="password" name="password" autocomplete="current-password" required />
          </div>
          <button type="submit" class="btn btn--primary btn--lg" style="width:100%">Sign in</button>
          <p class="field-hint mt-3" style="text-align:center">Default dev creds: admin / admin</p>
        </form>
      </div>`;

    app.querySelector('[data-login-form]').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = app.querySelector('#username').value;
      const password = app.querySelector('#password').value;
      const errEl = app.querySelector('[data-login-error]');
      try {
        await API.auth.login(username, password);
        errEl.setAttribute('aria-hidden', 'true');
        errEl.style.display = 'none';
        start();
      } catch (err) {
        errEl.textContent = err.message === 'unauthorized'
          ? 'Invalid username or password.'
          : 'Login failed: ' + err.message;
        errEl.setAttribute('aria-hidden', 'false');
        errEl.style.display = 'block';
      }
    });
  }

  /* ---- Boot ---------------------------------------------------------- */
  async function start() {
    const authed = await ensureAuth();
    if (!authed) { showLogin(); return; }
    renderShell();
    updateStepper();
    renderScreenStep(STEPS[0].id);
  }

  // listen for 401s from api.js
  window.addEventListener('auth-error', () => {
    UI.toast('Session expired. Please sign in again.', 'warning');
    setTimeout(showLogin, 1500);
  });

  start();
})();
