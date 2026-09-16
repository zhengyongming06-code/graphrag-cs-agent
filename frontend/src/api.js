async function parseSse(res) {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let final = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const blocks = buf.split("\n\n");
    buf = blocks.pop() || "";
    for (const block of blocks) {
      const line = block.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const ev = JSON.parse(line.slice(6));
      if (ev.type === "final") final = ev.response;
    }
  }
  return final;
}

export async function health() {
  return (await fetch("/api/health")).json();
}

export async function chat(message, sessionId) {
  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    if (res.ok && res.body) {
      const data = await parseSse(res);
      if (data?.answer) return data;
    }
  } catch {
    /* fallback */
  }
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "chat failed");
  return data;
}

export async function tickets() {
  return (await fetch("/api/tickets?limit=12")).json();
}

export async function entities() {
  return (await fetch("/api/graph/entities?limit=12")).json();
}

export async function compare(query) {
  const res = await fetch("/api/retrieve/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: 5 }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "compare failed");
  return data;
}

export async function runEval(token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Admin-Token"] = token;
  const res = await fetch("/api/eval/run", {
    method: "POST",
    headers,
    body: JSON.stringify({ mode: "both" }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "eval failed");
  return data;
}

export async function ingest(payload, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Admin-Token"] = token;
  const res = await fetch("/api/knowledge/ingest", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "ingest failed");
  return data;
}
