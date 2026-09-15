/* ============================================================================
   ui.js — shared UI helpers (no app logic). Toast, confirm, modal, status.
   Pure functions that return DOM or wire events. Direction-independent.
   ========================================================================== */

const UI = (() => {
  /* ---- Toast notifications ------------------------------------------ */
  let toastHost = null;
  function toastHostEl() {
    if (!toastHost) {
      toastHost = document.createElement('div');
      toastHost.setAttribute('role', 'status');
      toastHost.setAttribute('aria-live', 'polite');
      toastHost.setAttribute('aria-atomic', 'true');
      toastHost.style.cssText = `
        position:fixed; bottom:var(--sp-5); right:var(--sp-5);
        display:flex; flex-direction:column; gap:var(--sp-2);
        z-index:var(--z-toast); pointer-events:none;`;
      document.body.appendChild(toastHost);
    }
    return toastHost;
  }

  function toast(message, type = 'info', timeout = 4200) {
    const host = toastHostEl();
    const el = document.createElement('div');
    const styles = {
      success: 'var(--c-success)', error: 'var(--c-error)',
      warning: 'var(--c-warning)', info: 'var(--c-info)',
    };
    el.textContent = message;
    el.style.cssText = `
      pointer-events:auto; min-width:240px; max-width:360px;
      background:${styles[type] || styles.info}; color:#fff;
      padding:var(--sp-2) var(--sp-4); border-radius:var(--r-md);
      font-size:var(--fs-sm); font-weight:600; box-shadow:var(--sh-lg);
      opacity:0; transform:translateY(8px);
      transition:opacity var(--dur-base) var(--ease),transform var(--dur-base) var(--ease);`;
    host.appendChild(el);
    requestAnimationFrame(() => {
      el.style.opacity = '1'; el.style.transform = 'translateY(0)';
    });
    const timer = setTimeout(() => {
      el.style.opacity = '0'; el.style.transform = 'translateY(8px)';
      setTimeout(() => el.remove(), 300);
    }, timeout);
    el.addEventListener('click', () => { clearTimeout(timer); el.remove(); });
    return el;
  }

  /* ---- Confirm dialog ----------------------------------------------- */
  function confirm(message, { okText = 'OK', cancelText = 'Cancel', danger = false } = {}) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.setAttribute('role', 'dialog');
      overlay.setAttribute('aria-modal', 'true');
      overlay.style.cssText = `
        position:fixed; inset:0; background:rgb(15 23 42 / 0.5);
        display:flex; align-items:center; justify-content:center;
        z-index:var(--z-dialog); padding:var(--sp-4);`;
      overlay.innerHTML = `
        <div class="card" style="max-width:400px;width:100%;">
          <p style="margin-bottom:var(--sp-4);">${escapeHtml(message)}</p>
          <div class="row" style="justify-content:flex-end;">
            <button class="btn btn--ghost" data-cancel>${escapeHtml(cancelText)}</button>
            <button class="btn ${danger ? 'btn--danger' : 'btn--primary'}" data-ok>${escapeHtml(okText)}</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const okBtn = overlay.querySelector('[data-ok]');
      const cancelBtn = overlay.querySelector('[data-cancel]');
      function cleanup(result) { overlay.remove(); resolve(result); }
      okBtn.addEventListener('click', () => cleanup(true));
      cancelBtn.addEventListener('click', () => cleanup(false));
      overlay.addEventListener('click', (e) => { if (e.target === overlay) cleanup(false); });
      okBtn.focus();
      overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') cleanup(false);
        if (e.key === 'Tab') {
          // trap focus
          const focusable = [okBtn, cancelBtn];
          const i = focusable.indexOf(document.activeElement);
          if (e.shiftKey) focusable[(i - 1 + 2) % 2].focus();
          else focusable[(i + 1) % 2].focus();
          e.preventDefault();
        }
      });
    });
  }

  /* ---- Modal container ---------------------------------------------- */
  function modal({ title = '', content, width = 520 } = {}) {
    const overlay = document.createElement('div');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.style.cssText = `
      position:fixed; inset:0; background:rgb(15 23 42 / 0.5);
      display:flex; align-items:center; justify-content:center;
      z-index:var(--z-dialog); padding:var(--sp-4);`;
    const panel = document.createElement('div');
    panel.className = 'card';
    panel.style.cssText = `max-width:${width}px; width:100%; max-height:85vh; overflow:auto;`;
    panel.innerHTML = `
      <div class="spread mb-3">
        <h3>${escapeHtml(title)}</h3>
        <button class="btn btn--ghost btn--sm" aria-label="Close">&times;</button>
      </div>
      <div class="modal-body"></div>`;
    const body = panel.querySelector('.modal-body');
    if (typeof content === 'string') body.innerHTML = content;
    else if (content instanceof Node) body.appendChild(content);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);
    const closeBtn = overlay.querySelector('button[aria-label="Close"]');
    function close() { overlay.remove(); }
    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    overlay.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
    return { el: panel, body, close };
  }

  /* ---- Status badge ------------------------------------------------- */
  function badge(status) {
    const map = {
      matched: 'matched', previewed: 'matched',
      uncertain: 'uncertain',
      corrupt: 'error', error: 'error',
      pending: 'pending', skipped: 'pending', moved: 'moved',
    };
    const cls = 'badge badge--' + (map[status] || 'pending');
    return `<span class="${cls}">${escapeHtml(status || 'unknown')}</span>`;
  }

  /* ---- Escape HTML -------------------------------------------------- */
  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  return { toast, confirm, modal, badge, escapeHtml };
})();
