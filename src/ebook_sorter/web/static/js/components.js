/* ============================================================================
   components.js — screen-agnostic reusable widgets.
   All directions reuse these. Pure factory functions returning DOM nodes.
   Depends on api.js (API) and ui.js (UI).
   ========================================================================== */

const Components = (() => {
  const $ = (tag, attrs = {}, children = []) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'class') el.className = v;
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else if (v !== false && v != null) el.setAttribute(k, v);
    }
    for (const c of [].concat(children)) {
      if (c == null || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  };

  /* ------------------------------------------------------------------ */
  /* 1. Directory tree browser                                          */
  /*    opts: { root: 'books'|output', multiSelect: bool,               */
  /*            onSelect(paths), onPick(path) }                         */
  /* ------------------------------------------------------------------ */
  function dirTree(opts) {
    const { root = 'books', multiSelect = false, onSelect, onPick } = opts;
    const selected = new Set();

    const list = $('ul', {
      class: 'tree', role: 'tree', 'aria-label': `${root} directory`,
    });

    function emit() {
      if (onSelect) onSelect([...selected]);
    }

    async function loadInto(li, ul, relPath) {
      ul.innerHTML = '';
      let entries;
      try {
        entries = await API.browse(root, relPath);
      } catch (e) {
        if (e.status === 401) throw e;
        ul.append($('li', { class: 'tree__error', role: 'treeitem' }, 'Error: ' + e.message));
        return;
      }
      entries.sort((a, b) => Number(b.is_dir) - Number(a.is_dir) || a.name.localeCompare(b.name));

      for (const e of entries) {
        const childLi = $('li', { role: 'treeitem', 'aria-expanded': e.is_dir ? 'false' : null });
        if (!e.is_dir) {
          const cb = $('input', { type: 'checkbox', class: 'tree__cb', 'aria-label': `select ${e.name}` });
          cb.addEventListener('change', () => {
            if (cb.checked) selected.add(e.rel); else selected.delete(e.rel);
            emit();
          });
          childLi.append(cb, $('span', { class: 'tree__name' }, e.name));
          if (onPick) {
            childLi.append($('button', {
              class: 'btn btn--ghost btn--sm tree__pick', type: 'button',
              onClick: () => onPick(e.rel),
            }, 'Use this'));
          }
        } else {
          const toggle = $('button', {
            class: 'tree__toggle', type: 'button',
            'aria-label': `Expand ${e.name}`,
          }, '▸');
          const label = $('span', { class: 'tree__name tree__folder', tabindex: '0' }, e.name);
          const childUl = $('ul', { role: 'group' });
          childUl.classList.add('hidden');
          const toggleFn = async () => {
            const expanded = toggle.textContent === '▾';
            toggle.textContent = expanded ? '▸' : '▾';
            childLi.setAttribute('aria-expanded', String(!expanded));
            if (!expanded && childUl.dataset.loaded !== '1') {
              await loadInto(childLi, childUl, e.rel);
              childUl.dataset.loaded = '1';
            }
            childUl.classList.toggle('hidden', expanded);
          };
          toggle.addEventListener('click', toggleFn);
          label.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); toggleFn(); }
          });
          childLi.append(toggle, label, childUl);
        }
        ul.append(childLi);
      }
    }

    // root level
    const rootUl = list;
    loadInto(null, rootUl, '').catch((e) => {
      if (e.status === 401) opts.onAuthError && opts.onAuthError();
    });

    const refreshBtn = $('button', {
      class: 'btn btn--ghost btn--sm', type: 'button', 'aria-label': 'Refresh directory tree',
    }, 'Refresh');
    refreshBtn.addEventListener('click', () => {
      rootUl.innerHTML = '';
      loadInto(null, rootUl, '').catch(() => {});
    });

    const clearBtn = multiSelect ? $('button', {
      class: 'btn btn--ghost btn--sm', type: 'button',
    }, 'Clear selection') : null;
    if (clearBtn) clearBtn.addEventListener('click', () => {
      selected.clear();
      rootUl.querySelectorAll('input[type="checkbox"]').forEach((cb) => (cb.checked = false));
      emit();
    });

    const wrap = $('div', { class: 'tree-wrap' }, [
      $('div', { class: 'tree-toolbar spread mb-2' }, [
        $('span', { class: 'tree__selected text-sm muted' }, '0 selected'),
        $('div', { class: 'row gap-2' }, [clearBtn, refreshBtn]),
      ]),
      list,
    ]);

    // keep the counter in sync
    const counter = wrap.querySelector('.tree__selected');
    const origEmit = emit;
    function emitWithCount() {
      counter.textContent = `${selected.size} selected`;
      origEmit();
    }
    // re-bind by wrapping onSelect through the closure above — we patch via event
    list.addEventListener('change', emitWithCount);

    wrap.api = { getSelected: () => [...selected], refresh: () => refreshBtn.click() };
    return wrap;
  }

  /* ------------------------------------------------------------------ */
  /* 2. Item / metadata card (review screen)                            */
  /* ------------------------------------------------------------------ */
  function itemCard(item, { onEdit, onApply, onReset, onRelookup, editable = false } = {}) {
    const m = item.meta || {};
    const before = item.planned_dest || '';
    const after = item.actual_dest || '';

    const metaFields = $('dl', { class: 'meta-grid' });
    const rows = [
      ['Title', m.title], ['Authors', (m.authors || []).join(', ')],
      ['Series', m.series ? `${m.series} #${m.series_index ?? ''}` : null],
      ['ISBN', m.isbn_13 || m.isbn_10], ['Year', m.year],
      ['Publisher', m.publisher], ['Language', m.language],
      ['Source', m.source],
    ];
    for (const [k, v] of rows) {
      if (!v) continue;
      metaFields.append(
        $('dt', { class: 'muted text-sm' }, k),
        $('dd', {}, String(v)),
      );
    }

    const confPct = Math.round((item.meta?.confidence || 0) * 100);
    const confidence = $('div', { class: 'row gap-2 mt-2' }, [
      $('span', { class: 'text-sm muted' }, `Confidence: ${confPct}%`),
      $('div', { class: 'progress grow', style: 'flex:1;max-width:180px' }, [
        $('div', {
          class: 'progress__bar',
          style: `width:${confPct}%;background:${confPct >= 70 ? 'var(--c-success)' : confPct >= 40 ? 'var(--c-warning)' : 'var(--c-error)'}`,
        }),
      ]),
    ]);

    const beforeAfter = $('div', { class: 'before-after mt-3' }, [
      $('div', {}, [$('span', { class: 'text-sm muted' }, 'From:'), $('code', { class: 'mono' }, item.source_path || '')]),
      $('div', {}, [$('span', { class: 'text-sm muted' }, 'To:'), $('code', { class: 'mono' }, before || '—')]),
      after ? $('div', {}, [$('span', { class: 'text-sm muted' }, 'Applied:'), $('code', { class: 'mono' }, after)]) : null,
    ]);

    const actions = $('div', { class: 'row gap-2 mt-3 wrap' });
    if (editable && onEdit) actions.append($('button', { class: 'btn btn--sm', onClick: onEdit }, 'Edit'));
    if (onRelookup) actions.append($('button', { class: 'btn btn--ghost btn--sm', onClick: onRelookup }, 'Re-lookup'));
    if (onApply) actions.append($('button', { class: 'btn btn--primary btn--sm', onClick: onApply }, 'Apply'));
    if (onReset) actions.append($('button', { class: 'btn btn--ghost btn--sm', onClick: onReset }, 'Reset'));

    const card = $('article', {
      class: 'card item-card',
      dataset: { status: item.status, item: item.id },
    }, [
      $('div', { class: 'spread mb-2' }, [
        $('div', { class: 'row gap-2' }, [UI.badge(item.status)]),
        $('span', { class: 'text-sm muted mono' }, `#${item.id}`),
      ]),
      metaFields,
      confidence,
      beforeAfter,
      actions,
    ]);
    return card;
  }

  /* ------------------------------------------------------------------ */
  /* 3. Metadata editor form (returns form + getValues)                 */
  /* ------------------------------------------------------------------ */
  function metadataForm(meta = {}, { onLookup, readonly = false } = {}) {
    const fields = {
      title: 'Title', authors: 'Authors (comma-separated)',
      series: 'Series', series_index: 'Series #',
      isbn_13: 'ISBN-13', isbn_10: 'ISBN-10',
      year: 'Year', publisher: 'Publisher', language: 'Language',
    };
    const inputs = {};
    const form = $('form', { class: 'meta-form' });

    for (const [key, label] of Object.entries(fields)) {
      const inp = $('input', {
        type: key.includes('index') || key === 'year' ? 'number' : 'text',
        value: meta[key] || (key === 'authors' ? (meta.authors || []).join(', ') : ''),
        placeholder: ' ',
        readonly: readonly || false,
        step: key.includes('index') ? '0.1' : null,
      });
      const wrap2 = $('div', { class: 'field' }, [
        $('label', { for: `f_${key}` }, label),
        (() => { inp.id = `f_${key}`; return inp; })(),
      ]);
      form.append(wrap2);
      inputs[key] = inp;
    }

    function getValues() {
      return {
        title: inputs.title.value.trim() || undefined,
        authors: inputs.authors.value.split(',').map((s) => s.trim()).filter(Boolean),
        series: inputs.series.value.trim() || undefined,
        series_index: inputs.series_index.value ? parseFloat(inputs.series_index.value) : undefined,
        isbn_13: inputs.isbn_13.value.trim() || undefined,
        isbn_10: inputs.isbn_10.value.trim() || undefined,
        year: inputs.year.value ? parseInt(inputs.year.value, 10) : undefined,
        publisher: inputs.publisher.value.trim() || undefined,
        language: inputs.language.value.trim() || undefined,
      };
    }

    form.addEventListener('submit', (e) => e.preventDefault());
    if (onLookup) {
      form.append($('button', {
        type: 'button', class: 'btn btn--ghost btn--sm mt-2', onClick: onLookup,
      }, 'Re-lookup'));
    }
    form.api = { getValues, setValues: (data) => {
      for (const k of Object.keys(fields)) {
        if (data[k] != null) inputs[k].value = Array.isArray(data[k]) ? data[k].join(', ') : data[k];
      }
    } };
    return form;
  }

  /* ------------------------------------------------------------------ */
  /* 4. Log list (live feed)                                            */
  /* ------------------------------------------------------------------ */
  function logList({ max = 200 } = {}) {
    const list = $('ol', { class: 'log-list' });
    list.scrollTop = 0;

    function append(entry) {
      const li = $('li', { class: 'log-entry' });
      const time = new Date().toLocaleTimeString();
      if (entry.type === 'error') li.classList.add('log-entry--error');
      else if (entry.type === 'warn') li.classList.add('log-entry--warn');
      else if (entry.type === 'success') li.classList.add('log-entry--success');

      if (entry.source) li.append($('span', { class: 'log-entry__src mono' }, entry.source));
      li.append($('span', { class: 'log-entry__msg' }, entry.message || entry.text || ''));
      li.append($('span', { class: 'log-entry__time muted' }, time));
      list.append(li);
      while (list.children.length > max) list.removeChild(list.firstChild);
      list.scrollTop = list.scrollHeight;
    }

    function clear() { list.innerHTML = ''; }

    list.api = { append, clear };
    return list;
  }

  /* ------------------------------------------------------------------ */
  /* 5. Job progress block (counts + bar)                               */
  /* ------------------------------------------------------------------ */
  function jobProgress(job) {
    const c = job || { total: 0, matched: 0, uncertain: 0, error: 0, moved: 0 };
    const done = c.matched + c.uncertain + c.error + c.moved;
    const pct = c.total ? Math.round((done / c.total) * 100) : 0;

    const bar = $('div', { class: 'progress', 'aria-label': 'Job progress', role: 'progressbar',
      'aria-valuenow': pct, 'aria-valuemin': 0, 'aria-valuemax': 100 }, [
      $('div', { class: 'progress__bar', style: `width:${pct}%` }),
    ]);

    const counts = $('div', { class: 'counts' }, [
      countBadge('Matched', c.matched, 'matched'),
      countBadge('Uncertain', c.uncertain, 'uncertain'),
      countBadge('Error', c.error, 'error'),
      countBadge('Moved', c.moved, 'moved'),
      $('span', { class: 'muted text-sm' }, `${done}/${c.total}`),
    ]);

    function countBadge(label, n, cls) {
      return $('span', { class: `badge badge--${cls}` }, `${label}: ${n}`);
    }

    const wrap = $('div', { class: 'job-progress' }, [
      $('div', { class: 'spread mb-2' }, [
        $('span', { class: 'text-sm' }, `${pct}% complete`),
        $('span', { class: 'badge', dataset: { status: c.status } }, c.status || 'created'),
      ]),
      bar,
      counts,
    ]);

    wrap.api = update;
    function update(job) {
      const c2 = job || {};
      const done2 = (c2.matched||0) + (c2.uncertain||0) + (c2.error||0) + (c2.moved||0);
      const total2 = c2.total || 1;
      const pct2 = Math.round((done2 / total2) * 100);
      bar.firstElementChild.style.width = pct2 + '%';
      bar.setAttribute('aria-valuenow', pct2);
      const badges = counts.querySelectorAll('.badge');
      badges[0].textContent = `Matched: ${c2.matched||0}`;
      badges[1].textContent = `Uncertain: ${c2.uncertain||0}`;
      badges[2].textContent = `Error: ${c2.error||0}`;
      badges[3].textContent = `Moved: ${c2.moved||0}`;
      badges[4].textContent = `${done2}/${c2.total||0}`;
    }
    return wrap;
  }

  return { dirTree, itemCard, metadataForm, logList, jobProgress, $ };
})();
