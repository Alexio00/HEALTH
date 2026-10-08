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
vm.runInContext(harness + "\n globalThis.expose = { visitPreparation, isMedicalCardQuestion, questionSpecialties, renderRecordBody, recordDisplayTitle, fmtMskTimestamp };", context);
const x = context.expose;
const nav = [...html.matchAll(/<a href="#\/[\w-]*">[^<]+<\/a>/g)].map(m => m[0]);
assert.equal(nav.length, 10, "ten distinct navigation entries");
assert.equal(new Set(nav).size, 10);
for (const route of ["chronic","open-cases","medications","monitoring","visit-preparation","future-plan","vaccination"]) {
  assert(js.includes(`parts[0] === "${route}"`) || js.includes(`"${route}"`), `route ${route}`);
}
assert(html.includes('aria-expanded="false"'));
assert(css.includes('.topbar nav.is-open { display: flex; }'));

const q1 = { question: "Кардиологу: обсудить контрольный тест", metadata: {}, basis_record_id: "REC-20260101-001" };
const q2 = { question: "Эндокринологу: обсудить повторную оценку", metadata: {} };
const q3 = { question: "Кардиологу-терапевту или эндокринологу: уточнить план", metadata: {} };
const groups = x.visitPreparation(
  [{ title: "Кардиолог: плановый визит", metadata: { kind: "визит", due_text: "после обследования" } }],
  [q1, q2, q3]
);
assert(groups.includes("Визит к кардиологу"));
assert(groups.includes("Визит к эндокринологу"));
assert(groups.includes("Визит к терапевту"));
assert(groups.includes("после обследования"));
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
