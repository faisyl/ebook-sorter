/* ============================================================================
   stub.js — dev-only mock API matching spec sec 5. Replaced by real backend.
   Intercepts fetch to /api/* and serves deterministic fake data.
   OFF by default: the real backend is used unless a developer explicitly
   opts in with window.__USE_STUB__ = true (e.g. for frontend dev with no
   server). Shipping this active would hijack the real API — hence opt-in.
   ========================================================================== */
(function () {
  if (window.__USE_STUB__ !== true) return;

  const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms));
  const origFetch = window.fetch;

  // --- fake data stores ---
  const BOOKS_TREE = {
    '': [
      { name: 'Sci-Fi', is_dir: true, rel: 'Sci-Fi' },
      { name: 'Fantasy', is_dir: true, rel: 'Fantasy' },
      { name: 'Nonfiction', is_dir: true, rel: 'Nonfiction' },
      { name: 'misc.epub', is_dir: false, rel: 'misc.epub' },
    ],
    'Sci-Fi': [
      { name: 'Asimov', is_dir: true, rel: 'Sci-Fi/Asimov' },
      { name: 'Herbert', is_dir: true, rel: 'Sci-Fi/Herbert' },
      { name: 'Le Guin', is_dir: true, rel: 'Sci-Fi/Le Guin' },
    ],
    'Sci-Fi/Asimov': [
      { name: 'Foundation.epub', is_dir: false, rel: 'Sci-Fi/Asimov/Foundation.epub' },
      { name: 'I, Robot.pdf', is_dir: false, rel: 'Sci-Fi/Asimov/I, Robot.pdf' },
    ],
    'Sci-Fi/Herbert': [
      { name: 'Dune.epub', is_dir: false, rel: 'Sci-Fi/Herbert/Dune.epub' },
      { name: 'Dune Messiah.epub', is_dir: false, rel: 'Sci-Fi/Herbert/Dune Messiah.epub' },
    ],
    'Sci-Fi/Le Guin': [
      { name: 'The Left Hand of Darkness.epub', is_dir: false, rel: 'Sci-Fi/Le Guin/The Left Hand of Darkness.epub' },
    ],
    'Fantasy': [
      { name: 'Tolkien', is_dir: true, rel: 'Fantasy/Tolkien' },
      { name: 'Pratchett', is_dir: true, rel: 'Fantasy/Pratchett' },
    ],
    'Fantasy/Tolkien': [
      { name: 'The Hobbit.epub', is_dir: false, rel: 'Fantasy/Tolkien/The Hobbit.epub' },
      { name: 'LOTR.epub', is_dir: false, rel: 'Fantasy/Tolkien/LOTR.epub' },
    ],
    'Fantasy/Pratchett': [
      { name: 'Guards! Guards!.epub', is_dir: false, rel: 'Fantasy/Pratchett/Guards! Guards!.epub' },
      { name: 'Mort.epub', is_dir: false, rel: 'Fantasy/Pratchett/Mort.epub' },
    ],
    'Nonfiction': [
      { name: 'Sapiens.epub', is_dir: false, rel: 'Nonfiction/Sapiens.epub' },
      { name: 'Atomic Habits.pdf', is_dir: false, rel: 'Nonfiction/Atomic Habits.pdf' },
    ],
  };

  const OUTPUT_TREE = {
    '': [
      { name: 'sorted', is_dir: true, rel: 'sorted' },
      { name: 'to-sort', is_dir: true, rel: 'to-sort' },
    ],
    'sorted': [
      { name: 'Asimov, Isaac', is_dir: true, rel: 'sorted/Asimov, Isaac' },
      { name: 'Herbert, Frank', is_dir: true, rel: 'sorted/Herbert, Frank' },
    ],
  };

  const AUTHORS = {
    'Foundation.epub': { title: 'Foundation', authors: ['Asimov, Isaac'], series: 'Foundation', series_index: 1, isbn_13: '978-0553293357', year: 1951, publisher: 'Bantam', language: 'en', source: 'filename+lookup', confidence: 0.95 },
    'I, Robot.pdf': { title: 'I, Robot', authors: ['Asimov, Isaac'], series: 'Robot', series_index: 1, isbn_13: '978-0553294385', year: 1950, publisher: 'Bantam', language: 'en', source: 'lookup', confidence: 0.92 },
    'Dune.epub': { title: 'Dune', authors: ['Herbert, Frank'], series: 'Dune Chronicles', series_index: 1, isbn_13: '978-0441172719', year: 1965, publisher: 'Ace', language: 'en', source: 'lookup', confidence: 0.97 },
    'Dune Messiah.epub': { title: 'Dune Messiah', authors: ['Herbert, Frank'], series: 'Dune Chronicles', series_index: 2, isbn_13: '978-0441172696', year: 1969, publisher: 'Ace', language: 'en', source: 'lookup', confidence: 0.96 },
    'The Left Hand of Darkness.epub': { title: 'The Left Hand of Darkness', authors: ['Le Guin, Ursula K.'], isbn_13: '978-0441478125', year: 1969, publisher: 'Ace', language: 'en', source: 'lookup', confidence: 0.93 },
    'The Hobbit.epub': { title: 'The Hobbit', authors: ['Tolkien, J.R.R.'], isbn_13: '978-0547928227', year: 1937, publisher: 'Mariner', language: 'en', source: 'lookup', confidence: 0.98 },
    'LOTR.epub': { title: 'The Lord of the Rings', authors: ['Tolkien, J.R.R.'], series: 'Middle-earth', series_index: 0, isbn_13: '978-0544003415', year: 1954, publisher: 'Mariner', language: 'en', source: 'lookup', confidence: 0.94 },
    'Guards! Guards!.epub': { title: 'Guards! Guards!', authors: ['Pratchett, Terry'], series: 'Discworld', series_index: 8, isbn_13: '978-0062225672', year: 1989, publisher: 'Harper', language: 'en', source: 'lookup', confidence: 0.91 },
    'Mort.epub': { title: 'Mort', authors: ['Pratchett, Terry'], series: 'Discworld', series_index: 4, isbn_13: '978-0062225665', year: 1987, publisher: 'Harper', language: 'en', source: 'lookup', confidence: 0.90 },
    'Sapiens.epub': { title: 'Sapiens', authors: ['Harari, Yuval Noah'], isbn_13: '978-0062316097', year: 2015, publisher: 'Harper', language: 'en', source: 'lookup', confidence: 0.88 },
    'Atomic Habits.pdf': { title: 'Atomic Habits', authors: ['Clear, James'], isbn_13: '978-0735211292', year: 2018, publisher: 'Avery', language: 'en', source: 'lookup', confidence: 0.85 },
    'misc.epub': { title: 'Unknown Book', authors: [], source: 'filename', confidence: 0.25 },
  };

  function renderDest(meta, template) {
    const author = (meta.authors && meta.authors[0]) || 'Unknown';
    const seriesPart = meta.series ? ` - ${meta.series} ${String(meta.series_index || '').padStart(2, '0')}`.trim() : '';
    return `${author}/${meta.title || 'Unknown'}${meta.year ? ' (' + meta.year + ')' : ''}.epub`;
  }

  let JOBS = [];
  let JOB_ID = 1;

  function makeItems(subdirs) {
    const items = [];
    const allFiles = [];
    function collect(dir) {
      const entries = BOOKS_TREE[dir] || [];
      for (const e of entries) {
        if (e.is_dir) collect(e.rel);
        else allFiles.push(e);
      }
    }
    for (const s of subdirs) collect(s);
    for (const f of allFiles) {
      const meta = AUTHORS[f.name] || { title: f.name, authors: [], source: 'filename', confidence: 0.2 };
      const id = String(items.length + 1);
      items.push({
        id, source_path: f.rel,
        status: 'pending',
        meta: { ...meta },
        planned_dest: '',
        actual_dest: '',
        error: null, user_edited: false,
      });
    }
    return items;
  }

  window.fetch = async function (input, init) {
    const url = typeof input === 'string' ? input : input.url;
    if (!url.startsWith('/api/')) return origFetch.apply(this, arguments);

    const method = (init && init.method) || 'GET';
    const path = url.replace('/api', '');
    const body = (init && init.body) ? JSON.parse(init.body) : null;

    await delay(150 + Math.random() * 200);

    // --- auth ---
    if (method === 'POST' && path === '/login') {
      if (body.username === 'admin' && body.password === 'admin') {
        return json({ ok: true, user: body.username });
      }
      return json({ detail: 'Invalid credentials' }, 401);
    }
    if (method === 'POST' && path === '/logout') return json({});
    if (method === 'GET' && path === '/me') return json({ user: 'admin' });

    // --- browse ---
    if (method === 'GET' && path.startsWith('/browse')) {
      const p = new URL('http://x' + url);
      const root = p.searchParams.get('root');
      const rel = p.searchParams.get('path') || '';
      const tree = root === 'output' ? OUTPUT_TREE : BOOKS_TREE;
      const entries = tree[rel] || [];
      return json({ entries });
    }

    // --- jobs ---
    if (method === 'GET' && path === '/jobs') return json(JOBS.map(summary));
    if (method === 'POST' && path === '/jobs') {
      const id = 'job-' + (JOB_ID++);
      const items = makeItems(body.subdirs || []);
      const job = {
        id, name: body.name || 'Untitled run',
        input_root: body.input_root, subdirs: body.subdirs || [],
        output_dir: body.output_dir || '', options: body.options || {},
        status: 'previewing', created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
        total: items.length, matched: 0, uncertain: 0, error: 0, moved: 0,
        items,
      };
      JOBS.push(job);
      // simulate preview progress
      simulatePreview(job);
      return json(summary(job));
    }

    const jobMatch = path.match(/^\/jobs\/([\w-]+)$/);
    if (method === 'GET' && jobMatch) {
      const j = JOBS.find((x) => x.id === jobMatch[1]);
      if (!j) return json({ detail: 'not found' }, 404);
      return json(summary(j));
    }

    const itemsMatch = path.match(/^\/jobs\/([\w-]+)\/items$/);
    if (method === 'GET' && itemsMatch) {
      const j = JOBS.find((x) => x.id === itemsMatch[1]);
      if (!j) return json({ detail: 'not found' }, 404);
      const p = new URL('http://x' + url);
      const statusFilter = p.searchParams.get('status');
      let items = j.items;
      if (statusFilter) items = items.filter((i) => i.status === statusFilter);
      return json({ items, next_cursor: null });
    }

    const itemMatch = path.match(/^\/jobs\/([\w-]+)\/items\/([\w-]+)$/);
    if (method === 'GET' && itemMatch) {
      const j = JOBS.find((x) => x.id === itemMatch[1]);
      const item = j && j.items.find((i) => i.id === itemMatch[2]);
      if (!item) return json({ detail: 'not found' }, 404);
      return json({ ...item, candidates: [item.meta] });
    }
    if (method === 'PATCH' && itemMatch) {
      const j = JOBS.find((x) => x.id === itemMatch[1]);
      const item = j && j.items.find((i) => i.id === itemMatch[2]);
      if (!item) return json({ detail: 'not found' }, 404);
      Object.assign(item.meta, body, { confidence: 0.99 });
      item.user_edited = true;
      item.status = 'matched';
      item.planned_dest = renderDest(item.meta);
      return json(item);
    }

    const actionMatch = path.match(/^\/jobs\/([\w-]+)\/items\/([\w-]+)\/(\w+)$/);
    if (actionMatch) {
      const j = JOBS.find((x) => x.id === actionMatch[1]);
      const item = j && j.items.find((i) => i.id === actionMatch[2]);
      if (!item) return json({ detail: 'not found' }, 404);
      const action = actionMatch[3];
      if (action === 'relookup') {
        item.meta.confidence = Math.min(1, item.meta.confidence + 0.05);
        return json({ ...item, candidates: [item.meta] });
      }
      if (action === 'apply') {
        item.status = 'moved';
        item.actual_dest = item.planned_dest;
        j.moved++;
        return json(item);
      }
      if (action === 'reset') {
        const fresh = makeItems([item.source_path])[0];
        Object.assign(item, fresh);
        return json(item);
      }
    }

    const jobAction = path.match(/^\/jobs\/([\w-]+)\/(\w+)$/);
    if (jobAction) {
      const j = JOBS.find((x) => x.id === jobAction[1]);
      if (!j) return json({ detail: 'not found' }, 404);
      const action = jobAction[2];
      if (action === 'apply') {
        j.status = 'applying';
        simulateApply(j);
        return json(summary(j));
      }
      if (action === 'pause') { j.status = 'paused'; return json(summary(j)); }
      if (action === 'resume') { j.status = 'running'; return json(summary(j)); }
      if (action === 'cancel') { j.status = 'cancelled'; return json(summary(j)); }
    }

    return json({ detail: 'not stubbed: ' + method + ' ' + path }, 501);
  };

  function json(data, status = 200) {
    return {
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => 'application/json' },
      json: async () => data,
      text: async () => JSON.stringify(data),
    };
  }

  function summary(j) {
    const counts = { matched: 0, uncertain: 0, error: 0, moved: 0 };
    for (const i of j.items) {
      if (i.status === 'matched' || i.status === 'previewed') counts.matched++;
      else if (i.status === 'uncertain') counts.uncertain++;
      else if (i.status === 'error' || i.status === 'corrupt') counts.error++;
      else if (i.status === 'moved') counts.moved++;
    }
    return {
      id: j.id, name: j.name, status: j.status,
      total: j.items.length, ...counts,
      created_at: j.created_at, updated_at: j.updated_at,
    };
  }

  function simulatePreview(job) {
    let i = 0;
    const tick = () => {
      if (i >= job.items.length) {
        job.status = 'preview_ready';
        return;
      }
      const item = job.items[i];
      const conf = item.meta.confidence;
      item.status = conf >= (job.options.confidence_threshold || 0.7) ? 'matched' : 'uncertain';
      item.planned_dest = renderDest(item.meta, job.options.template);
      i++;
      setTimeout(tick, 300 + Math.random() * 400);
    };
    setTimeout(tick, 500);
  }

  function simulateApply(job) {
    let i = 0;
    const tick = () => {
      const next = job.items.find((x) => x.status === 'matched' || x.status === 'previewed');
      if (!next) { job.status = 'completed'; return; }
      next.status = 'moved';
      next.actual_dest = next.planned_dest;
      job.moved++;
      i++;
      setTimeout(tick, 400 + Math.random() * 500);
    };
    setTimeout(tick, 400);
  }
})();
