import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import {actualVaccinations, plannedVaccinations, buildVaccinationView} from "../vaccination.mjs";

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

// Vaccination projection: only confirmed administrations are included; no
// real medical data or REC identifiers are used as public test fixtures.
const vaccinationRecords = [
  {record_id:"REC-20050115-001",record_date:"2005-01-15",status:"active",
    tags:["VACCINATION"], summary:"Вакцинация: грипп (Ультрикс Квадри, V1) + пневмококковая инфекция (Превенар 13, V1)"},
  {record_id:"REC-20050116-002",record_date:"2005-01-16",status:null,
    tags:["VACCINATION"],summary:"Осмотр перед вакцинацией от полиомиелита (Полимилекс)"},
  {record_id:"REC-20050117-003",record_date:"2005-01-17",status:"cancelled",
    tags:["VACCINATION"],summary:"Вакцинация: грипп (Совигрипп, V1)"},
  {record_id:"REC-20010101-004",record_date:"2001-01-01",status:"active",
    tags:["VACCINATION"],summary:"Вакцинация: корь (ЖКВ, V1)"},
  {record_id:"REC-20020101-005",record_date:"2002-01-01",status:null,
    tags:["VACCINATION"],summary:"Осмотр перед вакцинацией, привит от кори, краснухи, паротита (ММР-II)"},
  {record_id:"REC-20010601-006",record_date:"2001-06-01",status:null,
    tags:["VACCINATION"],summary:"Осмотр перед вакцинацией",
    body_text:"## Выполненные вакцинации\n- Вакцинация против клещевого энцефалита (Клещ-Э-Вак, первая вакцинация основного курса)\n## Рекомендации\n- Вакцинация против гриппа в будущем"},
  {record_id:"REC-20020808-007",record_date:"2002-08-08",status:"active",
    tags:["VACCINATION"],summary:"Вакцинация: вирус герпеса 1-2 типа (Витагерпавак, доза 5)"},
  {record_id:"REC-20000303-008",record_date:"2000-03-03",status:null,
    tags:["VACCINATION"],summary:"Клиника: вакцинация против гепатита А (Альгавак) и В (Регевак)"},
  {record_id:"REC-20040305-009",record_date:"2004-03-05",status:null,
    tags:["VACCINATION"],summary:"Осмотр перед вакцинацией, привит от менингококка/пневмококка"},
  {record_id:"REC-20060707-010",record_date:"2006-07-07",status:null,
    tags:["VACCINATION"],summary:"Осмотр перед вакцинацией",
    body_text:"## Вакцинация\n- **Вакцина:** Полиомиелит (Полимилекс)\n## Рекомендации\n- Вакцинация против гриппа следующей осенью"},
  {record_id:"REC-20070808-011",record_date:"2007-08-08",status:null,
    tags:["VACCINATION"],summary:"Осмотр перед вакцинацией",
    body_text:"**Вакцинация:**\n- Вакцинирован от дифтерии, столбняка, коклюша, полиомиелита, гемофильной инфекции (Пентаксим)\n**Рекомендации:**\n- Вакцинация против гриппа плановая"}
];
const vaccinationPlans = [
  {plan_item_id:1,title:"Ежегодная вакцинация от гриппа",status:"planned",
    due_on:"2028-04-10",basis_record_id:"REC-20050115-001",metadata:{kind:"вакцинация"}},
  {plan_item_id:2,title:"Ревакцинация от клещевого энцефалита",status:"planned",
    due_on:"2026-04-10",basis_record_id:"REC-20010601-006",
    metadata:{kind:"вакцинация",source_status:"запланировано"}},
  {plan_item_id:3,title:"Повторный курс вакцинации Витагерпавак, 5 доз",status:"planned",
    due_on:null,metadata:{kind:"вакцинация",due_text:"срок не определён"}},
  {plan_item_id:4,title:"Анализ на антитела к кори",status:"planned",
    due_on:"2027-01-01",metadata:{kind:"обследование"}},
  {plan_item_id:5,title:"Ревакцинация от кори",status:"cancelled",
    due_on:"2001-01-01",metadata:{kind:"вакцинация"}}
];
const doses = actualVaccinations(vaccinationRecords);
assert.equal(doses.length,12,"one row per separately administered vaccine, plus one combined MMR");
assert.equal(doses.filter(x => x.date === "2004-03-05").length,2,"slash-separated injections stay separate");
assert.equal(doses.filter(x => x.infection === "Грипп").length,1,"cancelled and legacy consultation cannot invent flu doses");
assert.equal(doses.find(x => x.infection === "Грипп")?.stage,"RV","flu is RV even if source says V1");
assert.equal(doses.find(x => x.infection === "Пневмококковая инфекция")?.vaccine,"Превенар 13");
assert.equal(doses.find(x => x.infection === "Герпес 1–2 типа")?.stage,"V5");
assert(doses.find(x => x.infection === "Клещевой энцефалит"));
assert.equal(doses.filter(x => x.infection === "Гепатит A" || x.infection === "Гепатит B").length,2);
assert(doses.some(x => x.infection.includes("Гемофильная инфекция") || x.infection.includes("гемофильная")),"combination vaccine extracted from body");
assert(doses.some(x => x.infection === "Полиомиелит"),"confirmed body-only vaccine extracted");
assert.equal(doses.find(x => x.infection === "Клещевой энцефалит")?.stage,"V1");
assert(js.includes('contains("tags",["VACCINATION"])'),"fetch only vaccine-tagged RECs");
assert(doses.some(x => x.infection === "Корь, краснуха, паротит"),"MMR remains one injection");
assert(doses.every(x => x.administrationRecordId && !x.basisRecordId));

const future = plannedVaccinations(vaccinationPlans,"2026-10-13");
assert.equal(future.length,4,"category filter is immutable and must include cancelled plan history");
assert.equal(future.find(x => x.id === "plan:1").stage,"RV");
assert.equal(future.find(x => x.id === "plan:1").basisRecordId,"REC-20050115-001");
assert.equal(future.find(x => x.id === "plan:1").appointmentRecordId,null,"supporting REC is not silently a prescription");
assert.equal(future.find(x => x.id === "plan:2").sourceStatus,"Просрочено");
assert.equal(future.find(x => x.id === "plan:3").stage,"V1–V5");
assert(!future.find(x => x.id === "plan:3").overdue,"undated items are not overdue");
const akds = plannedVaccinations([{plan_item_id:99,title:"Ревакцинация АКДС",status:"planned",metadata:{kind:"вакцинация"}}],"2026-10-13")[0];
assert.equal(akds.infection,"Дифтерия, столбняк, коклюш");
assert.equal(akds.stage,"RV");
const vaccineView=buildVaccinationView(vaccinationRecords,vaccinationPlans,"2026-10-13");
assert.equal(vaccineView.planned.length,3,"cancelled plan does not appear among upcoming doses");
assert.equal(vaccineView.history.length,doses.length+future.length);
assert(!vaccineView.latest.some(x => x.infection === "Корь"),"later combination vaccine supersedes older measles-only row");
assert(vaccineView.latest.find(x => x.infection === "Клещевой энцефалит")?.next?.overdue);
assert(vaccineView.latest.find(x => x.infection === "Грипп")?.next?.date === "2028-04-10");
assert(vaccineView.history.some(x => x.status === "cancelled"));
console.log("PASS vaccination REC selection, stages, history, overdue and evidence links");
