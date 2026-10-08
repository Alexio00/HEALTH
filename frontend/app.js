import { createClient } from "./supabase-client.js";
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./config.js";

const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false
  }
});

const loading = document.querySelector("#loading");
const login = document.querySelector("#login");
const app = document.querySelector("#app");
const view = document.querySelector("#view");
const loginForm = document.querySelector("#login-form");
const loginError = document.querySelector("#login-error");
const logoutButton = document.querySelector("#logout");

const esc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

// Operational timestamps are stored as UTC instants and displayed in Moscow time.
const fmtMskTimestamp = (value) => {
  if (!value) return "";
  const stamp = new Date(value);
  return Number.isNaN(stamp.getTime()) ? String(value) :
    new Intl.DateTimeFormat("ru-RU", {
      timeZone: "Europe/Moscow", day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit", hour12: false
    }).format(stamp);
};

const fmtDate = (value) => {
  if (!value) return "";
  const m = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(value);
};

const recLink = (recordId, label = recordId) =>
  `<a href="#/records/${encodeURIComponent(recordId)}">${esc(label)}</a>`;

const caseLink = (caseKey, label) =>
  `<a href="#/cases/${encodeURIComponent(caseKey)}">${esc(label || caseKey)}</a>`;

function showOnly(target) {
  for (const el of [loading, login, app]) el.classList.add("hidden");
  target.classList.remove("hidden");
}

function empty(label = "Пока нет данных") {
  return `<p class="empty">${esc(label)}</p>`;
}

function list(items, renderItem) {
  if (!items?.length) return empty();
  return `<ul class="cards">${items.map(renderItem).join("")}</ul>`;
}

function chips(items) {
  const values = (items || []).filter(Boolean);
  if (!values.length) return "";
  return `<span class="chips">${values.map(x => `<span class="chip">${esc(x)}</span>`).join("")}</span>`;
}

const tableCell = (html, filterValue = "") => ({
  html,
  filterValue: String(filterValue ?? "")
});

const normalizeFilter = (value) => String(value ?? "").trim().toLocaleLowerCase("ru");
const recordTagFilters = new Set();

const uniqueValues = (values) =>
  [...new Set((values || []).map(x => String(x ?? "").trim()).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "ru", { numeric: true }));

// Shorten only the visible column heading; preserve the full original
// heading in the sorting button's accessible name and in source records.
function formatTableHeader(label) {
  return String(label ?? "").replace(
    /(^|[^\p{L}])количество(?=$|[^\p{L}])/giu,
    "$1К-во"
  );
}

function sortableTable(headers, rows, { id, emptyLabel = "Пока нет данных" } = {}) {
  if (!rows?.length) return empty(emptyLabel);
  if (!id) throw new Error("sortableTable requires a stable id");

  const body = rows.map(rowSpec => {
    const spec = Array.isArray(rowSpec) ? { cells: rowSpec, attrs: {} } : rowSpec;
    const attrs = Object.entries(spec.attrs || {})
      .map(([key, value]) => `${esc(key)}="${esc(value)}"`)
      .join(" ");

    const cells = spec.cells.map(cellSpec => {
      const cell = typeof cellSpec === "object" && cellSpec !== null && "html" in cellSpec
        ? cellSpec
        : tableCell(esc(cellSpec), cellSpec);
      return `<td data-sort-value="${esc(cell.filterValue)}">${cell.html}</td>`;
    }).join("");

    return `<tr ${attrs}>${cells}</tr>`;
  }).join("");

  return `
    <div class="table-wrap">
      <table class="data-table sortable-table" id="${esc(id)}" data-sortable>
        <thead>
          <tr>
            ${headers.map((h, index) => `
              <th>
                <button type="button" class="sort-button" data-column="${index}" aria-label="Сортировать: ${esc(h)}">
                  <span>${esc(formatTableHeader(h))}</span><span class="sort-indicator" aria-hidden="true">↕</span>
                </button>
              </th>
            `).join("")}
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>
    <p class="table-count muted" id="${esc(id)}-count"></p>
  `;
}

function compareSortValues(a, b) {
  const normalizeDate = (value) => {
    const text = String(value ?? "").trim();
    if (/^\d{4}-\d{2}-\d{2}/.test(text)) return text.slice(0, 10);
    const m = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
  };

  const av = String(a ?? "").trim();
  const bv = String(b ?? "").trim();
  const ad = normalizeDate(av);
  const bd = normalizeDate(bv);
  if (ad && bd) return ad.localeCompare(bd);

  const an = Number(av.replace(",", "."));
  const bn = Number(bv.replace(",", "."));
  if (av && bv && Number.isFinite(an) && Number.isFinite(bn)) return an - bn;

  return av.localeCompare(bv, "ru", { numeric: true, sensitivity: "base" });
}

function sortTable(table, column, button) {
  const sameColumn = Number(table.dataset.sortColumn) === column;
  const direction = sameColumn && table.dataset.sortDirection === "asc" ? "desc" : "asc";
  table.dataset.sortColumn = String(column);
  table.dataset.sortDirection = direction;

  const rows = [...table.tBodies[0].rows];
  rows.sort((a, b) => {
    const av = a.cells[column]?.dataset.sortValue || a.cells[column]?.textContent || "";
    const bv = b.cells[column]?.dataset.sortValue || b.cells[column]?.textContent || "";
    const cmp = compareSortValues(av, bv);
    return direction === "asc" ? cmp : -cmp;
  });
  rows.forEach(row => table.tBodies[0].appendChild(row));

  table.querySelectorAll(".sort-button").forEach(item => {
    const indicator = item.querySelector(".sort-indicator");
    const active = item === button;
    item.classList.toggle("active", active);
    if (indicator) indicator.textContent = active ? (direction === "asc" ? "↑" : "↓") : "↕";
  });
}

function updateTableCount(table) {
  if (!table) return;
  const rows = [...table.tBodies[0].rows];
  const visible = rows.filter(row => !row.hidden).length;
  const count = document.querySelector(`#${CSS.escape(table.id)}-count`);
  if (count) count.textContent = `Показано: ${visible} из ${rows.length}`;
}

// A table with overflow-x:auto cannot use CSS sticky <th> relative to the
// page viewport: the overflow wrapper becomes the sticky scroll container.
// A synchronized, fixed header copy provides both vertical pinning and normal
// horizontal scrolling without changing the source table or its sorting.
let pinnedHeaders = [];
let stickyFrame = 0;
let stickyChromeObserver = null;

function clearPinnedHeaders() {
  for (const entry of pinnedHeaders) entry.floating.remove();
  pinnedHeaders = [];
}

function stickyOffsets() {
  const topbar = document.querySelector(".topbar");
  const title = view.querySelector(":scope > h1");
  const filter = view.querySelector(".filter-bar[data-sticky-filter]");
  const headerHeight = Math.ceil(topbar?.getBoundingClientRect().height || 0);
  const titleHeight = Math.ceil(title?.getBoundingClientRect().height || 0);
  const filterHeight = Math.ceil(filter?.getBoundingClientRect().height || 0);
  return { headerHeight, titleHeight, filterHeight, tableTop: headerHeight + titleHeight + filterHeight };
}

function shouldPinTableHeader(head, wrapper, offset, viewportHeight) {
  return head.height > 0
    && head.bottom <= offset
    && wrapper.bottom > offset + head.height
    && wrapper.width > 0
    && offset + head.height < viewportHeight;
}

function updatePinnedHeaders() {
  const offset = stickyOffsets().tableTop;
  for (const entry of pinnedHeaders) {
    const { table, wrapper, floating, cloneTable } = entry;
    if (!wrapper.isConnected || !table.tHead) {
      floating.hidden = true;
      continue;
    }
    const rect = wrapper.getBoundingClientRect();
    const head = table.tHead.getBoundingClientRect();
    const show = shouldPinTableHeader(head, rect, offset, window.innerHeight);
    if (!show) {
      floating.hidden = true;
      continue;
    }
    const width = table.getBoundingClientRect().width;
    cloneTable.style.width = `${width}px`;
    cloneTable.style.minWidth = `${width}px`;
    const sourceCells = table.tHead.rows[0]?.cells || [];
    const cloneCells = cloneTable.tHead.rows[0]?.cells || [];
    for (let i = 0; i < sourceCells.length; i++) {
      const size = sourceCells[i].getBoundingClientRect().width;
      cloneCells[i].style.width = `${size}px`;
      cloneCells[i].style.minWidth = `${size}px`;
      cloneCells[i].style.maxWidth = `${size}px`;
      const originalIndicator = sourceCells[i].querySelector(".sort-indicator");
      const copyIndicator = cloneCells[i].querySelector(".sort-indicator");
      if (originalIndicator && copyIndicator) copyIndicator.textContent = originalIndicator.textContent;
      const originalButton = sourceCells[i].querySelector(".sort-button");
      const copyButton = cloneCells[i].querySelector(".sort-button");
      if (originalButton && copyButton) copyButton.classList.toggle("active", originalButton.classList.contains("active"));
    }
    floating.style.top = `${offset}px`;
    floating.style.left = `${rect.left}px`;
    floating.style.width = `${rect.width}px`;
    floating.style.height = `${head.height}px`;
    cloneTable.style.marginLeft = `${-wrapper.scrollLeft}px`;
    floating.hidden = false;
  }
}
function queuePinnedHeaderUpdate() {
  if (stickyFrame) return;
  stickyFrame = requestAnimationFrame(() => {
    stickyFrame = 0;
    updatePinnedHeaders();
  });
}
function setupStickyChrome() {
  stickyChromeObserver?.disconnect();
  const topbar = document.querySelector(".topbar");
  const title = view.querySelector(":scope > h1");
  const filter = view.querySelector(".filter-bar[data-sticky-filter]");
  const sync = () => {
    const { headerHeight, titleHeight } = stickyOffsets();
    document.documentElement.style.setProperty("--topbar-height", `${headerHeight}px`);
    document.documentElement.style.setProperty("--page-title-height", `${titleHeight}px`);
    queuePinnedHeaderUpdate();
  };
  if (typeof ResizeObserver !== "undefined") {
    stickyChromeObserver = new ResizeObserver(sync);
    for (const el of [topbar, title, filter]) if (el) stickyChromeObserver.observe(el);
  }
  sync();
}
function bindSortableTables() {
  document.querySelectorAll("table[data-sortable]").forEach(table => {
    table.querySelectorAll(".sort-button").forEach(button => {
      button.addEventListener("click", () => {
        sortTable(table, Number(button.dataset.column), button);
        queuePinnedHeaderUpdate();
      });
    });
    updateTableCount(table);
    const wrapper = table.closest(".table-wrap");
    if (!wrapper || !table.tHead) return;
    const floating = document.createElement("div");
    floating.className = "pinned-table-header";
    floating.hidden = true;
    const cloneTable = document.createElement("table");
    cloneTable.className = "data-table sortable-table";
    cloneTable.style.tableLayout = "fixed";
    cloneTable.appendChild(table.tHead.cloneNode(true));
    floating.appendChild(cloneTable);
    document.body.appendChild(floating);
    floating.addEventListener("click", event => {
      const copy = event.target.closest(".sort-button");
      if (!copy) return;
      const original = table.tHead.querySelector(`.sort-button[data-column="${copy.dataset.column}"]`);
      original?.click();
    });
    wrapper.addEventListener("scroll", queuePinnedHeaderUpdate, { passive: true });
    pinnedHeaders.push({ table, wrapper, floating, cloneTable });
  });
  queuePinnedHeaderUpdate();
}
window.addEventListener("scroll", queuePinnedHeaderUpdate, { passive: true });
window.addEventListener("resize", () => {
  const topbar = document.querySelector(".topbar");
  if (topbar && view.querySelector(":scope > h1")) setupStickyChrome();
});

const filterableTable = sortableTable;
const bindFilterableTables = bindSortableTables;

function compactSelect(label, id, values, allLabel = "Все") {
  const unique = uniqueValues(values);
  if (unique.length <= 1) return "";
  return `
    <label>
      ${esc(label)}
      <select id="${esc(id)}">
        <option value="">${esc(allLabel)}</option>
        ${unique.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join("")}
      </select>
    </label>
  `;
}

function bindAttributeFilters(tableId, specs) {
  const table = document.querySelector(`#${CSS.escape(tableId)}`);
  if (!table) return;

  const apply = () => {
    [...table.tBodies[0].rows].forEach(row => {
      row.hidden = specs.some(spec => {
        const control = document.querySelector(`#${CSS.escape(spec.id)}`);
        const wanted = normalizeFilter(control?.value || "");
        if (!wanted) return false;
        return normalizeFilter(row.dataset[spec.attr] || "") !== wanted;
      });
    });
    updateTableCount(table);
  };

  specs.forEach(spec => document.querySelector(`#${CSS.escape(spec.id)}`)?.addEventListener("change", apply));
  apply();
}

function renderActiveRecordTags() {
  const holder = document.querySelector("#records-active-tags");
  if (!holder) return;

  holder.innerHTML = [...recordTagFilters].map(tag => `
    <button type="button" class="active-filter-tag" data-remove-tag="${esc(tag)}" title="Убрать тег из фильтра">
      ${esc(tag)} ×
    </button>
  `).join("");

  holder.querySelectorAll("[data-remove-tag]").forEach(button => {
    button.addEventListener("click", () => {
      recordTagFilters.delete(button.dataset.removeTag);
      renderActiveRecordTags();
      applyRecordFilters();
    });
  });
}

function addRecordTagFilter(tag) {
  const value = String(tag || "").trim();
  if (!value) return;
  recordTagFilters.add(value);
  renderActiveRecordTags();
  applyRecordFilters();
}

function applyRecordFilters() {
  const table = document.querySelector("#records-index");
  if (!table) return;

  const dateFrom = document.querySelector("#records-date-from")?.value || "";
  const dateTo = document.querySelector("#records-date-to")?.value || "";
  const recordType = normalizeFilter(document.querySelector("#records-record-type")?.value || "");
  const confidence = normalizeFilter(document.querySelector("#records-confidence")?.value || "");

  [...table.tBodies[0].rows].forEach(row => {
    const rowDate = row.dataset.recordDate || "";
    const rowTags = (row.dataset.tags || "").split("||").filter(Boolean);
    const tagsOk = [...recordTagFilters].every(tag => rowTags.includes(normalizeFilter(tag)));
    const dateOk = (!dateFrom || !rowDate || rowDate >= dateFrom) && (!dateTo || !rowDate || rowDate <= dateTo);
    const typeOk = !recordType || normalizeFilter(row.dataset.recordType) === recordType;
    const confidenceOk = !confidence || normalizeFilter(row.dataset.confidence) === confidence;
    row.hidden = !(tagsOk && dateOk && typeOk && confidenceOk);
  });
  updateTableCount(table);
}

function setupRecordFilters(initialTags = []) {
  recordTagFilters.clear();
  initialTags.filter(Boolean).forEach(tag => recordTagFilters.add(tag));
  renderActiveRecordTags();

  ["#records-date-from", "#records-date-to"].forEach(id => {
    document.querySelector(id)?.addEventListener("input", applyRecordFilters);
  });
  ["#records-record-type", "#records-confidence"].forEach(id => {
    document.querySelector(id)?.addEventListener("change", applyRecordFilters);
  });

  const tagSelect = document.querySelector("#records-tag-filter");
  tagSelect?.addEventListener("change", () => {
    if (tagSelect.value) addRecordTagFilter(tagSelect.value);
    tagSelect.value = "";
  });

  document.querySelectorAll(".tag-filter-button").forEach(button => {
    button.addEventListener("click", () => addRecordTagFilter(button.dataset.tag));
  });

  applyRecordFilters();
}

async function assertReader(userId) {
  const { data, error } = await supabase
    .from("app_readers")
    .select("user_id")
    .eq("user_id", userId)
    .maybeSingle();

  if (error) throw error;
  return Boolean(data?.user_id);
}

async function enterApp(session) {
  const allowed = await assertReader(session.user.id);
  if (!allowed) {
    await supabase.auth.signOut();
    throw new Error("Этот аккаунт не разрешён для HEALTH.");
  }
  showOnly(app);
  await route();
}

async function boot() {
  const { data, error } = await supabase.auth.getSession();
  if (error) {
    showOnly(login);
    loginError.textContent = error.message;
    return;
  }
  if (!data.session) {
    showOnly(login);
    return;
  }

  try {
    await enterApp(data.session);
  } catch (error) {
    showOnly(login);
    loginError.textContent = error.message || "Не удалось проверить доступ.";
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  const email = document.querySelector("#email").value.trim();
  const password = document.querySelector("#password").value;

  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    loginError.textContent = "Не удалось войти.";
    return;
  }

  try {
    await enterApp(data.session);
  } catch (err) {
    loginError.textContent = err.message || "Доступ запрещён.";
    showOnly(login);
  }
});

logoutButton.addEventListener("click", async () => {
  clearPinnedHeaders();
  await supabase.auth.signOut();
  location.hash = "#/";
  showOnly(login);
});

const mobileMenu = document.querySelector("#primary-nav");
const menuToggle = document.querySelector("#menu-toggle");

function closeMobileMenu() {
  mobileMenu?.classList.remove("is-open");
  menuToggle?.setAttribute("aria-expanded", "false");
  menuToggle?.setAttribute("aria-label", "Открыть меню");
}
menuToggle?.addEventListener("click", () => {
  const opened = mobileMenu.classList.toggle("is-open");
  menuToggle.setAttribute("aria-expanded", String(opened));
  menuToggle.setAttribute("aria-label", opened ? "Закрыть меню" : "Открыть меню");
});
mobileMenu?.addEventListener("click", event => {
  if (event.target.closest("a")) closeMobileMenu();
});
window.addEventListener("hashchange", () => {
  closeMobileMenu();
  if (!app.classList.contains("hidden")) route();
});

async function route() {
  clearPinnedHeaders();
  const raw = location.hash.startsWith("#/") ? location.hash.slice(2) : location.hash.replace(/^#/, "");
  const [pathPart, queryString = ""] = raw.split("?");
  const parts = pathPart.split("/").filter(Boolean);
  const params = new URLSearchParams(queryString);
  view.innerHTML = '<p class="muted">Загрузка…</p>';

  try {
    if (parts.length === 0) {
      await renderCurrentState();
    } else if (["chronic", "open-cases", "medications", "monitoring", "visit-preparation", "future-plan"].includes(parts[0])) {
      await renderCurrentState(parts[0]);
    } else if (parts[0] === "vaccination") {
      view.innerHTML = '<h1>Вакцинация</h1><p class="empty">Раздел пока не заполнен</p>';
    } else if (parts[0] === "closed-cases") {
      await renderClosedCases();
    } else if (parts[0] === "cases" && parts[1]) {
      await renderCase(decodeURIComponent(parts[1]));
    } else if (parts[0] === "records" && parts.length === 1) {
      await renderRecords({ initialTags: params.getAll("tag") });
    } else if (parts[0] === "records" && parts[1]) {
      await renderRecord(decodeURIComponent(parts[1]));
    } else {
      view.innerHTML = "<h1>Не найдено</h1>";
    }
  } catch (error) {
    console.error(error);
    view.innerHTML = '<h1>Ошибка</h1><p class="error">Не удалось загрузить данные.</p>';
  }
  setupStickyChrome();
}

async function fetchCaseBundles(cases) {
  if (!cases?.length) return [];

  const caseKeys = cases.map(x => x.case_key);
  const { data: links, error: linksError } = await supabase
    .from("case_links")
    .select("case_key,record_id,relation,relation_date,note")
    .in("case_key", caseKeys)
    .order("relation_date", { ascending: true, nullsFirst: true });

  if (linksError) throw linksError;

  const recordIds = [...new Set([
    ...cases.flatMap(x => [x.opening_record_id, x.closing_record_id].filter(Boolean)),
    ...(links || []).map(x => x.record_id)
  ])];

  let records = [];
  if (recordIds.length) {
    const result = await supabase
      .from("records")
      .select("record_id,record_date,title,summary,body_text")
      .in("record_id", recordIds);
    if (result.error) throw result.error;
    records = result.data || [];
  }

  const recordMap = new Map(records.map(r => [r.record_id, r]));
  const linksByCase = new Map();
  for (const link of links || []) {
    const bucket = linksByCase.get(link.case_key) || [];
    bucket.push(link);
    linksByCase.set(link.case_key, bucket);
  }

  return cases.map(c => ({
    ...c,
    links: linksByCase.get(c.case_key) || [],
    opening_record: recordMap.get(c.opening_record_id) || null,
    closing_record: c.closing_record_id ? recordMap.get(c.closing_record_id) || null : null,
    record_map: recordMap
  }));
}

function caseDetails(item, { closed = false, open = false } = {}) {
  const startDate = item.opening_record?.record_date || item.metadata?.start_date || "";
  const endDate = item.closing_record?.record_date || item.metadata?.end_date || "";
  const linked = item.links.map(link => {
    const r = item.record_map.get(link.record_id);
    const date = link.relation_date || r?.record_date || "";
    return `
      <li>
        <span class="relation">${esc(link.relation)}</span>
        ${recLink(link.record_id, r ? recordDisplayTitle(r) : link.record_id)}
        ${date ? `<span class="muted"> · ${esc(fmtDate(date))}</span>` : ""}
        ${r?.title ? `<span> · ${esc(r.title)}</span>` : ""}
        ${link.note ? `<p class="muted">${esc(link.note)}</p>` : ""}
      </li>
    `;
  }).join("");

  const dateSuffix = closed && endDate ? ` <span class="summary-date">· закрыт ${esc(fmtDate(endDate))}</span>` : "";

  return `
    <details class="case-card" data-category="${esc(item.category || "")}" data-end-date="${esc(item.closing_record?.record_date || item.metadata?.end_date || "")}" ${open ? "open" : ""}>
      <summary><strong>${esc(item.title)}</strong>${dateSuffix}</summary>
      <div class="case-body">
        ${item.summary ? `<p class="lead-small">${esc(item.summary)}</p>` : ""}
        <dl class="meta-list">
          <dt>Категория</dt><dd>${esc(item.category === "chronic" ? "Хроническое состояние" : "Случай / эпизод")}</dd>
          <dt>Начало</dt><dd>${esc(fmtDate(startDate))}</dd>
          ${closed ? `<dt>Закрыт</dt><dd>${esc(fmtDate(endDate))}</dd>` : ""}
          <dt>Открывающая REC</dt><dd>${recLink(item.opening_record_id)}</dd>
          ${item.closing_record_id ? `<dt>Закрывающая REC</dt><dd>${recLink(item.closing_record_id)}</dd>` : ""}
        </dl>
        <h3>Все REC</h3>
        ${linked ? `<ul class="rec-links">${linked}</ul>` : empty("Связанные REC пока не импортированы")}
      </div>
    </details>
  `;
}


function questionDetails(item) {
  const meta = item.metadata || {};
  const created = meta.created_date || "";
  const note = meta.note || "";
  const related = Array.isArray(meta.source_record_ids) ? meta.source_record_ids : [];

  return `
    <details class="case-card question-card">
      <summary><strong>${esc(item.question)}</strong></summary>
      <div class="case-body">
        <dl class="meta-list">
          <dt>Статус</dt><dd>Открыт</dd>
          ${created ? `<dt>Создан</dt><dd>${esc(created)}</dd>` : ""}
          ${item.basis_record_id ? `<dt>Основание REC</dt><dd>${recLink(item.basis_record_id)}</dd>` : ""}
        </dl>
        ${note ? `<p class="lead-small">${esc(note)}</p>` : ""}
        ${related.length ? `
          <h3>Связанные REC</h3>
          <p class="rec-inline">${related.map(id => recLink(id)).join(", ")}</p>
        ` : ""}
      </div>
    </details>
  `;
}


const specialtyLabels = [
  ["эндокринолог", "эндокринологу"],
  ["кардиолог", "кардиологу"],
  ["терапевт", "терапевту"],
  ["лор", "лору"],
  ["отоларинголог", "лору"],
  ["хирург", "хирургу"],
  ["ортопед", "ортопеду"],
  ["гастроэнтеролог", "гастроэнтерологу"],
  ["невролог", "неврологу"],
  ["инфекционист", "инфекционисту"],
  ["стоматолог", "стоматологу"],
  ["уролог", "урологу"],
  ["психиатр", "психиатру"],
  ["дерматолог", "дерматологу"],
  ["ревматолог", "ревматологу"],
  ["аллерголог", "аллергологу"],
  ["онколог", "онкологу"],
  ["гинеколог", "гинекологу"]
];
const visitLabel = specialty => specialtyLabels.find(x => x[0] === specialty)?.[1] || "специалисту";

// Only an explicit specialist prefix in a question or an explicit visit plan
// is sufficient. Do not infer specialty from the medical history or drug names.
function namedSpecialties(text) {
  const value = String(text || "").toLocaleLowerCase("ru");
  const found = specialtyLabels.filter(([stem]) => value.includes(stem)).map(([stem]) =>
    stem === "отоларинголог" ? "лор" : stem
  );
  return [...new Set(found)];
}
function questionSpecialties(question) {
  const meta = question.metadata || {};
  if (Array.isArray(meta.visit_specialties) && meta.visit_specialties.length) {
    return meta.visit_specialties.map(x => String(x).toLocaleLowerCase("ru"))
      .filter(x => specialtyLabels.some(([stem]) => stem === x));
  }
  const prefix = String(question.question || "").split(":")[0];
  return prefix.length <= 95 ? namedSpecialties(prefix) : [];
}
function isMedicalCardQuestion(question) {
  return ["medical_card", "chart"].includes(question.metadata?.category)
    || question.metadata?.purpose === "medical_card";
}
function visitPreparation(planItems, questions) {
  const plannedGroups = [];
  const unmatchedGroups = new Map();
  for (const item of planItems || []) {
    const kind = String(item.metadata?.kind || "").toLocaleLowerCase("ru");
    if (!kind.includes("визит") && !kind.includes("консультаци")) continue;
    const prefix = String(item.title || "").split(":")[0];
    const specialties = prefix.length <= 100 ? namedSpecialties(prefix) : [];
    plannedGroups.push({
      specialty: specialties,
      title: specialties.length ? `Визит к ${specialties.map(visitLabel).join(" и ")}` : "Визит к специалисту",
      visits: [item], questions: [], planItemId: item.plan_item_id
    });
  }
  const unmatched = specialty => {
    if (!unmatchedGroups.has(specialty)) {
      unmatchedGroups.set(specialty, {
        specialty: [specialty],
        title: specialty === "специалист"
          ? "Вопросы к специалисту — специальность не указана"
          : `Вопросы к ${visitLabel(specialty)} — визит не запланирован`,
        visits: [], questions: []
      });
    }
    return unmatchedGroups.get(specialty);
  };
  for (const question of questions || []) {
    if (isMedicalCardQuestion(question)) continue;
    const specialties = questionSpecialties(question);
    if (!specialties.length) {
      unmatched("специалист").questions.push(question);
      continue;
    }
    // A question can belong to more than one explicit planned visit.
    // Show it only once within each visit, even if two specialties match.
    const matched = new Set();
    for (const specialty of specialties) {
      let found = false;
      for (const group of plannedGroups) {
        if (!group.specialty.includes(specialty)) continue;
        if (!matched.has(group)) {
          group.questions.push(question);
          matched.add(group);
        }
        found = true;
      }
      if (!found) unmatched(specialty).questions.push(question);
    }
  }
  const all = [...plannedGroups, ...unmatchedGroups.values()];
  if (!all.length) return empty("Плановых визитов и вопросов специалистам пока нет");
  return all.map(group => {
    const planNotes = group.visits.map(item => {
      const due = item.metadata?.due_text || fmtDate(item.due_on) || "Срок не указан";
      return `<li><strong>${esc(due)}</strong> · ${esc(item.title)}
        ${item.basis_record_id ? ` · ${recLink(item.basis_record_id)}` : ""}</li>`;
    }).join("");
    return `
      <details class="case-card visit-card" ${group.planItemId ? `data-plan-id="${esc(group.planItemId)}"` : ""}>
        <summary><strong>${esc(group.title)}</strong>
          <span class="muted"> · вопросов: ${group.questions.length}</span></summary>
        <div class="case-body">
          ${planNotes ? `<h3>Плановый визит</h3><ul class="record-list">${planNotes}</ul>` :
            '<p class="muted">Связанный пункт будущего плана пока не найден</p>'}
          <h3>Вопросы к специалисту</h3>
          ${group.questions.length ? group.questions.map(questionDetails).join("") :
            empty("Вопросы пока не добавлены")}
        </div>
      </details>`;
  }).join("");
}

async function renderCurrentState(mode = "all") {
  const [cases, meds, monitoring, plan, questions] = await Promise.all([
    supabase.from("cases").select("case_key,title,summary,status,category,opening_record_id,closing_record_id,metadata").eq("status","open").order("title"),
    supabase.from("medications").select("medication_id,name,dose,schedule,status,basis_record_id").eq("status","active").order("name"),
    supabase.from("monitoring").select("monitoring_id,title,cadence_text,status,basis_record_id").eq("status","active").order("title"),
    supabase.from("plan_items").select("plan_item_id,title,due_on,status,basis_record_id,metadata").eq("status","planned").order("due_on",{ascending:true,nullsFirst:false}),
    supabase.from("questions").select("question_id,question,status,basis_record_id,metadata").eq("status","open").order("question_id")
  ]);

  for (const result of [cases, meds, monitoring, plan, questions]) {
    if (result.error) throw result.error;
  }

  const bundled = await fetchCaseBundles(cases.data || []);
  const medicalQuestions = (questions.data || []).filter(isMedicalCardQuestion);
  const chronic = bundled.filter(x => x.category === "chronic");
  const episodes = bundled.filter(x => x.category !== "chronic");

  const medsRows = (meds.data || []).map(x => [
    tableCell(`<strong>${esc(x.name)}</strong>`, x.name),
    tableCell(esc(x.dose || ""), x.dose || ""),
    tableCell(esc(x.schedule || ""), x.schedule || ""),
    tableCell(x.basis_record_id ? recLink(x.basis_record_id) : "", x.basis_record_id || "")
  ]);

  const monitoringRows = (monitoring.data || []).map(x => [
    tableCell(`<strong>${esc(x.title)}</strong>`, x.title),
    tableCell(esc(x.cadence_text || ""), x.cadence_text || ""),
    tableCell(x.basis_record_id ? recLink(x.basis_record_id) : "", x.basis_record_id || "")
  ]);

  const planRows = (plan.data || []).map(x => {
    const due = x.metadata?.due_text || fmtDate(x.due_on) || "";
    const kind = x.metadata?.kind || "";
    const status = x.metadata?.source_status || "запланировано";
    return {
      attrs: { "data-kind": kind, "data-status": status },
      cells: [
        tableCell(esc(due), due),
        tableCell(esc(kind), kind),
        tableCell(esc(x.title), x.title),
        tableCell(esc(status), status),
        tableCell(x.basis_record_id ? recLink(x.basis_record_id) : "", x.basis_record_id || "")
      ]
    };
  });
  const planKinds = uniqueValues((plan.data || []).map(x => x.metadata?.kind || ""));
  const planStatuses = uniqueValues((plan.data || []).map(x => x.metadata?.source_status || "запланировано"));


  const sections = {
    "medical-card": `<section><h2>Вопросы по медкарте</h2>
      ${medicalQuestions.length ? medicalQuestions.map(questionDetails).join("") : empty("Открытых вопросов по медкарте нет")}
    </section>`,
    "chronic": `<section>${mode === "all" ? "<h2>Хронические состояния</h2>" : ""}
      ${chronic.length ? chronic.map(x => caseDetails(x)).join("") : empty()}
    </section>`,
    "open-cases": `<section>${mode === "all" ? "<h2>Открытые случаи</h2>" : ""}
      ${episodes.length ? episodes.map(x => caseDetails(x)).join("") : empty()}
    </section>`,
    "medications": `<section>${mode === "all" ? "<h2>Принимаемые препараты</h2>" : ""}
      ${filterableTable(["Препарат","Дозировка","Режим","REC"], medsRows, { id: "medications-table" })}
    </section>`,
    "monitoring": `<section>${mode === "all" ? "<h2>Мониторинг</h2>" : ""}
      ${filterableTable(["Что контролировать","Периодичность","REC"], monitoringRows, { id: "monitoring-table" })}
    </section>`,
    "visit-preparation": `<section>${mode === "all" ? "<h2>Подготовка к визиту</h2>" : ""}
      ${visitPreparation(plan.data || [], questions.data || [])}
    </section>`,
    "future-plan": `<section>${mode === "all" ? "<h2>Будущий план</h2>" : ""}
      ${planKinds.length > 1 || planStatuses.length > 1 ? `
        <div class="filter-bar" ${mode === "future-plan" ? "data-sticky-filter" : ""} aria-label="Фильтр будущего плана">
          ${compactSelect("Вид", "plan-kind-filter", planKinds)}
          ${compactSelect("Статус", "plan-status-filter", planStatuses)}
        </div>
      ` : ""}
      ${filterableTable(["Срок или условие","Вид","Действие","Статус","REC"], planRows, { id: "future-plan-table" })}
    </section>`
  };
  const sectionNames = {
    "chronic": "Хронические состояния",
    "open-cases": "Открытые случаи",
    "medications": "Принимаемые препараты",
    "monitoring": "Мониторинг",
    "visit-preparation": "Подготовка к визиту",
    "future-plan": "Будущий план"
  };
  const content = mode === "all"
    ? ["medical-card", "chronic", "open-cases", "medications", "monitoring", "visit-preparation", "future-plan"]
      .map(name => sections[name]).join("\n")
    : sections[mode] || empty();
  view.innerHTML = `
    <h1>${esc(sectionNames[mode] || "Текущее состояние")}</h1>
    ${content}
  `;
  bindFilterableTables();
  bindAttributeFilters("future-plan-table", [
    { id: "plan-kind-filter", attr: "kind" },
    { id: "plan-status-filter", attr: "status" }
  ]);
}

async function renderClosedCases() {
  const { data, error } = await supabase
    .from("cases")
    .select("case_key,title,summary,status,category,opening_record_id,closing_record_id,metadata")
    .eq("status","closed")
    .order("title");

  if (error) throw error;

  const bundled = await fetchCaseBundles(data || []);
  bundled.sort((a, b) => {
    const ad = a.closing_record?.record_date || a.metadata?.end_date || "";
    const bd = b.closing_record?.record_date || b.metadata?.end_date || "";
    return bd.localeCompare(ad);
  });

  view.innerHTML = `
    <h1>Закрытые случаи</h1>
    <section class="case-stack" id="closed-case-list">
      ${bundled.length ? bundled.map(x => caseDetails(x, { closed: true })).join("") : empty("Закрытых случаев пока нет")}
    </section>
  `;
}

async function renderCase(caseKey) {
  const { data, error } = await supabase
    .from("cases")
    .select("case_key,title,summary,status,category,opening_record_id,closing_record_id,metadata")
    .eq("case_key", caseKey)
    .single();

  if (error) throw error;

  const [item] = await fetchCaseBundles([data]);
  const backHref = item.status === "closed" ? "#/closed-cases" : "#/";
  const backLabel = item.status === "closed" ? "Закрытые случаи" : "Текущее состояние";

  const rows = item.links.map(link => {
    const r = item.record_map.get(link.record_id);
    const date = fmtDate(link.relation_date || r?.record_date || "");
    return [
      tableCell(`<span class="relation">${esc(link.relation)}</span>`, link.relation),
      tableCell(esc(date), date),
      tableCell(recLink(link.record_id), link.record_id),
      tableCell(esc(r ? recordDisplayTitle(r) : ""), r ? recordDisplayTitle(r) : "")
    ];
  });

  view.innerHTML = `
    <p><a href="${backHref}">← ${esc(backLabel)}</a></p>
    <h1>${esc(item.title)}</h1>
    <p class="status-line">${chips([
      item.category === "chronic" ? "Хроническое состояние" : "Случай / эпизод",
      item.status === "closed" ? "Закрыт" : "Открыт"
    ])}</p>
    ${item.summary ? `<p class="lead">${esc(item.summary)}</p>` : ""}
    <dl>
      <dt>ID случая</dt><dd class="mono">${esc(item.case_key)}</dd>
      <dt>Начало</dt><dd>${esc(fmtDate(item.opening_record?.record_date || item.metadata?.start_date || ""))} · ${recLink(item.opening_record_id)}</dd>
      ${item.closing_record_id ? `<dt>Закрытие</dt><dd>${esc(fmtDate(item.closing_record?.record_date || item.metadata?.end_date || ""))} · ${recLink(item.closing_record_id)}</dd>` : ""}
    </dl>
    <section>
      <h2>Хронология REC</h2>
      ${filterableTable(["Связь","Дата","REC","Запись"], rows, { id: "case-chronology-table" })}
    </section>
  `;
  bindFilterableTables();
}

async function renderRecords({ initialTags = [] } = {}) {
  const [{ data: records, error: recordsError }, { data: links, error: linksError }, { data: cases, error: casesError }] = await Promise.all([
    supabase
      .from("records")
      .select("record_id,record_date,title,type,record_type,confidence,status,tags,summary")
      .order("record_date", { ascending: false })
      .limit(500),
    supabase
      .from("case_links")
      .select("case_key,record_id,relation"),
    supabase
      .from("cases")
      .select("case_key,title,status")
  ]);

  if (recordsError) throw recordsError;
  if (linksError) throw linksError;
  if (casesError) throw casesError;

  const caseMap = new Map((cases || []).map(x => [x.case_key, x]));
  const linksByRecord = new Map();
  for (const link of links || []) {
    const bucket = linksByRecord.get(link.record_id) || [];
    bucket.push(link);
    linksByRecord.set(link.record_id, bucket);
  }

  const allTags = [...new Set((records || []).flatMap(r => r.tags || []))].sort((a, b) => a.localeCompare(b, "ru"));
  const recordTypes = uniqueValues((records || []).map(r => r.record_type || r.type || ""));
  const confidences = uniqueValues((records || []).map(r => r.confidence || ""));

  const rows = (records || []).map(r => {
    const caseCell = (linksByRecord.get(r.record_id) || []).map(link => {
      const c = caseMap.get(link.case_key);
      return `<div><span class="relation">${esc(link.relation)}</span> ${caseLink(link.case_key, c?.title || link.case_key)}</div>`;
    }).join("");

    const tagHtml = (r.tags || []).map(tag => `
      <button type="button" class="chip tag-filter-button" data-tag="${esc(tag)}" title="Фильтровать по тегу ${esc(tag)}">
        ${esc(tag)}
      </button>
    `).join("");

    return {
      attrs: {
        "data-record-date": r.record_date || "",
        "data-tags": (r.tags || []).map(normalizeFilter).join("||"),
        "data-record-type": r.record_type || r.type || "",
        "data-confidence": r.confidence || ""
      },
      cells: [
        tableCell(recLink(r.record_id), r.record_id),
        tableCell(esc(fmtDate(r.record_date)), fmtDate(r.record_date)),
        tableCell(`<span class="chips">${tagHtml}</span>`, (r.tags || []).join(" ")),
        tableCell(esc(r.record_type || r.type || ""), r.record_type || r.type || ""),
        tableCell(esc(r.confidence || ""), r.confidence || ""),
        tableCell(esc(r.summary || r.title || ""), r.summary || r.title || ""),
        tableCell(caseCell, (linksByRecord.get(r.record_id) || []).map(link => {
          const c = caseMap.get(link.case_key);
          return `${link.relation} ${c?.title || link.case_key}`;
        }).join(" "))
      ]
    };
  });

  view.innerHTML = `
    <h1>Записи</h1>
    <div class="filter-bar" data-sticky-filter aria-label="Фильтр записей">
      <label>Дата от<input id="records-date-from" type="date"></label>
      <label>Дата до<input id="records-date-to" type="date"></label>
      <label>Тег
        <select id="records-tag-filter">
          <option value="">Все</option>
          ${allTags.map(tag => `<option value="${esc(tag)}">${esc(tag)}</option>`).join("")}
        </select>
      </label>
      ${compactSelect("Тип записи", "records-record-type", recordTypes)}
      ${compactSelect("Подтверждение", "records-confidence", confidences)}
      <div class="active-filter-block">
        <span class="filter-bar-label">Активные теги</span>
        <div id="records-active-tags" class="active-filter-tags"></div>
      </div>
    </div>
    ${filterableTable(["REC","Дата","Домен / теги","Тип записи","Подтверждение","Кратко","Кейс"], rows, { id: "records-index" })}
  `;
  bindFilterableTables();
  setupRecordFilters(initialTags);
}

let inlineTableSequence = 0;

const recordTagLink = (tag) =>
  `<a class="chip record-tag-link" href="#/records?tag=${encodeURIComponent(tag)}">${esc(tag)}</a>`;

function cleanLegacyRecordText(text) {
  let value = String(text || "").trim();

  // Remove legacy migration wrappers such as:
  // ===== REC ... =====, ===== BEGIN FILE: ... =====, ===== END FILE ... =====.
  value = value
    .split(/\r?\n/)
    .filter(line => !/^=+\s*(?:BEGIN\s+FILE:|END\s+FILE:|REC\b|END\s+REC\b).*?=+\s*$/i.test(line.trim()))
    .join("\n")
    .trim();

  // Remove YAML/frontmatter when it is explicitly delimited.
  if (value.startsWith("---")) {
    const second = value.indexOf("\n---", 3);
    if (second >= 0) value = value.slice(second + 4).trim();
  }

  // Some historical volumes contain flattened metadata without --- delimiters.
  // If a medical H1 follows a metadata-looking prefix, keep the H1 and drop only
  // the duplicated technical prefix. recordDisplayTitle() still uses this H1;
  // renderRecordBody() removes the repeated H1 from the visible body.
  const lines = value.split(/\r?\n/);
  const firstH1 = lines.findIndex(line => /^#\s+\S/.test(line.trim()));
  if (firstH1 > 0) {
    const prefix = lines.slice(0, firstH1).join("\n");
    const looksLikeMetadata = /(?:^|\n|\s)(?:type|record_id|date|tags|record_type|confidence|status|source|source_file|source_sha256|source_pages)\s*:/i.test(prefix);
    if (looksLikeMetadata) value = lines.slice(firstH1).join("\n").trim();
  }

  return value;
}

function recordDisplayTitle(record) {
  const cleaned = cleanLegacyRecordText(record.body_text);
  const heading = cleaned.match(/^#\s+(.+)$/m)?.[1]?.trim();
  if (heading && /[А-Яа-яЁё]/.test(heading)) return heading;

  const summary = String(record.summary || "").trim();
  if (summary && /[А-Яа-яЁё]/.test(summary)) {
    const first = summary.split(/[.;]/)[0].trim();
    if (first) return first.charAt(0).toUpperCase() + first.slice(1);
  }

  const fallback = String(record.title || "Запись").replace(/[-_]+/g, " ").trim();
  return fallback.charAt(0).toUpperCase() + fallback.slice(1);
}

function inlineRecordMarkdown(value) {
  let html = esc(value);
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\`([^\`]+)\`/g, "<code>$1</code>");
  html = html.replace(/\[(REC-\d{8}-\d{3})\]/g, (_, id) => recLink(id));
  return html;
}

function parseMarkdownTableRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(x => x.trim());
}

// This is a presentation-only transform. The source body_text remains intact.
function readableRecordParagraphs(lines) {
  const text = lines.join(" ").trim();
  if (!text) return "";
  if (text.length < 450) return `<p>${inlineRecordMarkdown(text)}</p>`;
  // Split long prose at clear sentence boundaries; never alter stored medical text.
  const sentences = text.split(/(?<=[.!?…])\s+(?=[А-ЯЁA-Z])/u);
  if (sentences.length < 3) return `<p>${inlineRecordMarkdown(text)}</p>`;
  const paragraphs = [];
  let group = "";
  for (const sentence of sentences) {
    if (group && group.length + sentence.length > 330) {
      paragraphs.push(group);
      group = "";
    }
    group += (group ? " " : "") + sentence;
  }
  if (group) paragraphs.push(group);
  return paragraphs.map(value => `<p>${inlineRecordMarkdown(value)}</p>`).join("\n");
}

function renderRecordBody(text) {
  const cleaned = cleanLegacyRecordText(text);
  const lines = cleaned.split(/\r?\n/);
  if (lines[0]?.startsWith("# ")) lines.shift();

  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();

    if (!line || /^---+$/.test(line)) {
      i += 1;
      continue;
    }

    if (line.startsWith("|") && i + 1 < lines.length && /^\|?\s*:?-+/.test(lines[i + 1].trim())) {
      const headers = parseMarkdownTableRow(lines[i]);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const cells = parseMarkdownTableRow(lines[i]);
        rows.push(cells.map(cell => tableCell(inlineRecordMarkdown(cell), cell.replace(/\*\*/g, ""))));
        i += 1;
      }
      blocks.push(sortableTable(headers, rows, { id: `record-inline-table-${++inlineTableSequence}` }));
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      const level = Math.min(4, heading[1].length + 1);
      blocks.push(`<h${level}>${inlineRecordMarkdown(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (/^-\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^-\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^-\s+/, ""));
        i += 1;
      }
      blocks.push(`<ul class="record-list">${items.map(item => `<li>${inlineRecordMarkdown(item)}</li>`).join("")}</ul>`);
      continue;
    }

    const paragraph = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,4})\s+/.test(lines[i].trim()) &&
      !/^-\s+/.test(lines[i].trim()) &&
      !lines[i].trim().startsWith("|") &&
      !/^---+$/.test(lines[i].trim())
    ) {
      paragraph.push(lines[i].trim());
      i += 1;
    }
    blocks.push(readableRecordParagraphs(paragraph));
  }

  return blocks.join("\n");
}

async function renderRecord(recordId) {
  const [{ data: record, error: recordError }, { data: sourceLinks, error: sourceLinksError }, { data: caseLinks, error: caseLinksError }] = await Promise.all([
    supabase.from("records").select("*").eq("record_id", recordId).single(),
    supabase.from("record_sources").select("source_id,role,source_pages").eq("record_id", recordId),
    supabase.from("case_links").select("case_key,relation,relation_date").eq("record_id", recordId)
  ]);

  if (recordError) throw recordError;
  if (sourceLinksError) throw sourceLinksError;
  if (caseLinksError) throw caseLinksError;

  let relatedCases = [];
  if (caseLinks?.length) {
    const keys = [...new Set(caseLinks.map(x => x.case_key))];
    const result = await supabase.from("cases").select("case_key,title,status").in("case_key", keys);
    if (result.error) throw result.error;
    const map = new Map((result.data || []).map(x => [x.case_key, x]));
    relatedCases = caseLinks.map(link => ({ ...link, case: map.get(link.case_key) }));
  }

  let sourceViews = [];
  if (sourceLinks?.length) {
    const ids = [...new Set(sourceLinks.map(x => x.source_id))];
    const [sourceResult, locationResult] = await Promise.all([
      supabase.from("sources").select("source_id,original_filename").in("source_id", ids),
      supabase.from("source_locations").select("source_id,provider,provider_object_id,location_role").in("source_id", ids)
    ]);
    if (sourceResult.error) throw sourceResult.error;
    if (locationResult.error) throw locationResult.error;

    const sourceMap = new Map((sourceResult.data || []).map(x => [x.source_id, x]));
    sourceViews = sourceLinks.map(link => {
      const locations = (locationResult.data || []).filter(x => x.source_id === link.source_id);
      const preferred = locations.find(x => x.location_role === "PRIMARY" && x.provider === "google-drive")
        || locations.find(x => x.provider === "google-drive");
      return { ...link, source: sourceMap.get(link.source_id), location: preferred };
    });
  }

  inlineTableSequence = 0;
  const title = recordDisplayTitle(record);
  const body = renderRecordBody(record.body_text);
  const tags = (record.tags || []).map(recordTagLink).join("");

  view.innerHTML = `
    <p><a href="#/records">← Записи</a></p>
    <h1>${esc(title)}</h1>

    <dl class="record-meta">
      <dt>Дата</dt><dd>${esc(fmtDate(record.record_date))}</dd>
      <dt>ID записи</dt><dd class="mono">${esc(record.record_id)}</dd>
      <dt>Тип записи</dt><dd>${esc(record.record_type || "")}</dd>
      <dt>Подтверждение</dt><dd>${esc(record.confidence || "")}</dd>
    </dl>

    ${tags ? `<div class="record-tags" aria-label="Теги">${tags}</div>` : ""}
    ${record.summary ? `<p class="lead">${esc(record.summary)}</p>` : ""}

    <section>
      <h2>Связанные случаи</h2>
      ${relatedCases.length ? list(relatedCases, x => `
        <li>
          <span class="relation">${esc(x.relation)}</span>
          ${caseLink(x.case_key, x.case?.title || x.case_key)}
          ${x.case?.status ? `<span class="muted"> · ${esc(x.case.status === "closed" ? "закрыт" : "открыт")}</span>` : ""}
        </li>
      `) : empty()}
    </section>

    <section>
      <h2>Текст записи</h2>
      <article class="record-body rich-record-body">${body}</article>
    </section>

    <section>
      <h2>Источники</h2>
      ${sourceViews.length ? list(sourceViews, item => {
        const driveId = item.location?.provider_object_id;
        const href = driveId ? `https://drive.google.com/open?id=${encodeURIComponent(driveId)}` : "";
        return `
          <li>
            ${href
              ? `<a href="${href}" target="_blank" rel="noopener noreferrer"><strong>Открыть оригинал</strong></a>`
              : `<strong>${esc(item.source?.original_filename || "Оригинал")}</strong>`}
            ${record.source_label ? `<p>${esc(record.source_label)}</p>` : ""}
            ${item.source_pages ? `<p class="muted">Страницы в источнике: ${esc(item.source_pages)}</p>` : ""}
          </li>
        `;
      }) : empty("Источники не привязаны")}
    </section>
  `;

  bindSortableTables();
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
}

boot();
