/* ============================================================================
   screens.js — guided flow (direction B) step wizard.
   4 steps: Select → Configure → Preview → Review.
   Each step returns a DOM node and exposes onEnter/onLeave hooks.
   Uses api.js, ui.js, components.js.
   ========================================================================== */
(function () {
  const Screens = {};
  const state = {
    selected: [],        // selected subdir rel paths
    outputDir: '',
    options: {
      template: '{author_sort}/{series}/{title} ({year}).{ext}',
      confidence_threshold: 0.7,
      ocr_enabled: false,
      mode: 'move',
    },
    currentJob: null,
    reviewFilter: 'uncertain',
  };

  /* ------------------------------------------------------------------ */
  /* Step 1: Select                                                      */
  /* ------------------------------------------------------------------ */
  Screens.select = function (root) {
    const wrap = document.createElement('div');
    const browseGrid = document.createElement('div');
    browseGrid.className = 'browse-grid';

    const tree = Components.dirTree({
      root: 'books',
      multiSelect: true,
      onSelect: (paths) => { state.selected = paths; renderChips(); },
      onAuthError: () => { window.dispatchEvent(new CustomEvent('auth-error')); },
    });

    const selectedPane = document.createElement('aside');
    selectedPane.className = 'browse-selected';
    selectedPane.innerHTML = `<h4>Selected folders</h4>
      <div class="chips" data-chips></div>
      <p class="text-sm muted mt-2" data-hint>Select one or more folders from the tree. Folders are multi-select.</p>`;

    const chipsEl = selectedPane.querySelector('[data-chips]');
    const hintEl = selectedPane.querySelector('[data-hint]');

    function renderChips() {
      chipsEl.innerHTML = '';
      for (const p of state.selected) {
        const chip = document.createElement('span');
        chip.className = 'chip';
        chip.innerHTML = `${UI.escapeHtml(p)} <button class="chip__remove" aria-label="Remove ${UI.escapeHtml(p)}">&times;</button>`;
        chip.querySelector('button').addEventListener('click', () => {
          state.selected = state.selected.filter((s) => s !== p);
          tree.api.refresh();
          renderChips();
        });
        chipsEl.append(chip);
      }
      hintEl.textContent = state.selected.length
        ? `${state.selected.length} folder(s) selected. Next: configure options.`
        : 'Select one or more folders from the tree. Folders are multi-select.';
    }

    browseGrid.append(tree, selectedPane);
    wrap.append(
      document.createElement('div'), // placeholder for head
      browseGrid,
    );
    wrap.querySelector('div').className = 'screen__head';
    wrap.querySelector('div').innerHTML = `<h2>1. Select folders</h2>
      <p class="muted">Pick the folders under <code class="mono">/books</code> you want to sort.</p>`;

    wrap.api = {
      onEnter: () => tree.api.refresh(),
      canAdvance: () => state.selected.length > 0,
      getData: () => ({ subdirs: [...state.selected] }),
    };
    return wrap;
  };

  /* ------------------------------------------------------------------ */
  /* Step 2: Configure                                                   */
  /* ------------------------------------------------------------------ */
  Screens.configure = function () {
    const wrap = document.createElement('div');
    wrap.className = 'screen';

    const form = document.createElement('form');
    form.className = 'options-grid';

    // Output dir picker
    const outField = document.createElement('div');
    outField.className = 'field field--full';
    outField.innerHTML = `<label for="output-dir">Output directory</label>`;
    const outTree = Components.dirTree({
      root: 'output',
      multiSelect: false,
      onPick: (path) => {
        state.outputDir = path;
        outInput.value = path;
      },
    });
    outTree.querySelector('.tree-toolbar').remove();
    const outInput = document.createElement('input');
    outInput.type = 'text';
    outInput.id = 'output-dir';
    outInput.placeholder = 'Click a folder in the tree, or type a path';
    outInput.value = state.outputDir;
    outInput.addEventListener('input', () => { state.outputDir = outInput.value; });
    outField.append(outInput, outTree, document.createElement('p'));
    outField.querySelector('p').className = 'field-hint';
    outField.querySelector('p').textContent = 'Where sorted books will be written (/output).';

    // Options
    const templateField = document.createElement('div');
    templateField.className = 'field field--full';
    templateField.innerHTML = `<label for="template">Filename template</label>`;
    const templateInput = document.createElement('input');
    templateInput.type = 'text';
    templateInput.id = 'template';
    templateInput.value = state.options.template;
    templateInput.addEventListener('input', () => { state.options.template = templateInput.value; });
    templateField.append(templateInput, document.createElement('p'));
    templateField.querySelector('p').className = 'field-hint';
    templateField.querySelector('p').textContent = 'e.g. {author_sort}/{series}/{title} ({year}).{ext}';

    const thresholdField = document.createElement('div');
    thresholdField.className = 'field';
    thresholdField.innerHTML = `<label for="threshold">Confidence threshold</label>`;
    const thresholdInput = document.createElement('input');
    thresholdInput.type = 'number';
    thresholdInput.id = 'threshold';
    thresholdInput.min = '0'; thresholdInput.max = '1'; thresholdInput.step = '0.05';
    thresholdInput.value = state.options.confidence_threshold;
    thresholdInput.addEventListener('input', () => {
      state.options.confidence_threshold = parseFloat(thresholdInput.value) || 0.7;
    });
    thresholdField.append(thresholdInput);

    const modeField = document.createElement('div');
    modeField.className = 'field';
    modeField.innerHTML = `<label>File operation</label>`;
    const modeRow = document.createElement('div');
    modeRow.className = 'row gap-3';
    const moveBtn = document.createElement('button');
    moveBtn.type = 'button';
    moveBtn.className = 'btn' + (state.options.mode === 'move' ? ' btn--primary' : '');
    moveBtn.textContent = 'Move originals';
    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'btn' + (state.options.mode === 'copy' ? ' btn--primary' : '');
    copyBtn.textContent = 'Copy (keep originals)';
    moveBtn.addEventListener('click', () => {
      state.options.mode = 'move';
      moveBtn.className = 'btn btn--primary';
      copyBtn.className = 'btn';
    });
    copyBtn.addEventListener('click', () => {
      state.options.mode = 'copy';
      copyBtn.className = 'btn btn--primary';
      moveBtn.className = 'btn';
    });
    modeRow.append(moveBtn, copyBtn);
    modeField.append(modeRow);

    const ocrField = document.createElement('div');
    ocrField.className = 'field field--full';
    const ocrLabel = document.createElement('label');
    ocrLabel.className = 'row gap-2';
    const ocrCheck = document.createElement('input');
    ocrCheck.type = 'checkbox';
    ocrCheck.checked = state.options.ocr_enabled;
    ocrCheck.addEventListener('change', () => { state.options.ocr_enabled = ocrCheck.checked; });
    ocrLabel.append(ocrCheck, document.createTextNode('Enable OCR for scanned pages'));
    ocrField.append(ocrLabel);

    form.append(outField, templateField, thresholdField, modeField, ocrField);

    wrap.append(
      document.createElement('div'),
      form,
    );
    wrap.querySelector('div').className = 'screen__head';
    wrap.querySelector('div').innerHTML = `<h2>2. Configure</h2>
      <p class="muted">Set output location, filename template, and sort options.</p>`;

    wrap.api = {
      onEnter: () => {
        outInput.value = state.outputDir;
        templateInput.value = state.options.template;
        thresholdInput.value = state.options.confidence_threshold;
        ocrCheck.checked = state.options.ocr_enabled;
      },
      canAdvance: () => true,
      getData: () => ({
        output_dir: state.outputDir,
        options: { ...state.options },
      }),
    };
    return wrap;
  };

  /* ------------------------------------------------------------------ */
  /* Step 3: Preview/Monitor                                             */
  /* ------------------------------------------------------------------ */
  Screens.preview = function () {
    const wrap = document.createElement('div');
    wrap.className = 'screen';

    const head = document.createElement('div');
    head.className = 'screen__head';
    head.innerHTML = `<h2>3. Preview &amp; apply</h2>
      <p class="muted">Review the detected matches before applying.</p>`;

    const progress = Components.jobProgress({});
    const countsRow = progress.querySelector('.counts');

    // Action buttons
    const actions = document.createElement('div');
    actions.className = 'row gap-2 mt-3';

    const pauseBtn = document.createElement('button');
    pauseBtn.className = 'btn';
    pauseBtn.textContent = 'Pause';
    pauseBtn.addEventListener('click', async () => {
      if (!state.currentJob) return;
      try {
        await API.jobs.pause(state.currentJob.id);
        pauseBtn.disabled = true;
        resumeBtn.disabled = false;
      } catch (e) { UI.toast('Failed to pause: ' + e.message, 'error'); }
    });

    const resumeBtn = document.createElement('button');
    resumeBtn.className = 'btn';
    resumeBtn.textContent = 'Resume';
    resumeBtn.disabled = true;
    resumeBtn.addEventListener('click', async () => {
      if (!state.currentJob) return;
      try {
        await API.jobs.resume(state.currentJob.id);
        resumeBtn.disabled = true;
        pauseBtn.disabled = false;
      } catch (e) { UI.toast('Failed to resume: ' + e.message, 'error'); }
    });

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn--danger';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', async () => {
      if (!state.currentJob) return;
      const ok = await UI.confirm('Cancel this run? No files will be moved.', { okText: 'Cancel run', danger: true });
      if (!ok) return;
      try {
        await API.jobs.cancel(state.currentJob.id);
        UI.toast('Run cancelled', 'warning');
      } catch (e) { UI.toast('Failed to cancel: ' + e.message, 'error'); }
    });

    const applyBtn = document.createElement('button');
    applyBtn.className = 'btn btn--primary btn--lg hidden';
    applyBtn.textContent = 'Apply matched';
    applyBtn.addEventListener('click', async () => {
      if (!state.currentJob) return;
      const matched = state.currentJob.items.filter((i) => i.status === 'matched').length;
      const ok = await UI.confirm(`Apply ${matched} matched files? This will ${state.options.mode || 'move'} originals.`, { okText: 'Apply', danger: state.options.mode === 'move' });
      if (!ok) return;
      try {
        await API.jobs.apply(state.currentJob.id);
        UI.toast('Applying matched files...', 'info');
      } catch (e) { UI.toast('Failed to apply: ' + e.message, 'error'); }
    });

    actions.append(pauseBtn, resumeBtn, cancelBtn, applyBtn);

    // Log list
    const logList = Components.logList();

    wrap.append(head, progress, actions, document.createElement('h4'), logList);
    wrap.querySelector('h4').className = 'mt-4 mb-2';
    wrap.querySelector('h4').textContent = 'Live log';

    let wsHandle = null;

    wrap.api = {
      onEnter: async () => {
        if (state.currentJob) return;
        // create the job from stored data
        const jobData = {
          name: 'Run ' + new Date().toLocaleString(),
          subdirs: state.selected,
          output_dir: state.outputDir,
          options: { ...state.options },
        };
        try {
          const job = await API.jobs.create(jobData);
          state.currentJob = job;
          state.currentJob.items = [];
          // connect events
          wsHandle = API.events(job.id, {
            onJob: (j) => {
              if (j.status === 'preview_ready' || j.status === 'completed') {
                applyBtn.classList.remove('hidden');
              }
              progress.api.update(j);
            },
            onLog: (entry) => logList.api.append(entry),
          });
          // poll items for the table
          pollItems(job.id);
        } catch (e) {
          UI.toast('Failed to start preview: ' + e.message, 'error');
          if (e.status === 401) window.dispatchEvent(new CustomEvent('auth-error'));
        }
      },
      onLeave: () => {
        if (wsHandle) wsHandle.close();
      },
      canAdvance: () => {
        return state.currentJob && (state.currentJob.status === 'preview_ready' || state.currentJob.status === 'completed');
      },
      getData: () => ({ job: state.currentJob }),
    };

    async function pollItems(jobId) {
      try {
        const data = await API.jobs.items(jobId);
        if (data.items) {
          state.currentJob.items = state.currentJob.items || [];
          for (const item of data.items) {
            const existing = state.currentJob.items.find((i) => i.id === item.id);
            if (existing) Object.assign(existing, item);
            else state.currentJob.items.push(item);
          }
        }
      } catch (e) { /* swallow */ }
      if (wrap.api._active) setTimeout(() => pollItems(jobId), 2000);
    }

    wrap.api._active = false;
    const origEnter = wrap.api.onEnter;
    wrap.api.onEnter = async (...args) => {
      wrap.api._active = true;
      await origEnter(...args);
    };
    const origLeave = wrap.api.onLeave;
    wrap.api.onLeave = () => {
      wrap.api._active = false;
      origLeave();
    };

    return wrap;
  };

  /* ------------------------------------------------------------------ */
  /* Step 4: Review / redo                                                */
  /* ------------------------------------------------------------------ */
  Screens.review = function () {
    const wrap = document.createElement('div');
    wrap.className = 'screen';

    const head = document.createElement('div');
    head.className = 'screen__head';
    head.innerHTML = `<h2>4. Review &amp; redo</h2>
      <p class="muted">Fix uncertain or errored items before they're sorted.</p>`;

    // Filter bar
    const filterBar = document.createElement('div');
    filterBar.className = 'filter-bar';
    const statuses = ['uncertain', 'error', 'corrupt', 'matched', 'moved'];
    statuses.forEach((s) => {
      const btn = document.createElement('button');
      btn.className = 'btn btn--sm' + (s === state.reviewFilter ? ' btn--primary' : '');
      btn.textContent = s;
      btn.addEventListener('click', () => {
        state.reviewFilter = s;
        filterBar.querySelectorAll('.button, .btn').forEach((b) => b.classList.remove('btn--primary'));
        btn.classList.add('btn--primary');
        renderItems();
      });
      filterBar.append(btn);
    });

    const itemList = document.createElement('div');
    itemList.className = 'item-list';

    wrap.append(head, filterBar, itemList);

    async function renderItems() {
      itemList.innerHTML = '';
      const jobId = state.currentJob && state.currentJob.id;
      if (!jobId) {
        itemList.innerHTML = '<div class="empty-state"><p>No job yet.</p></div>';
        return;
      }
      try {
        const data = await API.jobs.items(jobId, { status: state.reviewFilter });
        const items = data.items || [];
        if (!items.length) {
          itemList.innerHTML = `<div class="empty-state"><p>No ${state.reviewFilter} items.</p></div>`;
          return;
        }
        for (const item of items) {
          const card = Components.itemCard(item, {
            editable: state.reviewFilter !== 'moved',
            onEdit: () => openEditor(item),
            onApply: async () => {
              try { await API.jobs.applyItem(jobId, item.id); UI.toast('Applied', 'success'); renderItems(); }
              catch (e) { UI.toast(e.message, 'error'); }
            },
            onReset: async () => {
              try { await API.jobs.resetItem(jobId, item.id); UI.toast('Reset', 'info'); renderItems(); }
              catch (e) { UI.toast(e.message, 'error'); }
            },
            onRelookup: async () => {
              try { const r = await API.jobs.relookup(jobId, item.id); UI.toast('Re-lookup done', 'success'); openEditor(r); }
              catch (e) { UI.toast(e.message, 'error'); }
            },
          });
          itemList.append(card);
        }
      } catch (e) {
        if (e.status === 401) { window.dispatchEvent(new CustomEvent('auth-error')); return; }
        itemList.innerHTML = `<p class="muted">Failed to load items: ${e.message}</p>`;
      }
    }

    function openEditor(item) {
      const form = Components.metadataForm(item.meta, {
        onLookup: async () => {
          try {
            const r = await API.jobs.relookup(state.currentJob.id, item.id, form.api.getValues());
            form.api.setValues(r.meta || r);
            UI.toast('Candidates refreshed', 'success');
          } catch (e) { UI.toast(e.message, 'error'); }
        },
      });

      const { close } = UI.modal({
        title: 'Edit metadata',
        content: form,
        width: 480,
      });

      const saveBtn = document.createElement('button');
      saveBtn.className = 'btn btn--primary';
      saveBtn.textContent = 'Save & recompute';
      saveBtn.addEventListener('click', async () => {
        try {
          const updated = await API.jobs.patchItem(state.currentJob.id, item.id, form.api.getValues());
          Object.assign(item, updated);
          UI.toast('Saved', 'success');
          close();
          renderItems();
        } catch (e) { UI.toast(e.message, 'error'); }
      });

      form.append(saveBtn);
    }

    wrap.api = {
      onEnter: renderItems,
      onLeave: () => {},
      canAdvance: () => true,
      getData: () => ({}),
    };
    return wrap;
  };

  window.Screens = Screens;
  window.AppState = state;
})();
