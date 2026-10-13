// Read-only projection of vaccination history from existing REC summaries and plan items.
// Source text is never modified. Unknown dose/product/links remain unknown.
const dictionaries = [
  {key:"flu", label:"Грипп", re:/грипп|ультрикс|ultrix|гриппол|совигрипп/iu},
  {key:"tbe", label:"Клещевой энцефалит", re:/клещев|энцефалит|клещ-э-вак/iu},
  {key:"meningococcus", label:"Менингококковая инфекция", re:/менингокок|менактра/iu},
  {key:"pneumococcus", label:"Пневмококковая инфекция", re:/пневмокок|превенар|пневмовакс/iu},
  {key:"hpv", label:"ВПЧ", re:/\bHPV\b|впч/iu},
  {key:"hsv", label:"Герпес 1–2 типа", re:/герпес|витагерпавак/iu},
  {key:"covid", label:"COVID-19", re:/covid|ковид|спутник|гам-ковид/iu},
  {key:"hep-a", label:"Гепатит A", re:/гепатит[а-я]*\s*[aа](?=[^\p{L}]|$)|альгавак/iu},
  {key:"hep-b", label:"Гепатит B", re:/гепатит[а-я]*\s*[bв](?=[^\p{L}]|$)|регевак/iu},
  {key:"measles", label:"Корь", re:/кор[ьи]|корев|жкв/iu},
  {key:"rubella", label:"Краснуха", re:/краснух/iu},
  {key:"mumps", label:"Паротит", re:/паротит/iu},
  {key:"polio", label:"Полиомиелит", re:/полиомиелит|полимилекс/iu}
];

const products = [
  [/Ультрикс Квадри|Ultrix Quadri/iu, "Ультрикс Квадри"],
  [/Ультрикс/iu, "Ультрикс"],
  [/Гриппол плюс|Гриппол\+/iu, "Гриппол плюс"],
  [/Гриппол/iu, "Гриппол"],
  [/Совигрипп/iu, "Совигрипп"],
  [/Клещ-Э-Вак/iu, "Клещ-Э-Вак"],
  [/Менактра/iu, "Менактра"],
  [/Пневмовакс\s*23/iu, "Пневмовакс 23"],
  [/Превенар\s*13/iu, "Превенар 13"],
  [/Альгавак/iu, "Альгавак"],
  [/Регевак/iu, "Регевак"],
  [/АДС[-‑ ]?М/iu, "АДС-М"],
  [/ММР[-‑ ]?(?:II|2)|MMR[-‑ ]?(?:II|2)/iu, "ММР-II"],
  [/ЖКВ/iu, "ЖКВ"],
  [/Гам-КОВИД-Вак/iu, "Гам-КОВИД-Вак"],
  [/Спутник Лайт/iu, "Спутник Лайт"],
  [/Витагерпавак/iu, "Витагерпавак"],
  [/Пентаксим/iu, "Пентаксим"],
  [/Полимилекс/iu, "Полимилекс"]
];

const knownKey = Object.fromEntries(dictionaries.map(item => [item.key, item]));
const has = (text, re) => re.test(String(text || ""));
const uniq = list => [...new Set(list)];
const dateKey = value => /^\d{4}-\d{2}-\d{2}$/.test(String(value || "")) ? String(value) : "";
const recId = value => /^REC-\d{8}-\d{3}$/.test(String(value || "")) ? String(value) : null;

function targets(fragment) {
  if (has(fragment, /\bАКДС\b/iu)) {
    return { keys:["diphtheria","tetanus","pertussis"], label:"Дифтерия, столбняк, коклюш" };
  }
  if (has(fragment, /АДС[-‑ ]?М/iu)) {
    return { keys:["diphtheria","tetanus"], label:"Дифтерия, столбняк" };
  }
  if (has(fragment, /ММР[-‑ ]?(?:II|2)|MMR|кор[ьи].*краснух.*паротит/iu)) {
    return { keys:["measles","rubella","mumps"], label:"Корь, краснуха, паротит" };
  }
  const keys = dictionaries.filter(item => item.re.test(fragment)).map(item => item.key);
  if (!keys.length) return null;
  return { keys:uniq(keys), label:keys.map(key => knownKey[key].label).join(", ") };
}

function vaccineName(fragment) {
  const found = products.find(([pattern]) => pattern.test(fragment));
  return found ? found[1] : "";
}

function stageForActual(fragment, keys) {
  if (keys.includes("flu")) return "RV";
  if (has(fragment, /\bR\d+\b|\bRV\b|ревакцинац/iu)) return "RV";
  const dose = fragment.match(/\bV([1-9]\d*)\b/iu)
    || fragment.match(/(?:доз[аыуе]|доза\s*№)\s*([1-9]\d*)/iu)
    || fragment.match(/([1-9]\d*)[-‑]?(?:я|ая)\s+доз[аыуе]/iu);
  if (dose) return "V" + dose[1];
  if (has(fragment, /компонент\s*II\b/iu)) return "V2";
  if (has(fragment, /компонент\s*I\b/iu)) return "V1";
  return "—";
}

function administeredSummary(summary) {
  const s = String(summary || "");
  return has(s, /(^|\s)Вакцинация\s*:|выполнена вакцинация|привит[аы]?\s+от|вакцинация против|вторая вакцинация|вторая доза/iu);
}

// "Осмотр перед вакцинацией" alone never proves administration.
// This explicit legacy note describes one TBE dose, not COVID/flu doses.
function recordedTbeFromLegacyConsult(summary) {
  const s = String(summary || "");
  return has(s, /^Осмотр перед вакцинацией/iu)
    && has(s, /клещев[а-я -]*энцефалит\s+V\s*[—-]\s*добавлено из ЕМИАС/iu);
}

function splitAdministrationSummary(summary) {
  const s = String(summary || "")
    .replace(/\)\s+и\s+В\s*\(/giu, ") + гепатит В (")
    .replace(/\s+и\s+(?=АДС[-‑ ]?М)/giu, " + ");
  return s.split(/\s+\+\s+/u);
}

export function actualVaccinations(records) {
  const events = [];
  for (const record of records || []) {
    if (String(record.status || "").toLowerCase() === "cancelled") continue;
    const tagged = (record.tags || []).some(x => String(x).toUpperCase() === "VACCINATION")
      || has(record.title, /vakcinaciya|вакцинац|прививк/iu);
    if (!tagged || !dateKey(record.record_date)) continue;
    const summary = String(record.summary || "");
    const legacyTbe = recordedTbeFromLegacyConsult(summary);
    if (!administeredSummary(summary) && !legacyTbe) continue;
    const fragments = legacyTbe && !administeredSummary(summary)
      ? ["клещевой энцефалит"]
      : splitAdministrationSummary(summary);
    for (const fragment of fragments) {
      const target = targets(fragment);
      if (!target) continue;
      const keys = legacyTbe && fragments.length === 1 ? ["tbe"] : target.keys;
      const label = legacyTbe && fragments.length === 1 ? "Клещевой энцефалит" : target.label;
      events.push({
        kind:"actual", id:String(record.record_id) + ":" + keys.join("-"),
        keys, infection:label, stage:stageForActual(fragment, keys),
        date:record.record_date, vaccine:vaccineName(fragment),
        appointmentRecordId:recId(record.metadata?.appointment_record_id),
        administrationRecordId:recId(record.record_id),
        basisRecordId:null, status:"done", sourceStatus:"Проведена"
      });
    }
  }
  return events.sort((a,b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
}

function stageForPlan(item) {
  const meta = item.metadata || {};
  if (/^V[1-9]\d*$/iu.test(String(meta.stage || ""))) return String(meta.stage).toUpperCase();
  if (/^RV$/iu.test(String(meta.stage || ""))) return "RV";
  if (has(item.title, /повторный курс.*5\s+доз/iu)) return "V1–V5";
  if (has(item.title, /ревакцинац|ежегодн/iu)) return "RV";
  return "—";
}

export function plannedVaccinations(items, today = moscowToday()) {
  return (items || []).filter(x => normalizeKind(x.metadata?.kind) === "вакцинация")
    .map(x => {
      const t = targets(String(x.title || ""));
      const due = dateKey(x.due_on);
      const status = String(x.status || "planned");
      const overdue = status === "planned" && due && due < today;
      const sourceStatus = String(x.metadata?.source_status || "");
      return {
        kind:"plan", id:"plan:" + x.plan_item_id, keys:t?.keys || [],
        infection:t?.label || String(x.title || ""), stage:stageForPlan(x),
        date:due, dateText:due ? "" : String(x.metadata?.due_text || "Срок не указан"),
        vaccine:String(x.metadata?.vaccine_name || x.metadata?.vaccine || ""),
        appointmentRecordId:recId(x.metadata?.appointment_record_id),
        administrationRecordId:recId(x.metadata?.administration_record_id),
        basisRecordId:recId(x.basis_record_id), status,
        sourceStatus:status === "cancelled" ? "Отменено"
          : status === "done" ? "Выполнено"
          : overdue ? "Просрочено" : sourceStatus || "Запланировано",
        overdue:Boolean(overdue), title:String(x.title || "")
      };
    }).sort((a,b) => {
      if (!a.date && !b.date) return a.id.localeCompare(b.id);
      if (!a.date) return 1;
      if (!b.date) return -1;
      return a.date.localeCompare(b.date) || a.id.localeCompare(b.id);
    });
}
function normalizeKind(value) {
  return String(value || "").trim().toLocaleLowerCase("ru");
}
export function moscowToday(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone:"Europe/Moscow", year:"numeric", month:"2-digit", day:"2-digit"
  }).formatToParts(now);
  const byType = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return byType.year + "-" + byType.month + "-" + byType.day;
}

function intersection(a,b) {
  return a.some(key => b.includes(key));
}
export function buildVaccinationView(records, planItems, today = moscowToday()) {
  const actual = actualVaccinations(records);
  const plans = plannedVaccinations(planItems,today);
  const upcoming = plans.filter(item => item.status === "planned");
  const latestPerAntigen = new Map();
  for (const item of actual) {
    for (const key of item.keys) {
      if (!latestPerAntigen.has(key)) latestPerAntigen.set(key,item);
    }
  }
  const latest = uniq([...latestPerAntigen.values()]).sort(
    (a,b) => a.infection.localeCompare(b.infection,"ru")
  ).map(item => {
    const next = upcoming.find(plan => intersection(plan.keys,item.keys));
    return {...item, next:next || null};
  });
  const history = [...actual, ...plans].sort((a,b) =>
    (b.date || "").localeCompare(a.date || "") || a.id.localeCompare(b.id)
  );
  return {latest, planned:upcoming, history};
}
