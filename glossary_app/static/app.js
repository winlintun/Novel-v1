// Glossary Review — frontend logic. Vanilla JS, no framework.

const state = {
  novelId: null,
  filters: {
    status: "pending",
    category: "",
    minConfidence: 0,
    search: "",
    sort: "confidence_desc",
  },
  selected: new Set(),
  expanded: new Set(),
  terms: [],
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function toast(message, kind = "info") {
  const colors = {
    info: "bg-slate-800",
    ok: "bg-emerald-600",
    err: "bg-rose-600",
  };
  const t = el("div", {
    class: `${colors[kind]} text-white text-sm rounded-lg shadow-lg px-4 py-2 max-w-xs`
  }, message);
  $("#toast-container").appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

const Api = {
  listNovels: () => api("/api/novels"),
  listTerms: (params) => {
    const q = new URLSearchParams(params).toString();
    return api(`/api/terms?${q}`);
  },
  termDetail: (id) => api(`/api/terms/${encodeURIComponent(id)}`),
  approve: (id) => api(`/api/terms/${id}/approve`, { method: "POST" }),
  reject: (id) => api(`/api/terms/${id}/reject`, { method: "POST" }),
  edit: (id, body) => api(`/api/terms/${id}/edit`, {
    method: "POST",
    body: JSON.stringify(body),
  }),
  addVariant: (id, text) => api(`/api/terms/${id}/variants`, {
    method: "POST",
    body: JSON.stringify({ variant_text: text }),
  }),
  deleteVariant: (vid) => api(`/api/variants/${vid}`, { method: "DELETE" }),
  bulkApprove: (ids) => api(`/api/bulk/approve`, {
    method: "POST",
    body: JSON.stringify({ term_ids: ids }),
  }),
  stats: (novelId) => api(`/api/stats/${novelId}`),
};

function statusBadge(status) {
  const colors = {
    pending: "bg-amber-100 text-amber-800",
    approved: "bg-emerald-100 text-emerald-800",
    rejected: "bg-rose-100 text-rose-800",
  };
  return el("span", {
    class: `${colors[status] || "bg-slate-200"} text-xs px-2 py-0.5 rounded-full font-medium`
  }, status);
}

function confidenceBar(conf) {
  const pct = Math.round(conf * 100);
  const color = conf >= 0.8 ? "bg-emerald-500"
              : conf >= 0.5 ? "bg-amber-500"
              : "bg-rose-500";
  return el("div", { class: "flex items-center gap-2" },
    el("div", { class: "w-20 h-2 bg-slate-200 rounded overflow-hidden" },
      el("div", { class: `h-full ${color}`, style: `width: ${pct}%` })
    ),
    el("span", { class: "text-xs text-slate-500 tabular-nums w-10" }, conf.toFixed(2))
  );
}

function renderTermCard(t) {
  const isExpanded = state.expanded.has(t.id);
  const isChecked = state.selected.has(t.id);

  const card = el("div", {
    class: "bg-white rounded-lg shadow-sm hover:shadow border border-slate-200 transition",
    dataset: { termId: t.id }
  });

  const header = el("div", {
    class: "flex items-center gap-3 px-4 py-3 cursor-pointer",
    onClick: (e) => {
      if (e.target.closest("input, button")) return;
      toggleExpanded(t.id);
    }
  });

  const cb = el("input", {
    type: "checkbox",
    class: "w-4 h-4 rounded border-slate-300",
    onChange: (e) => {
      if (e.target.checked) state.selected.add(t.id);
      else state.selected.delete(t.id);
      updateBulkButton();
    }
  });
  if (isChecked) cb.checked = true;
  if (t.status !== "pending") cb.disabled = true;
  header.appendChild(cb);

  header.appendChild(
    el("div", { class: "flex-1 min-w-0" },
      el("div", { class: "flex items-center gap-2 flex-wrap" },
        el("span", { class: "font-medium text-slate-900" }, t.source_term),
        el("span", { class: "text-slate-400" }, "\u2192"),
        el("span", { class: "font-medium text-slate-900" }, t.target_term)
      ),
      el("div", { class: "text-xs text-slate-500 mt-0.5" },
        `${t.category} \u00b7 used ${t.usage_count}\u00d7`
      )
    )
  );

  header.appendChild(confidenceBar(t.confidence));
  header.appendChild(statusBadge(t.status));

  header.appendChild(
    el("span", { class: "text-slate-400 text-sm select-none" },
      isExpanded ? "\u25bc" : "\u25b6")
  );

  card.appendChild(header);

  if (isExpanded) {
    card.appendChild(renderDetailPanel(t));
  }

  return card;
}

function renderDetailPanel(t) {
  const panel = el("div", {
    class: "border-t border-slate-200 px-4 py-4 bg-slate-50 space-y-4"
  });

  const editRow = el("div", { class: "grid grid-cols-1 md:grid-cols-3 gap-3" });

  const targetInput = el("input", {
    type: "text", value: t.target_term,
    class: "border border-slate-300 rounded px-2 py-1 text-sm"
  });
  editRow.appendChild(
    el("label", { class: "text-xs text-slate-500" },
      el("div", { class: "mb-1" }, "Target (Burmese)"),
      targetInput
    )
  );

  const catSelect = el("select", {
    class: "border border-slate-300 rounded px-2 py-1 text-sm"
  });
  ["character","location","organization","technique","cultivation_concept",
   "item_artifact","title_honorific","power_level","general"].forEach(c => {
    const opt = el("option", { value: c }, c);
    if (c === t.category) opt.selected = true;
    catSelect.appendChild(opt);
  });
  editRow.appendChild(
    el("label", { class: "text-xs text-slate-500" },
      el("div", { class: "mb-1" }, "Category"),
      catSelect
    )
  );

  editRow.appendChild(
    el("div", { class: "flex items-end" },
      el("button", {
        class: "bg-blue-600 hover:bg-blue-500 text-white text-sm rounded px-3 py-1.5",
        onClick: async () => {
          try {
            await Api.edit(t.id, {
              target_term: targetInput.value,
              category: catSelect.value,
            });
            toast("Saved", "ok");
            refresh();
          } catch (e) { toast(e.message, "err"); }
        }
      }, "Save changes")
    )
  );

  panel.appendChild(editRow);

  const variantsBox = el("div", {});
  variantsBox.appendChild(
    el("h3", { class: "text-xs font-semibold text-slate-600 uppercase mb-2" }, "Variants")
  );
  loadVariants(t.id, variantsBox);
  panel.appendChild(variantsBox);

  const usageBox = el("div", {});
  usageBox.appendChild(
    el("h3", { class: "text-xs font-semibold text-slate-600 uppercase mb-2" }, "Usage samples")
  );
  loadUsage(t.id, usageBox);
  panel.appendChild(usageBox);

  panel.appendChild(
    el("div", { class: "flex gap-2 pt-2 border-t border-slate-200" },
      el("button", {
        class: "bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded px-4 py-1.5",
        onClick: async () => {
          try { await Api.approve(t.id); toast("Approved", "ok"); refresh(); }
          catch (e) { toast(e.message, "err"); }
        }
      }, "Approve"),
      el("button", {
        class: "bg-rose-600 hover:bg-rose-500 text-white text-sm rounded px-4 py-1.5",
        onClick: async () => {
          if (!confirm("Reject this term?")) return;
          try { await Api.reject(t.id); toast("Rejected", "ok"); refresh(); }
          catch (e) { toast(e.message, "err"); }
        }
      }, "Reject")
    )
  );

  return panel;
}

async function loadVariants(termId, container) {
  try {
    const data = await Api.termDetail(termId);
    const list = el("div", { class: "space-y-1" });
    for (const v of data.variants) {
      list.appendChild(
        el("div", { class: "flex items-center gap-2 text-sm" },
          el("span", { class: "bg-white border border-slate-200 rounded px-2 py-0.5" },
            v.variant_text),
          el("button", {
            class: "text-rose-600 hover:text-rose-800 text-xs",
            onClick: async () => {
              try { await Api.deleteVariant(v.id); refresh(); }
              catch (e) { toast(e.message, "err"); }
            }
          }, "\u2715")
        )
      );
    }
    const input = el("input", {
      type: "text", placeholder: "Add variant\u2026",
      class: "border border-slate-300 rounded px-2 py-1 text-sm flex-1"
    });
    list.appendChild(
      el("div", { class: "flex gap-2 mt-2" },
        input,
        el("button", {
          class: "bg-slate-700 hover:bg-slate-600 text-white text-sm rounded px-3",
          onClick: async () => {
            if (!input.value.trim()) return;
            try {
              await Api.addVariant(termId, input.value.trim());
              input.value = "";
              refresh();
            } catch (e) { toast(e.message, "err"); }
          }
        }, "Add")
      )
    );
    container.appendChild(list);
  } catch (e) {
    container.appendChild(
      el("div", { class: "text-xs text-rose-600" }, e.message)
    );
  }
}

async function loadUsage(termId, container) {
  try {
    const data = await Api.termDetail(termId);
    if (!data.usage.length) {
      container.appendChild(
        el("div", { class: "text-xs text-slate-400" }, "No usage records")
      );
      return;
    }
    const list = el("div", { class: "space-y-2" });
    for (const u of data.usage.slice(0, 5)) {
      list.appendChild(
        el("div", { class: "text-xs bg-white border border-slate-200 rounded p-2" },
          el("div", { class: "text-slate-500 mb-1" },
            `Chapter ${u.chapter_id || "?"} \u00b7 paragraph ${u.paragraph_idx}`),
          el("div", { class: "text-slate-700 italic" },
            (u.context_snippet || "").slice(0, 200))
        )
      );
    }
    container.appendChild(list);
  } catch (e) {
    container.appendChild(
      el("div", { class: "text-xs text-rose-600" }, e.message)
    );
  }
}

function toggleExpanded(termId) {
  if (state.expanded.has(termId)) state.expanded.delete(termId);
  else state.expanded.add(termId);
  render();
}

function updateBulkButton() {
  const btn = $("#bulk-approve-btn");
  btn.disabled = state.selected.size === 0;
  btn.textContent = state.selected.size
    ? `Approve ${state.selected.size} selected`
    : "Bulk approve selected";
}

function render() {
  const list = $("#terms-list");
  list.innerHTML = "";
  if (!state.terms.length) {
    $("#empty-state").classList.remove("hidden");
  } else {
    $("#empty-state").classList.add("hidden");
    for (const t of state.terms) {
      list.appendChild(renderTermCard(t));
    }
  }
  $("#terms-count").textContent = state.terms.length;
}

async function loadTerms() {
  if (!state.novelId) return;
  $("#loading").classList.remove("hidden");
  try {
    const data = await Api.listTerms({
      novel_id: state.novelId,
      status: state.filters.status,
      category: state.filters.category,
      min_confidence: state.filters.minConfidence,
      q: state.filters.search,
      sort: state.filters.sort,
      limit: 200,
    });
    state.terms = data.terms;
    render();
  } catch (e) {
    toast(e.message, "err");
  } finally {
    $("#loading").classList.add("hidden");
  }
}

async function loadStats() {
  if (!state.novelId) return;
  try {
    const s = await Api.stats(state.novelId);
    const panel = $("#stats-panel");
    panel.innerHTML = "";
    const o = s.overall;
    panel.appendChild(
      el("div", { class: "flex justify-between" },
        el("span", { class: "text-slate-500" }, "Total"),
        el("span", { class: "font-medium" }, String(o.total || 0)))
    );
    panel.appendChild(
      el("div", { class: "flex justify-between" },
        el("span", { class: "text-amber-700" }, "Pending"),
        el("span", { class: "font-medium" }, String(o.pending || 0)))
    );
    panel.appendChild(
      el("div", { class: "flex justify-between" },
        el("span", { class: "text-emerald-700" }, "Approved"),
        el("span", { class: "font-medium" }, String(o.approved || 0)))
    );
    panel.appendChild(
      el("div", { class: "flex justify-between" },
        el("span", { class: "text-rose-700" }, "Rejected"),
        el("span", { class: "font-medium" }, String(o.rejected || 0)))
    );
  } catch (e) { /* silent */ }
}

function refresh() {
  loadTerms();
  loadStats();
}

async function init() {
  try {
    const novels = await Api.listNovels();
    const sel = $("#novel-select");
    sel.innerHTML = "";
    for (const n of novels) {
      const opt = el("option", { value: n.id },
        `${n.name} (${n.pending_count || 0} pending)`);
      sel.appendChild(opt);
    }
    if (novels.length) {
      state.novelId = novels[0].id;
      sel.value = state.novelId;
      refresh();
    }
    sel.addEventListener("change", (e) => {
      state.novelId = e.target.value;
      state.selected.clear();
      state.expanded.clear();
      updateBulkButton();
      refresh();
    });
  } catch (e) {
    toast("Failed to load novels: " + e.message, "err");
  }

  $("#filter-status").addEventListener("change", (e) => {
    state.filters.status = e.target.value;
    loadTerms();
  });
  $("#filter-category").addEventListener("change", (e) => {
    state.filters.category = e.target.value;
    loadTerms();
  });
  $("#filter-confidence").addEventListener("input", (e) => {
    state.filters.minConfidence = parseFloat(e.target.value);
    $("#conf-label").textContent = state.filters.minConfidence.toFixed(2);
  });
  $("#filter-confidence").addEventListener("change", loadTerms);
  $("#filter-search").addEventListener("input", debounce((e) => {
    state.filters.search = e.target.value;
    loadTerms();
  }, 300));
  $("#filter-sort").addEventListener("change", (e) => {
    state.filters.sort = e.target.value;
    loadTerms();
  });

  $("#refresh-btn").addEventListener("click", refresh);

  $("#bulk-approve-btn").addEventListener("click", async () => {
    if (!state.selected.size) return;
    if (!confirm(`Approve ${state.selected.size} terms?`)) return;
    try {
      const r = await Api.bulkApprove([...state.selected]);
      toast(`Approved ${r.count}`, "ok");
      state.selected.clear();
      updateBulkButton();
      refresh();
    } catch (e) { toast(e.message, "err"); }
  });
}

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

init();
