import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const js = readFileSync("frontend/app.js", "utf8");
const html = readFileSync("frontend/index.html", "utf8");
const css = readFileSync("frontend/styles.css", "utf8");
const fakeEl = {
  addEventListener() {}, setAttribute() {}, getAttribute() { return ""; },
  classList: { add() {}, remove() {}, toggle() { return true; }, contains() { return false; } },
  querySelectorAll() { return []; },
  querySelector() { return null; },
  textContent: "", innerHTML: ""
};
const context = vm.createContext({
  createClient() { return { auth: {} }; },
  SUPABASE_URL: "", SUPABASE_PUBLISHABLE_KEY: "",
  document: { querySelector() { return fakeEl; }, querySelectorAll() { return []; } },
  window: { addEventListener() {} },
  navigator: {}, location: { hash: "" },
  URLSearchParams, Date, Intl, Set, Map, console,
  CSS: { escape(x) { return x; } }
});
const harness = js.replace(/^import .*;\s*$/gm, "").replace(/\nboot\(\);\s*$/, "");
vm.runInContext(harness + "\n globalThis.expose = { visitPreparation, isMedicalCardQuestion, questionSpecialties, renderRecordBody, recordDisplayTitle, fmtMskTimestamp, formatTableHeader, sortableTable, shouldPinTableHeader };", context);
const x = context.expose;
const nav = [...html.matchAll(/<a href="#\/[\w-]*">[^<]+<\/a>/g)].map(m => m[0]);
assert.equal(nav.length, 10, "ten distinct navigation entries");
assert.equal(new Set(nav).size, 10);
for (const route of ["chronic","open-cases","medications","monitoring","visit-preparation","future-plan","vaccination"]) {
  assert(js.includes(`parts[0] === "${route}"`) || js.includes(`"${route}"`), `route ${route}`);
}
assert(html.includes('aria-expanded="false"'));
assert(css.includes('.topbar nav.is-open { display: flex; }'));

// No redundant visible "Фильтр" caption on either records or future-plan
// filter bars. Keep the bars' aria-label for screen readers.
assert(!js.includes('class="filter-bar-title"'));
assert(js.includes('aria-label="Фильтр записей"'));
assert(js.includes('aria-label="Фильтр будущего плана"'));
// Center names above every filter field without centering input/select values.
function cssDeclarations(selector) {
  const marker = selector + " {";
  const start = css.indexOf(marker);
  assert(start !== -1, "CSS selector missing: " + selector);
  return css.slice(start + marker.length, css.indexOf("}", start));
}
assert(cssDeclarations(".filter-bar label").includes("text-align: center;"));
assert(cssDeclarations(".filter-bar-label").includes("text-align: center;"));
assert(cssDeclarations(".filter-bar select").includes("text-align: start;"));


// Regression: REC markup was inheriting pre-wrap from record-body. Indentation
// in generated table templates became large empty areas above table headings.
assert.match(css, /\.record-body\.rich-record-body\s*\{\s*white-space:\s*normal;/);
assert.match(css, /\.record-body\.rich-record-body\s+\.data-table\s*\{\s*white-space:\s*normal;/);
assert.match(css, /\.data-table th\s*\{[^}]*padding:\s*\.5lh \.5rem;[^}]*line-height:\s*1\.2;[^}]*text-align:\s*center;[^}]*vertical-align:\s*middle;/);
assert.match(css, /\.sort-button\s*\{[^}]*justify-content:\s*center;[^}]*text-align:\s*center;/);
assert.match(css, /\.data-table \.sort-button > span:first-child\s*\{[^}]*min-width:\s*min-content;[^}]*white-space:\s*normal;/);
assert.match(css, /\.data-table thead,[\s\S]*?\.data-table \.sort-button > span\s*\{[^}]*overflow-wrap:\s*normal;[^}]*word-break:\s*normal;[^}]*hyphens:\s*none;/);
assert.equal(x.formatTableHeader("Количество"), "К-во");
assert.equal(x.formatTableHeader("Общее количество результатов"), "Общее К-во результатов");
assert.equal(x.formatTableHeader("Предколичество"), "Предколичество");
assert.equal(x.formatTableHeader("Референс"), "Референс");
const formattedTable = x.sortableTable(
  ["Параметр", "Результат", "Референс", "Ед. изм.", "Количество"],
  [["Показатель", "1", "норма", "ед.", "2"]],
  { id: "heading-contract" }
);
assert(formattedTable.includes("<span>К-во</span>"));
assert(formattedTable.includes('aria-label="Сортировать: Количество"'));
assert(formattedTable.includes("<span>Результат</span>"));
  
// Layout contract for every page: the first-level page title sticks below
// the global header; the filter (when present) stacks below the title.
assert.match(css, /\.content\s*\{\s*padding-top:\s*1rem;/);
assert.match(css, /\.content\s*>\s*h1\s*\{[^}]*position:\s*sticky;[^}]*top:\s*var\(--topbar-height/);
assert.match(css, /\.content\s+\.filter-bar\[data-sticky-filter\]\s*\{[^}]*position:\s*sticky;[^}]*top:\s*calc\(var\(--topbar-height/);
assert.match(css, /\.pinned-table-header\s*\{[^}]*position:\s*fixed;/);
assert.match(css, /\.topbar\s*\{[^}]*z-index:\s*20;/);
assert(js.includes("function setupStickyChrome()"));
assert(js.includes('window.addEventListener("scroll", queuePinnedHeaderUpdate'));
assert(js.includes('cloneTable.appendChild(table.tHead.cloneNode(true))'));
assert(js.includes('cloneTable.style.marginLeft = `${-wrapper.scrollLeft}px`'));
assert(js.includes("original?.click()"), "pinned sort buttons must forward to the original table");
assert(x.shouldPinTableHeader({height:38,bottom:120}, {width:440,bottom:900}, 130, 800));
assert(!x.shouldPinTableHeader({height:38,bottom:180}, {width:440,bottom:900}, 130, 800));
assert(!x.shouldPinTableHeader({height:38,bottom:120}, {width:440,bottom:150}, 130, 800));
assert(!x.shouldPinTableHeader({height:38,bottom:120}, {width:440,bottom:900}, 770, 800));

// All standalone views suppress their repeated section H2, while Current
// State continues to display headings for its multiple sections.
for (const title of ["Хронические состояния","Открытые случаи","Принимаемые препараты",
  "Мониторинг","Подготовка к визиту","Будущий план"]) {
  assert(js.includes('mode === "all" ? "<h2>' + title + '</h2>" : ""'), title + " must not duplicate page title");
}
assert(!js.includes('class="intro"'), "remove page introduction text");
assert(!js.includes("setupClosedCaseFilters"), "closed cases have no filter logic");
const closedSource = js.split("async function renderClosedCases() {")[1].split("async function renderCase(")[0];
assert(!closedSource.includes("filter-bar"), "closed cases have no filter bar");
assert(js.includes('data-sticky-filter aria-label="Фильтр записей"'));
assert(js.includes('mode === "future-plan" ? "data-sticky-filter" : ""'));



// Both controls are assigned the same explicit height on mobile; the menu
// additionally sets equal width and a larger symbol.
assert.match(css, /--mobile-action-height:\s*3\.25rem;/);
assert.match(css, /\.menu-toggle\s*\{[^}]*width:\s*var\(--mobile-action-height\);[^}]*height:\s*var\(--mobile-action-height\);/);
assert.match(css, /\.topbar #logout\s*\{[^}]*height:\s*var\(--mobile-action-height\);/);
assert.match(css, /\.menu-toggle span\s*\{[^}]*font-size:\s*1\.6rem;/);


const q1 = { question: "Кардиологу: обсудить контрольный тест", metadata: {}, basis_record_id: "REC-20260101-001" };
const q2 = { question: "Эндокринологу: обсудить повторную оценку", metadata: {} };
const q3 = { question: "Кардиологу-терапевту или эндокринологу: уточнить план", metadata: {} };
const groups = x.visitPreparation(
  [{ title: "Кардиолог: плановый визит", metadata: { kind: "визит", due_text: "после обследования" } }],
  [q1, q2, q3]
);
assert(groups.includes("Визит к кардиологу"));
assert(groups.includes("Вопросы к эндокринологу — визит не запланирован"));
assert(groups.includes("Вопросы к терапевту — визит не запланирован"));
assert(groups.includes("после обследования"));
const twice = x.visitPreparation([
  { plan_item_id: 31, title: "Кардиолог: первый визит", metadata: { kind: "визит" } },
  { plan_item_id: 32, title: "Кардиолог: повторный визит", metadata: { kind: "визит" } }
], [q1]);
assert.equal((twice.match(/class="case-card visit-card"/g) || []).length, 2, "one row per planned visit");
assert.equal((twice.match(/Кардиологу: обсудить контрольный тест/g) || []).length, 2, "questions shown under each relevant visit");
assert(groups.includes('href="#/records/REC-20260101-001"'));
assert.equal(x.isMedicalCardQuestion(q1), false);
assert.equal(x.isMedicalCardQuestion({ metadata: { category: "medical_card" } }), true);
assert.equal(x.questionSpecialties(q3).length, 3);
assert(!groups.includes("проверка взаимодействий"), "no fabricated medication question");

const rec = x.renderRecordBody("# Тестовая запись\n\n## Обстоятельства\n\nПервый абзац.\n\nВторой абзац.");
assert(rec.includes("<h3>Обстоятельства</h3>"));
assert(rec.includes("<p>Первый абзац.</p>"));
assert(rec.includes("<p>Второй абзац.</p>"));
assert(rec.indexOf("Первый абзац") < rec.indexOf("Второй абзац"));
const table = x.renderRecordBody("# Запись\n\n| Вопрос | Ответ |\n| --- | --- |\n| Тест | Данные |");
assert(table.includes("sortable-table"));
const named = x.recordDisplayTitle({ body_text: "# Русское название\n\nТекст", title: "latin-slug" });
assert.equal(named, "Русское название");
assert(x.fmtMskTimestamp("2026-10-08T12:00:00Z").includes("15:00"));
console.log("PASS frontend navigation, visit groups, question split, REC rendering, MSK, tables");
