const STORAGE_KEY = "health.session.v1";

function apiError(status, area) {
  return new Error(`${area} request failed (${status})`);
}

export function createClient(baseUrl, publishableKey) {
  let refreshPromise = null;

  const load = () => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
  };

  const save = (payload) => {
    if (!payload?.access_token || !payload?.refresh_token || !payload?.user) {
      throw new Error("Incomplete auth session");
    }
    const session = {
      access_token: payload.access_token,
      refresh_token: payload.refresh_token,
      token_type: payload.token_type || "bearer",
      expires_at: payload.expires_at || Math.floor(Date.now() / 1000) + Number(payload.expires_in || 3600),
      user: payload.user
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    return session;
  };

  const clear = () => localStorage.removeItem(STORAGE_KEY);

  async function authRequest(path, body, accessToken = "") {
    const headers = {
      apikey: publishableKey,
      "Content-Type": "application/json"
    };
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    const response = await fetch(`${baseUrl}/auth/v1/${path}`, {
      method: "POST",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store"
    });
    return response;
  }

  async function refreshSession() {
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async () => {
      const current = load();
      if (!current?.refresh_token) return null;
      const response = await authRequest("token?grant_type=refresh_token", {
        refresh_token: current.refresh_token
      });
      if (!response.ok) {
        clear();
        throw apiError(response.status, "Auth refresh");
      }
      const payload = await response.json();
      return save(payload);
    })().finally(() => {
      refreshPromise = null;
    });
    return refreshPromise;
  }

  async function ensureSession() {
    const current = load();
    if (!current?.access_token) return null;
    const now = Math.floor(Date.now() / 1000);
    if (!current.expires_at || current.expires_at - now <= 60) {
      return refreshSession();
    }
    return current;
  }

  async function restRequest(table, params, retry = true) {
    const session = await ensureSession();
    if (!session?.access_token) return { response: null, error: new Error("Authentication required") };

    const url = new URL(`${baseUrl}/rest/v1/${encodeURIComponent(table)}`);
    for (const [key, value] of params) url.searchParams.append(key, value);

    const response = await fetch(url, {
      method: "GET",
      headers: {
        apikey: publishableKey,
        Authorization: `Bearer ${session.access_token}`,
        Accept: "application/json"
      },
      cache: "no-store"
    });

    if (response.status === 401 && retry && session.refresh_token) {
      await refreshSession();
      return restRequest(table, params, false);
    }
    if (!response.ok) return { response, error: apiError(response.status, "Database") };
    return { response, error: null };
  }

  class QueryBuilder {
    constructor(table) {
      this.table = table;
      this.params = [];
      this.mode = "many";
    }

    select(columns = "*") {
      this.params.push(["select", columns]);
      return this;
    }

    eq(column, value) {
      this.params.push([column, `eq.${value}`]);
      return this;
    }

    in(column, values) {
      const safe = (values || []).map(value => String(value).replaceAll('"', '\\"'));
      this.params.push([column, `in.(${safe.join(",")})`]);
      return this;
    }

    order(column, { ascending = true, nullsFirst = false } = {}) {
      this.params.push([
        "order",
        `${column}.${ascending ? "asc" : "desc"}.${nullsFirst ? "nullsfirst" : "nullslast"}`
      ]);
      return this;
    }

    limit(value) {
      this.params.push(["limit", String(value)]);
      return this;
    }

    single() {
      this.mode = "single";
      return this;
    }

    maybeSingle() {
      this.mode = "maybeSingle";
      return this;
    }

    async execute() {
      try {
        const { response, error } = await restRequest(this.table, this.params);
        if (error) return { data: null, error };
        const rows = await response.json();
        if (!Array.isArray(rows)) return { data: null, error: new Error("Unexpected database response") };

        if (this.mode === "single") {
          return rows.length === 1
            ? { data: rows[0], error: null }
            : { data: null, error: new Error("Expected exactly one row") };
        }
        if (this.mode === "maybeSingle") {
          return rows.length <= 1
            ? { data: rows[0] || null, error: null }
            : { data: null, error: new Error("Expected zero or one row") };
        }
        return { data: rows, error: null };
      } catch (error) {
        return { data: null, error };
      }
    }

    then(resolve, reject) {
      return this.execute().then(resolve, reject);
    }
  }

  return {
    auth: {
      async getSession() {
        try {
          const session = await ensureSession();
          return { data: { session }, error: null };
        } catch (error) {
          return { data: { session: null }, error };
        }
      },

      async signInWithPassword({ email, password }) {
        try {
          const response = await authRequest("token?grant_type=password", { email, password });
          if (!response.ok) return { data: { session: null }, error: apiError(response.status, "Auth") };
          const payload = await response.json();
          const session = save(payload);
          return { data: { session, user: session.user }, error: null };
        } catch (error) {
          return { data: { session: null }, error };
        }
      },

      async signOut() {
        const current = load();
        try {
          if (current?.access_token) await authRequest("logout", undefined, current.access_token);
        } finally {
          clear();
        }
        return { error: null };
      }
    },

    from(table) {
      return new QueryBuilder(table);
    }
  };
}
