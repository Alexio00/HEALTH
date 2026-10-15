import "./logout.mjs";
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
vm.runInContext(harness + "\n globalThis.expose = { visitPreparation, plannedVisitSpecialties, isMedicalCardQuestion, questionSpecialties, medicationRecordIds, latestMedicationRecordId, medicationHistoriesForRecord, renderRecordBody, recordDisplayTitle, fmtMskTimestamp, formatTableHeader, sortableTable, shouldPinTableHeader, vaccinationRecCell, vaccinationRows };", context);
const x = context.expose;

// Shared REC cell renderer is used in all three vaccination tables. Only
// human-visible prefixes disappear; links and their source roles remain.
const appointment = "REC-20260101-001";
const basis = "REC-20260102-002";
const administration = "REC-20260103-003";
for (const section of ["latest", "planned", "history"]) {
  const rows = x.vaccinationRows([{
    infection: "Синтетическая инфекция", stage: "V1", date: "2026-01-04",
    vaccine: "Синтетическая вакцина", sourceStatus: "Запланировано",
    basisRecordId: basis, administrationRecordId: administration
  }], section);
  const cell = rows[0].cells[5].html;
  assert(cell.includes('href="#/records/' + basis + '"'), section + " keeps basis REC");
  assert(cell.includes('href="#/records/' + administration + '"'), section + " keeps administration REC");
  assert(!cell.includes("Осн.:"), section + " drops basis prefix");
  assert(!cell.includes("Пров.:"), section + " drops administration prefix");
  assert(cell.includes('title="Основание REC"'), section + " retains basis link context");
  assert(cell.includes('title="Запись о проведении"'), section + " retains administration link context");
}
// A multiple-infection REC displays its existing labels without inferring one
// injection, an independently confirmed antigen stage, or a clinical link.
const multiItem = {
  kind:"actual", infection:"Корь, краснуха, паротит",
  keys:["measles","rubella","mumps"], stage:"—",
  administrationRecordId:administration, sourceStatus:"Проведена"
};
const multiRows = x.vaccinationRows([multiItem],"history");
const multiHtml = multiRows[0].cells[0].html;
assert(multiHtml.includes('<details class="vaccination-multi-infection">'));
assert.equal((multiHtml.match(/class="vaccination-component-tag"/g)||[]).length,3);
for (const name of ["Корь", "краснуха", "паротит"]) assert(multiHtml.includes(name));
assert(!/комбинированная|инъекция|Rv[0-9]|V[0-9]/iu.test(multiHtml),
  "UI must not invent a combined product or per-antigen stage");
assert(!x.vaccinationRows([multiItem],"latest")[0].cells[0].html.includes("<details"),
  "current latest projection is unchanged");
assert(!x.vaccinationRows([{
  kind:"plan", infection:"Корь, краснуха",keys:["measles","rubella"]
}],"history")[0].cells[0].html.includes("<details"),
  "a planned dose is not presented as administration");
const hostileInfection = x.vaccinationRows([{
  ...multiItem, infection:"Корь, <img src=x onerror=alert(1)>"
}],"history")[0].cells[0].html;
assert(!hostileInfection.includes("<img") && hostileInfection.includes("&lt;img"),
  "both summary and expanded labels are HTML-escaped");
assert.equal(multiRows[0].cells[0].filterValue,"Корь, краснуха, паротит");
assert(multiRows[0].cells[5].html.includes(administration),
  "historical REC link survives display-only grouping");
assert(css.includes(".vaccination-multi-infection summary:focus-visible"),
  "keyboard focus remains visible");

assert(x.vaccinationRecCell({appointmentRecordId: appointment})
  .includes("Назн.:"), "separately requested labels are not silently changed");
assert.equal((x.vaccinationRecCell({basisRecordId: basis, administrationRecordId: basis})
  .match(/href=/g) || []).length, 1, "duplicate evidence link is still suppressed");
assert.match(css, /\.case-body p:not\(\.rec-inline\),\s*\.content > p\.lead,\s*\.rich-record-body p\s*\{[^}]*text-align:\s*justify;[^}]*text-align-last:\s*left;[^}]*hyphens:\s*auto;/);
assert.match(css, /\.data-table td\s*\{[^}]*text-align:\s*left;/,
  "tabular lines stay left aligned");
console.log("PASS vaccination link-only cells and justified prose boundaries");

const nav = [...html.matchAll(/<a href="#\/[\w-]*">[^<]+<\/a>/g)].map(m => m[0]);
assert.equal(nav.length, 9, "nine distinct navigation entries");
assert.equal(new Set(nav).size, 9);
assert(!html.includes('href="#/monitoring"'), "remove monitoring from navigation");
assert(!js.includes('from("monitoring")'), "removed route must not query monitoring");
assert(!js.includes('"monitoring":'), "no hidden section or page remains");
assert(!js.includes('"monitoring",'), "removed page is not routable");

for (const route of ["chronic","open-cases","medications","visit-preparation","future-plan","vaccination"]) {
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
// Every expandable case/question/visit card must use full-width prose, not 80ch.
assert(css.includes(".case-card .lead,\n.case-card .lead-small { max-width: none; }"));


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
  "Подготовка к визиту","Будущий план"]) {
  assert(js.includes('mode === "all" ? "<h2>' + title + '</h2>" : ""'), title + " must not duplicate page title");
}
assert(!js.includes('class="intro"'), "remove page introduction text");
assert(!js.includes("setupClosedCaseFilters"), "closed cases have no filter logic");
const closedSource = js.split(/async function renderClosedCases\([^)]*\) \{/)[1]?.split("async function renderCase(")[0];
assert(closedSource, "closed cases renderer must be present");
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
assert(!groups.includes("вопросов:"), "visit headers contain titles only");

// The plan itself names the specialty; do not require a short colon-prefixed
// heading. Unspecified questions can use an explicit visit note.
const visits = [
  { plan_item_id: 1, title: "Травматолог-ортопед: контрольный осмотр", metadata: { kind: "визит" } },
  { plan_item_id: 2, title: "Колопроктолог: плановый приём", metadata: { kind: "визит" } },
  { plan_item_id: 3, title: "Приём в СПИД-центре у врача; обсудить план", metadata: { kind: "визит" } },
  { plan_item_id: 4, title: "Косметолог: процедура", metadata: { kind: "визит" } },
  { plan_item_id: 5, title: "Эндокринолог при повторно повышенном показателе и иных условиях", metadata: { kind: "визит" } },
  { plan_item_id: 6, title: "Гастроэнтеролог при сохраняющемся повышении показателя и дополнительных симптомах", metadata: { kind: "визит" } }
];
const visitQuestions = [
  { question: "Как сохранить здоровье суставов?", metadata: { note: "Вопрос к будущему приёму ортопеда. Сформулирован владельцем." } },
  { question: "Эндокринологу: обсудить контроль", metadata: {} },
  { question: "Инфекционисту: обсудить контроль", metadata: {} }
];
const visitHtml = x.visitPreparation(visits, visitQuestions);
for (const title of ["Визит к ортопеду", "Визит к колопроктологу",
  "Визит к инфекционисту", "Визит к косметологу", "Визит к эндокринологу",
  "Визит к гастроэнтерологу"]) assert(visitHtml.includes(title), title);
assert(!visitHtml.includes("Визит к специалисту"), "no generic title for explicitly named visits");
assert(!visitHtml.includes("Вопросы к специалисту — специальность не указана"));
assert(!visitHtml.includes("Вопросы к эндокринологу — визит не запланирован"));
assert(!visitHtml.includes("Вопросы к инфекционисту — визит не запланирован"));
assert(!visitHtml.includes("вопросов:"));
assert.equal(x.questionSpecialties(visitQuestions[0]).join(","), "ортопед");

// Use existing metadata sources and SELECTed REC dates, not opaque NNN order,
// to link the latest current medication evidence; never fabricate a REC.
const activeMed = { basis_record_id: null, metadata: { source_record_ids: [
  "REC-20250101-270", "REC-20261001-001"] } };
assert.equal(x.medicationRecordIds(activeMed).length, 2);
assert.equal(x.latestMedicationRecordId(activeMed,
  new Map([["REC-20250101-270", "2025-01-01"], ["REC-20261001-001", "2026-10-01"]])),
  "REC-20261001-001");
assert.equal(x.latestMedicationRecordId(activeMed, new Map()), "",
  "missing/unreadable records must not produce broken links");
const syntheticHistory = x.medicationHistoriesForRecord("REC-20261001-001", [
  { name: "Синтетический препарат", ...activeMed },
  { name: "Другой препарат", metadata: { source_record_ids: ["REC-20230101-002"] } }
]);
assert.equal(syntheticHistory.length, 1, "only the matching medication contributes history");
assert.equal(syntheticHistory[0].recordIds.join(","), "REC-20250101-270");

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
assert.equal(doses.find(x => x.infection === "Грипп")?.stage,"Rv","flu is Rv even if source says V1");
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
assert.equal(future.find(x => x.id === "plan:1").stage,"Rv");
assert.equal(future.find(x => x.id === "plan:1").basisRecordId,"REC-20050115-001");
assert.equal(future.find(x => x.id === "plan:1").appointmentRecordId,null,"supporting REC is not silently a prescription");
assert.equal(future.find(x => x.id === "plan:2").sourceStatus,"Просрочено");
assert.equal(future.find(x => x.id === "plan:3").stage,"V1–V5");
assert(!future.find(x => x.id === "plan:3").overdue,"undated items are not overdue");
const akds = plannedVaccinations([{plan_item_id:99,title:"Ревакцинация АКДС",status:"planned",metadata:{kind:"вакцинация"}}],"2026-10-13")[0];
assert.equal(akds.infection,"Дифтерия, столбняк, коклюш");
assert.equal(akds.stage,"Rv");
// Synthetic evidence: normalize letter case, never invent a missing booster index.
const numberedRecords = [
  {record_id:"REC-20090115-101",record_date:"2009-01-15",status:"active",tags:["VACCINATION"],
    summary:"Вакцинация: корь (ЖКВ, Rv1)"},
  {record_id:"REC-20100115-102",record_date:"2010-01-15",status:"active",tags:["VACCINATION"],
    summary:"Вакцинация: пневмококковая инфекция (Превенар 13, RV2)"}
];
const numbered = actualVaccinations(numberedRecords);
assert.equal(numbered.find(x => x.infection === "Корь")?.stage,"Rv1");
assert.equal(numbered.find(x => x.infection === "Пневмококковая инфекция")?.stage,"Rv2");
const numberedPlans = plannedVaccinations([
  {plan_item_id:101,title:"Ревакцинация от кори",status:"planned",
    metadata:{kind:"вакцинация",stage:"rv1"}},
  {plan_item_id:102,title:"Ревакцинация от кори (Rv2)",status:"planned",
    metadata:{kind:"вакцинация"}},
  {plan_item_id:103,title:"Ревакцинация от кори",status:"planned",
    metadata:{kind:"вакцинация"}},
  {plan_item_id:104,title:"Ревакцинация от кори (Rv2)",status:"planned",
    metadata:{kind:"вакцинация",stage:"RV1"}}
],"2026-10-13");
assert.deepEqual(numberedPlans.map(item => item.stage),["Rv1","Rv2","Rv","Rv1"],
  "metadata wins over explicit title; unnumbered revaccination stays unnumbered");

// PWA80-M01: a fragment is not evidence for transferring a numbered stage
// to every infection, nor for turning a future plan into a completed dose.
const ambiguousStages = actualVaccinations([
  {record_id:"REC-20110101-111",record_date:"2011-01-01",tags:["VACCINATION"],
    summary:"Вакцинация: корь (ЖКВ, Rv2), краснуха (V1)"},
  {record_id:"REC-20110102-112",record_date:"2011-01-02",tags:["VACCINATION"],
    summary:"Вакцинация: корь, краснуха (Rv2)"},
  {record_id:"REC-20110103-113",record_date:"2011-01-03",tags:["VACCINATION"],
    summary:"Вакцинация: корь (ЖКВ, V1), в будущем ревакцинация Rv2"},
  {record_id:"REC-20110104-114",record_date:"2011-01-04",tags:["VACCINATION"],
    summary:"Вакцинация: корь (ЖКВ, Rv2); следующая ревакцинация Rv3"},
  {record_id:"REC-20110105-115",record_date:"2011-01-05",tags:["VACCINATION"],
    summary:"Вакцинация: корь (ЖКВ); планируется ревакцинация Rv2"},
  {record_id:"REC-20110106-116",record_date:"2011-01-06",tags:["VACCINATION"],
    summary:"Вакцинация: корь (ЖКВ, V1) и повторно Rv2"}
]);
const stagedByRecord = new Map(ambiguousStages.map(item => [item.administrationRecordId, item]));
assert.equal(stagedByRecord.get("REC-20110101-111")?.stage,"—",
  "different infection stages cannot be collapsed into Rv2");
assert.equal(stagedByRecord.get("REC-20110102-112")?.stage,"—",
  "a multi-infection fragment cannot automatically share a numbered stage");
assert.equal(stagedByRecord.get("REC-20110103-113")?.stage,"V1",
  "future booster cannot replace the performed first stage");
assert.equal(stagedByRecord.get("REC-20110104-114")?.stage,"Rv2",
  "future Rv3 cannot replace the administered Rv2");
assert.equal(stagedByRecord.get("REC-20110105-115")?.stage,"—",
  "an only-planned Rv2 cannot be reported as administered");
assert.equal(stagedByRecord.get("REC-20110106-116")?.stage,"—",
  "two nonfuture stage claims in one fragment must remain ambiguous");

// PWA80-M01 R2: postfix plans and textual doses are adversarial input too.
// No future-only infection may appear as a performed multi-infection label.
const reproInputs = [
  ["REC-20110201-121","Вакцинация: корь (ЖКВ, Rv2 запланирована)"],
  ["REC-20110202-122","Вакцинация: корь (ЖКВ, V1), ревакцинация Rv2 запланирована"],
  ["REC-20110203-123","Вакцинация: корь (ЖКВ, V1; доза 2)"],
  ["REC-20110204-124","Вакцинация: корь (ЖКВ, V1; вторая вакцинация)"],
  ["REC-20110205-125","Вакцинация: корь (ЖКВ, V1), краснуха запланирована"],
  ["REC-20110206-126","Вакцинация: корь (ЖКВ, V1), в будущем краснуха (Rv2)"],
  ["REC-20110207-127","Вакцинация: краснуха запланирована"],
  ["REC-20110208-128","Вакцинация: корь (ЖКВ, V1, Rv2 рекомендована)"],
  ["REC-20110209-129","Вакцинация: корь (ЖКВ, Rv2) и краснуха запланирована"],
  ["REC-20110210-130","Вакцинация: корь (ЖКВ, V1); ревакцинация Rv2 назначена"]
];
const reproRows = actualVaccinations(reproInputs.map(([record_id,summary]) => ({
  record_id, summary, record_date:"2011-02-01", tags:["VACCINATION"]
})));
const repro = new Map(reproRows.map(row => [row.administrationRecordId,row]));
for (const id of ["REC-20110201-121","REC-20110207-127"]) {
  assert(!repro.has(id), id + ": future-only vaccination cannot be actual");
}
for (const id of ["REC-20110202-122","REC-20110205-125","REC-20110206-126",
  "REC-20110208-128","REC-20110210-130"]) {
  assert.equal(repro.get(id)?.stage,"V1",id + ": keep only performed V1");
}
for (const id of ["REC-20110203-123","REC-20110204-124"])
  assert.equal(repro.get(id)?.stage,"—",id + ": conflicting textual dose is ambiguous");
assert.equal(repro.get("REC-20110209-129")?.stage,"Rv2",
  "future rubella cannot dilute a separately performed measles booster");
for (const id of ["REC-20110205-125","REC-20110206-126","REC-20110209-129"]) {
  assert.deepEqual(repro.get(id)?.keys,["measles"],
    id + ": no future-only rubella antigen in actual row");
}
const bodyMixed = actualVaccinations([{
  record_id:"REC-20110301-131",record_date:"2011-03-01",tags:["VACCINATION"],
  summary:"Осмотр перед вакцинацией",
  body_text:"## Вакцинация\n- Вакцинация против кори (ЖКВ, V1), краснуха запланирована\n## Рекомендации\n- Вакцинация против паротита"
}]);
assert.equal(bodyMixed.length,1,"performed body line retained even when plan follows");
assert.deepEqual(bodyMixed[0].keys,["measles"],"body future infection excluded");
console.log("PASS PWA80-M01 R2 postfix plans, mixed antigens, conflicting textual doses");

// PWA80-M01-R3: a comma/semicolon INSIDE an event is not an administration
// boundary. Postfix "Rv2, запланирована" must never be shown as performed.
const r3 = [
  ["141","Вакцинация: краснуха (Rv2, запланирована)",null],
  ["142","Вакцинация: краснуха (Rv2; запланирована)",null],
  ["143","Вакцинация: краснуха Rv2, запланирована",null],
  ["144","Вакцинация: краснуха (Rv2) запланирована",null],
  ["145","Вакцинация: краснуха (Rv2, рекомендована)",null],
  ["146","Вакцинация: корь (ЖКВ, V1), краснуха (Rv2, запланирована)",["measles","V1"]],
  ["147","Вакцинация: корь (ЖКВ, V1, краснуха запланирована)",["measles","V1"]],
  ["148","Вакцинация: корь (ЖКВ, V1, Rv2 запланирована)",["measles","V1"]],
  ["149","Вакцинация: корь (ЖКВ, V1), краснуха, запланирована",["measles","V1"]],
  ["150","Вакцинация: корь (ЖКВ, Rv2), краснуха (Rv2, запланирована)",["measles","Rv2"]],
  ["151","Вакцинация: корь (ЖКВ, V1) и краснуха (Rv2, запланирована)",["measles","V1"]],
  ["152","Вакцинация: корь (ЖКВ, V1; доза 2)",["measles","—"]],
  ["153","Вакцинация: краснуха (V1)",["rubella","V1"]]
];
const r3Events = actualVaccinations(r3.map(([nnn, summary]) => ({
  record_id:"REC-20110401-" + nnn,record_date:"2011-04-01",
  tags:["VACCINATION"],summary
})));
const r3ById = new Map(r3Events.map(event => [event.administrationRecordId,event]));
for (const [nnn,,expect] of r3) {
  const id = "REC-20110401-" + nnn;
  const found = r3ById.get(id);
  if (!expect) {
    assert.equal(found,undefined,id + ": future-only vaccination must not be actual");
  } else {
    assert(found,id + ": previous performed event must remain visible");
    assert.deepEqual(found.keys,[expect[0]],id + ": future antigen not administered");
    assert.equal(found.stage,expect[1],id + ": performed stage only");
  }
}
const r3Body = actualVaccinations([
  {record_id:"REC-20110401-154",record_date:"2011-04-01",tags:["VACCINATION"],
    summary:"Осмотр перед вакцинацией",
    body_text:"## Вакцинация\n- Вакцинация против краснухи (Rv2, запланирована)"},
  {record_id:"REC-20110401-155",record_date:"2011-04-01",tags:["VACCINATION"],
    summary:"Осмотр перед вакцинацией",
    body_text:"## Вакцинация\n- Вакцинация против кори (ЖКВ, V1)\n- Вакцинация против краснухи (Rv2, запланирована)\n## Рекомендации\n- Вакцинация против паротита"}
]);
assert.equal(r3Body.length,1,"future-only body must not create administered events");
assert.equal(r3Body[0].administrationRecordId,"REC-20110401-155");
assert.deepEqual(r3Body[0].keys,["measles"],"future-only body infection excluded");
assert.equal(r3Body[0].stage,"V1");
console.log("PASS PWA80-M01 R3 balanced events, postfix plans and future-only body");

const vaccineView=buildVaccinationView(vaccinationRecords,vaccinationPlans,"2026-10-13");
assert.equal(vaccineView.planned.length,3,"cancelled plan does not appear among upcoming doses");
assert.equal(vaccineView.history.length,doses.length+future.length);
assert(!vaccineView.latest.some(x => x.infection === "Корь"),"later combination vaccine supersedes older measles-only row");
assert(vaccineView.latest.find(x => x.infection === "Клещевой энцефалит")?.next?.overdue);
assert(vaccineView.latest.find(x => x.infection === "Грипп")?.next?.date === "2028-04-10");
assert(vaccineView.history.some(x => x.status === "cancelled"));
console.log("PASS vaccination REC selection, stages, history, overdue and evidence links");

// TEST OAuth config and network gates; synthetic values only.
await import('./oauth-consent.mjs');
