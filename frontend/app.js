import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.2/+esm";
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

function filterableTable(headers, rows, { id, emptyLabel = "Пока нет данных" } = {}) {
  if (!rows?.length) return empty(emptyLabel);
  if (!id) throw new Error("filterableTable requires a stable id");

  const body = rows.map(rowSpec => {
    const spec = Array.isArray(rowSpec) ? { cells: rowSpec, attrs: {} } : rowSpec;
    const attrs = Object.entries(spec.attrs || {})
      .map(([key, value]) => `${esc(key)}="${esc(value)}"`)
      .join(" ");

    const cells = spec.cells.map(cellSpec => {
      const cell = typeof cellSpec === "object" && cellSpec !== null && "html" in cellSpec
        ? cellSpec
        : tableCell(esc(cellSpec), cellSpec);
      return `<td data-filter-value="${esc(cell.filterValue)}">${cell.html}</td>`;
    }).join("");

    return `<tr ${attrs}>${cells}</tr>`;
  }).join("");

  return `
    <div class="table-wrap">
      <table class="data-table" id="${esc(id)}" data-filterable>
        <thead>
          <tr>${headers.map(h => `<th>${esc(h)}</th>`).join("")}</tr>
          <tr class="column-filters">
            ${headers.map((h, index) => `
              <th>
                <input type="search"
                  class="column-filter"
                  data-column="${index}"
                  placeholder="Фильтр"
                  aria-label="Фильтр: ${esc(h)}"
                  autocomplete="off">
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

function applyTableFilters(table) {
  if (!table) return;

  const columnFilters = [...table.querySelectorAll(".column-filter")].map(input => ({
    column: Number(input.dataset.column),
    value: normalizeFilter(input.value)
  }));

  const dateFrom = table.id === "records-index" ? document.querySelector("#records-date-from")?.value || "" : "";
  const dateTo = table.id === "records-index" ? document.querySelector("#records-date-to")?.value || "" : "";

  let visible = 0;
  const rows = [...table.tBodies[0].rows];

  for (const row of rows) {
    const columnMatch = columnFilters.every(filter => {
      if (!filter.value) return true;
      const cell = row.cells[filter.column];
      return normalizeFilter(cell?.dataset.filterValue || cell?.textContent).includes(filter.value);
    });

    let globalMatch = true;
    if (table.id === "records-index") {
      const rowDate = row.dataset.recordDate || "";
      if (dateFrom && rowDate && rowDate < dateFrom) globalMatch = false;
      if (dateTo && rowDate && rowDate > dateTo) globalMatch = false;

      const rowTags = (row.dataset.tags || "").split("||").filter(Boolean);
      if ([...recordTagFilters].some(tag => !rowTags.includes(normalizeFilter(tag)))) {
        globalMatch = false;
      }
    }

    row.hidden = !(columnMatch && globalMatch);
    if (!row.hidden) visible += 1;
  }

  const count = document.querySelector(`#${CSS.escape(table.id)}-count`);
  if (count) count.textContent = `Показано: ${visible} из ${rows.length}`;
}

function bindFilterableTables() {
  document.querySelectorAll("table[data-filterable]").forEach(table => {
    table.querySelectorAll(".column-filter").forEach(input => {
      input.addEventListener("input", () => applyTableFilters(table));
    });
    applyTableFilters(table);
  });
}

function renderActiveRecordTags() {
  const holder = document.querySelector("#records-active-tags");
  if (!holder) return;

  holder.innerHTML = [...recordTagFilters].map(tag => `
    <button type="button" class="active-filter-tag" data-remove-tag="${esc(tag)}" title="Убрать фильтр">
      ${esc(tag)} ×
    </button>
  `).join("");

  holder.querySelectorAll("[data-remove-tag]").forEach(button => {
    button.addEventListener("click", () => {
      recordTagFilters.delete(button.dataset.removeTag);
      renderActiveRecordTags();
      applyTableFilters(document.querySelector("#records-index"));
    });
  });
}

function addRecordTagFilter(tag) {
  const value = String(tag || "").trim();
  if (!value) return;
  recordTagFilters.add(value);
  renderActiveRecordTags();
  applyTableFilters(document.querySelector("#records-index"));
}

function setupRecordFilters() {
  const table = document.querySelector("#records-index");
  if (!table) return;

  recordTagFilters.clear();
  renderActiveRecordTags();

  for (const id of ["#records-date-from", "#records-date-to"]) {
    document.querySelector(id)?.addEventListener("input", () => applyTableFilters(table));
  }

  const tagSelect = document.querySelector("#records-tag-filter");
  tagSelect?.addEventListener("change", () => {
    if (tagSelect.value) addRecordTagFilter(tagSelect.value);
    tagSelect.value = "";
  });

  document.querySelectorAll(".tag-filter-button").forEach(button => {
    button.addEventListener("click", () => addRecordTagFilter(button.dataset.tag));
  });
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
  await supabase.auth.signOut();
  location.hash = "#/";
  showOnly(login);
});

window.addEventListener("hashchange", () => {
  if (!app.classList.contains("hidden")) route();
});

async function route() {
  const parts = (location.hash.replace(/^#\/?/, "") || "").split("/").filter(Boolean);
  view.innerHTML = '<p class="muted">Загрузка…</p>';

  try {
    if (parts.length === 0) return renderCurrentState();
    if (parts[0] === "closed-cases") return renderClosedCases();
    if (parts[0] === "cases" && parts[1]) return renderCase(decodeURIComponent(parts[1]));
    if (parts[0] === "records" && parts.length === 1) return renderRecords();
    if (parts[0] === "records" && parts[1]) return renderRecord(decodeURIComponent(parts[1]));
    if (parts[0] === "sources" && parts[1]) return renderSource(decodeURIComponent(parts[1]));
    view.innerHTML = "<h1>Не найдено</h1>";
  } catch (error) {
    console.error(error);
    view.innerHTML = '<h1>Ошибка</h1><p class="error">Не удалось загрузить данные.</p>';
  }
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
      .select("record_id,record_date,title")
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
        ${recLink(link.record_id)}
        ${date ? `<span class="muted"> · ${esc(fmtDate(date))}</span>` : ""}
        ${r?.title ? `<span> · ${esc(r.title)}</span>` : ""}
        ${link.note ? `<p class="muted">${esc(link.note)}</p>` : ""}
      </li>
    `;
  }).join("");

  const dateSuffix = closed && endDate ? ` <span class="summary-date">· закрыт ${esc(fmtDate(endDate))}</span>` : "";

  return `
    <details class="case-card" ${open ? "open" : ""}>
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
        <p class="case-action">${caseLink(item.case_key, "Открыть карточку случая →")}</p>
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

async function renderCurrentState() {
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
    return [
      tableCell(esc(due), due),
      tableCell(esc(kind), kind),
      tableCell(esc(x.title), x.title),
      tableCell(esc(status), status),
      tableCell(x.basis_record_id ? recLink(x.basis_record_id) : "", x.basis_record_id || "")
    ];
  });

  view.innerHTML = `
    <h1>Текущее состояние</h1>
    <p class="intro">Актуальное состояние, открытые случаи, препараты, мониторинг и будущий план. Каждая медицинская деталь должна прослеживаться до REC.</p>

    <section>
      <h2>Вопросы по медкарте</h2>
      ${questions.data?.length ? questions.data.map(questionDetails).join("") : empty("Открытых вопросов нет")}
    </section>

    <section>
      <h2>Хронические состояния</h2>
      ${chronic.length ? chronic.map(x => caseDetails(x)).join("") : empty()}
    </section>

    <section>
      <h2>Открытые случаи</h2>
      ${episodes.length ? episodes.map(x => caseDetails(x)).join("") : empty()}
    </section>

    <section>
      <h2>Текущие лекарственные средства</h2>
      ${filterableTable(["Препарат","Дозировка","Режим","REC"], medsRows, { id: "medications-table" })}
    </section>

    <section>
      <h2>Мониторинг</h2>
      ${filterableTable(["Что контролировать","Периодичность","REC"], monitoringRows, { id: "monitoring-table" })}
    </section>

    <section>
      <h2>Будущий план</h2>
      ${filterableTable(["Срок или условие","Вид","Действие","Статус","REC"], planRows, { id: "future-plan-table" })}
    </section>
  `;
  bindFilterableTables();
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
    <p class="intro">Завершённые клинические случаи. Внутри каждой карточки — начало, закрывающая REC и полная импортированная цепочка связей.</p>
    <section class="case-stack">
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
      tableCell(esc(r?.title || ""), r?.title || "")
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
      <dt>Case key</dt><dd class="mono">${esc(item.case_key)}</dd>
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

async function renderRecords() {
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
        "data-tags": (r.tags || []).map(normalizeFilter).join("||")
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
    <p class="intro">Индекс REC. Структура повторяет старый HealthDB: кликабельная REC, дата, домены/теги, тип, достоверность, краткое содержание и связь со случаем.</p>
    <div class="global-filters" aria-label="Общие фильтры записей">
      <label>
        Дата от
        <input id="records-date-from" type="date">
      </label>
      <label>
        Дата до
        <input id="records-date-to" type="date">
      </label>
      <label>
        Добавить тег
        <select id="records-tag-filter">
          <option value="">Без фильтра</option>
          ${allTags.map(tag => `<option value="${esc(tag)}">${esc(tag)}</option>`).join("")}
        </select>
      </label>
      <div class="active-filter-block">
        <span class="muted">Активные теги</span>
        <div id="records-active-tags" class="active-filter-tags"></div>
      </div>
    </div>
    ${filterableTable(["REC","Дата","Домен / теги","Тип записи","Достоверность","Кратко","Кейс"], rows, { id: "records-index" })}
  `;
  bindFilterableTables();
  setupRecordFilters();
}

async function renderRecord(recordId) {
  const [{ data: record, error: recordError }, { data: sources, error: sourcesError }, { data: caseLinks, error: caseLinksError }] = await Promise.all([
    supabase.from("records").select("*").eq("record_id", recordId).single(),
    supabase.from("record_sources").select("source_id,role,source_pages").eq("record_id", recordId),
    supabase.from("case_links").select("case_key,relation,relation_date").eq("record_id", recordId)
  ]);

  if (recordError) throw recordError;
  if (sourcesError) throw sourcesError;
  if (caseLinksError) throw caseLinksError;

  let relatedCases = [];
  if (caseLinks?.length) {
    const keys = [...new Set(caseLinks.map(x => x.case_key))];
    const result = await supabase.from("cases").select("case_key,title,status").in("case_key", keys);
    if (result.error) throw result.error;
    const map = new Map((result.data || []).map(x => [x.case_key, x]));
    relatedCases = caseLinks.map(link => ({ ...link, case: map.get(link.case_key) }));
  }

  view.innerHTML = `
    <p><a href="#/records">← Записи</a></p>
    <h1>${esc(record.title)}</h1>
    <p class="muted">${esc(fmtDate(record.record_date))} · ${esc(record.record_id)}</p>
    <p class="status-line">${chips([...(record.tags || []), record.record_type, record.confidence].filter(Boolean))}</p>
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
      <article class="record-body">${esc(record.body_text)}</article>
    </section>

    <section>
      <h2>Источники</h2>
      ${list(sources, x => `<li><a href="#/sources/${encodeURIComponent(x.source_id)}">${esc(x.source_id)}</a><p class="muted">${esc(x.role)} ${esc(x.source_pages || "")}</p></li>`)}
    </section>
  `;
}

async function renderSource(sourceId) {
  const [{ data: source, error: sourceError }, { data: locations, error: locError }] = await Promise.all([
    supabase.from("sources").select("source_id,logical_path,original_filename,mime_type,size_bytes,source_date,sha256").eq("source_id", sourceId).single(),
    supabase.from("source_locations").select("provider,account_alias,provider_object_id,location_role,verified_at").eq("source_id", sourceId).order("location_role")
  ]);

  if (sourceError) throw sourceError;
  if (locError) throw locError;

  const locationHtml = list(locations, x => {
    const isDrive = x.provider === "google-drive" && x.provider_object_id;
    const href = isDrive ? `https://drive.google.com/open?id=${encodeURIComponent(x.provider_object_id)}` : null;
    return `<li><strong>${esc(x.location_role)}</strong> · ${esc(x.provider)} · ${esc(x.account_alias)}
      ${href ? `<p><a href="${href}" target="_blank" rel="noopener noreferrer">Открыть оригинал в Google Drive</a></p>` : ""}
    </li>`;
  });

  view.innerHTML = `
    <p><button class="link-button" type="button" id="back">← Назад</button></p>
    <h1>${esc(source.original_filename)}</h1>
    <dl>
      <dt>ID</dt><dd>${esc(source.source_id)}</dd>
      <dt>Дата</dt><dd>${esc(fmtDate(source.source_date || ""))}</dd>
      <dt>MIME</dt><dd>${esc(source.mime_type || "")}</dd>
      <dt>Размер</dt><dd>${esc(source.size_bytes ?? "")}</dd>
      <dt>SHA-256</dt><dd class="mono">${esc(source.sha256 || "")}</dd>
    </dl>
    <h2>Хранилища</h2>
    ${locationHtml}
  `;

  document.querySelector("#back")?.addEventListener("click", () => history.back());
}

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
}

boot();
