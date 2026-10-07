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
    if (parts[0] === "records" && parts.length === 1) return renderRecords();
    if (parts[0] === "records" && parts[1]) return renderRecord(decodeURIComponent(parts[1]));
    if (parts[0] === "sources" && parts[1]) return renderSource(decodeURIComponent(parts[1]));
    view.innerHTML = "<h1>Не найдено</h1>";
  } catch (error) {
    console.error(error);
    view.innerHTML = '<h1>Ошибка</h1><p class="error">Не удалось загрузить данные.</p>';
  }
}

async function renderCurrentState() {
  const [cases, meds, monitoring, plan, questions] = await Promise.all([
    supabase.from("cases").select("case_key,title,summary,status,category").eq("status","open").order("title"),
    supabase.from("medications").select("medication_id,name,dose,schedule,status").eq("status","active").order("name"),
    supabase.from("monitoring").select("monitoring_id,title,cadence_text,status").eq("status","active").order("title"),
    supabase.from("plan_items").select("plan_item_id,title,due_on,status").eq("status","planned").order("due_on",{ascending:true,nullsFirst:false}),
    supabase.from("questions").select("question_id,question,status").eq("status","open").order("question_id")
  ]);

  for (const result of [cases, meds, monitoring, plan, questions]) {
    if (result.error) throw result.error;
  }

  view.innerHTML = `
    <h1>Текущее состояние</h1>
    <section>
      <h2>Открытые случаи</h2>
      ${list(cases.data, x => `<li><a href="#/records/${encodeURIComponent(x.case_key)}"><strong>${esc(x.title)}</strong></a>${x.summary ? `<p>${esc(x.summary)}</p>` : ""}</li>`)}
    </section>
    <section>
      <h2>Активные препараты</h2>
      ${list(meds.data, x => `<li><strong>${esc(x.name)}</strong><p>${esc([x.dose,x.schedule].filter(Boolean).join(" · "))}</p></li>`)}
    </section>
    <section>
      <h2>Мониторинг</h2>
      ${list(monitoring.data, x => `<li><strong>${esc(x.title)}</strong><p>${esc(x.cadence_text || "")}</p></li>`)}
    </section>
    <section>
      <h2>План</h2>
      ${list(plan.data, x => `<li><strong>${esc(x.title)}</strong><p>${esc(x.due_on || "")}</p></li>`)}
    </section>
    <section>
      <h2>Открытые вопросы</h2>
      ${list(questions.data, x => `<li>${esc(x.question)}</li>`)}
    </section>
  `;
}

async function renderRecords() {
  const { data, error } = await supabase
    .from("records")
    .select("record_id,record_date,title,type,record_type,status,summary")
    .order("record_date", { ascending: false })
    .limit(250);

  if (error) throw error;

  view.innerHTML = `
    <h1>Записи</h1>
    ${list(data, r => `
      <li>
        <a href="#/records/${encodeURIComponent(r.record_id)}"><strong>${esc(r.title)}</strong></a>
        <p class="muted">${esc(r.record_date)} · ${esc(r.record_id)}</p>
        ${r.summary ? `<p>${esc(r.summary)}</p>` : ""}
      </li>
    `)}
  `;
}

async function renderRecord(recordId) {
  const [{ data: record, error: recordError }, { data: links, error: linksError }] = await Promise.all([
    supabase.from("records").select("*").eq("record_id", recordId).single(),
    supabase.from("record_sources").select("source_id,role,source_pages").eq("record_id", recordId)
  ]);

  if (recordError) throw recordError;
  if (linksError) throw linksError;

  view.innerHTML = `
    <p><a href="#/records">← Записи</a></p>
    <h1>${esc(record.title)}</h1>
    <p class="muted">${esc(record.record_date)} · ${esc(record.record_id)}</p>
    ${record.summary ? `<p class="lead">${esc(record.summary)}</p>` : ""}
    <article class="record-body">${esc(record.body_text).replaceAll("\n","<br>")}</article>
    <section>
      <h2>Источники</h2>
      ${list(links, x => `<li><a href="#/sources/${encodeURIComponent(x.source_id)}">${esc(x.source_id)}</a><p class="muted">${esc(x.role)} ${esc(x.source_pages || "")}</p></li>`)}
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
      <dt>Дата</dt><dd>${esc(source.source_date || "")}</dd>
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
