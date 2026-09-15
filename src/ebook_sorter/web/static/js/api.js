/* ============================================================================
   api.js — data layer (no UI). Wraps the spec sec-5 HTTP API + WS events.
   Auth: cookie-based; on 401 the caller should redirect to #/login.
   All methods return Promises; throw Error with .status on HTTP errors.
   ========================================================================== */

const API = (() => {
  const BASE = '/api';

  async function request(method, path, body) {
    const opts = { method, headers: {}, credentials: 'same-origin' };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(BASE + path, opts);
    if (res.status === 401) {
      const err = new Error('unauthorized');
      err.status = 401;
      throw err;
    }
    if (res.status === 204) return null;
    const ct = res.headers.get('content-type') || '';
    const data = ct.includes('application/json') ? await res.json() : await res.text();
    if (!res.ok) {
      const err = new Error((data && data.detail) || `HTTP ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  /* ---- Auth ---------------------------------------------------------- */
  const auth = {
    login: (username, password) => request('POST', '/login', { username, password }),
    logout: () => request('POST', '/logout'),
    me: () => request('GET', '/me'),
  };

  /* ---- Browse -------------------------------------------------------- */
  const browse = (root, path = '') =>
    request('GET', `/browse?root=${encodeURIComponent(root)}&path=${encodeURIComponent(path)}`);

  /* ---- Jobs ---------------------------------------------------------- */
  const jobs = {
    list: () => request('GET', '/jobs'),
    get: (id) => request('GET', `/jobs/${id}`),
    create: (payload) => request('POST', '/jobs', payload),
    items: (id, params = {}) => {
      const qs = new URLSearchParams();
      if (params.status) qs.set('status', params.status);
      if (params.limit) qs.set('limit', params.limit);
      if (params.cursor) qs.set('cursor', params.cursor);
      const q = qs.toString();
      return request('GET', `/jobs/${id}/items${q ? '?' + q : ''}`);
    },
    apply: (id) => request('POST', `/jobs/${id}/apply`),
    pause: (id) => request('POST', `/jobs/${id}/pause`),
    resume: (id) => request('POST', `/jobs/${id}/resume`),
    cancel: (id) => request('POST', `/jobs/${id}/cancel`),

    /* ---- Review / redo (per item) -------------------------------- */
    item: (jobId, itemId) => request('GET', `/jobs/${jobId}/items/${itemId}`),
    patchItem: (jobId, itemId, fields) =>
      request('PATCH', `/jobs/${jobId}/items/${itemId}`, fields),
    relookup: (jobId, itemId, overrides = {}) =>
      request('POST', `/jobs/${jobId}/items/${itemId}/relookup`, overrides),
    applyItem: (jobId, itemId) =>
      request('POST', `/jobs/${jobId}/items/${itemId}/apply`),
    resetItem: (jobId, itemId) =>
      request('POST', `/jobs/${jobId}/items/${itemId}/reset`),
  };

  /* ---- WebSocket events (with polling fallback) --------------------- */
  function events(id, handlers = {}) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/api/jobs/${id}/events`;
    let ws = null;
    let pollTimer = null;
    let closed = false;

    const { onItem, onJob, onLog, onStatus, onOpen, onClose } = handlers;

    function startPoll() {
      if (pollTimer || closed) return;
      pollTimer = setInterval(async () => {
        try {
          const job = await jobs.get(id);
          if (onJob) onJob(job);
          if (onStatus && job.status) onStatus(job.status);
        } catch (e) { /* swallow; WS may come back */ }
      }, 3000);
    }

    function connect() {
      try {
        ws = new WebSocket(url);
      } catch {
        startPoll();
        return;
      }
      ws.onopen = () => {
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        if (onOpen) onOpen();
      };
      ws.onmessage = (ev) => {
        let msg;
        try { msg = JSON.parse(ev.data); } catch { return; }
        if (msg.type === 'item_update' && onItem) onItem(msg);
        else if (msg.type === 'job_update' && onJob) onJob(msg);
        else if (msg.type === 'log' && onLog) onLog(msg);
      };
      ws.onerror = () => { /* fall through to close */ };
      ws.onclose = () => {
        if (closed) return;
        startPoll();
        if (onClose) onClose();
        // Reconnect after a delay
        setTimeout(() => { if (!closed) connect(); }, 4000);
      };
    }

    connect();

    return {
      close: () => {
        closed = true;
        if (pollTimer) clearInterval(pollTimer);
        if (ws) try { ws.close(); } catch {}
      },
    };
  }

  return { auth, browse, jobs, events };
})();
