const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const ingestForm = document.getElementById("ingestForm");
const ingestHint = document.getElementById("ingestHint");
const compareForm = document.getElementById("compareForm");
const compareOut = document.getElementById("compareOut");
const evalBtn = document.getElementById("evalBtn");
const evalOut = document.getElementById("evalOut");
const adminTokenInput = document.getElementById("adminToken");
const sessionId = crypto.randomUUID();

const savedToken = localStorage.getItem("sage_admin_token") || "";
if (adminTokenInput) adminTokenInput.value = savedToken;

document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
    const tab = btn.dataset.tab;
    document.querySelectorAll(".page").forEach((p) => p.classList.add("hidden"));
    document.getElementById(`tab-${tab}`).classList.remove("hidden");
  });
});

function adminHeaders(extra = {}) {
  const token = (adminTokenInput?.value || "").trim();
  if (token) localStorage.setItem("sage_admin_token", token);
  const headers = { ...extra };
  headers["X-Admin-Token"] = token || "change-me-in-production";
  return headers;
}

function addMessage(role, content, extra = null) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const body = document.createElement("div");
  body.textContent = content;
  div.appendChild(body);
  if (extra) {
    if (extra.ticket_id) {
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = extra.ticket_id;
      div.appendChild(meta);
    }
    if (extra.pipeline && extra.pipeline.length) {
      const det = document.createElement("details");
      det.className = "pipe";
      det.innerHTML = `<summary>过程</summary>${extra.pipeline.map((s) => s.step).join(" → ")}`;
      div.appendChild(det);
    }
    if (extra.citations && extra.citations.length) {
      extra.citations.forEach((c, i) => {
        const item = document.createElement("div");
        item.className = "cite";
        item.textContent = `[${i + 1}] ${c.title || ""} ${c.snippet || ""}`.slice(0, 220);
        div.appendChild(item);
      });
    }
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function parseSseResponse(res) {
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

async function sendChat(message) {
  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    if (res.ok && res.body) {
      const data = await parseSseResponse(res);
      if (data && data.answer) return data;
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

async function refreshHealth() {
  try {
    const data = await (await fetch("/api/health")).json();
    document.getElementById("pillNeo").textContent = `Neo4j ${data.neo4j}`;
    document.getElementById("pillLlm").textContent = `LLM ${data.llm}`;
    const s = data.stats || {};
    const line = document.getElementById("statsLine");
    if (line) {
      line.textContent = `文档 ${s.documents ?? 0} · 片段 ${s.chunks ?? 0} · 实体 ${s.entities ?? 0}`;
    }
    const catList = document.getElementById("catList");
    if (catList) {
      catList.textContent = (data.categories || []).map((c) => `${c.category} ${c.documents}`).join("  ");
    }
  } catch {
    document.getElementById("pillNeo").textContent = "API 挂了";
  }
}

async function refreshEntities() {
  try {
    const rows = await (await fetch("/api/graph/entities?limit=12")).json();
    const list = document.getElementById("entityList");
    if (!list) return;
    list.innerHTML = rows.map((e) => `<li>${e.name} <span class="dim">${e.type}</span></li>`).join("");
  } catch {
    /* ignore */
  }
}

async function refreshTickets() {
  const list = document.getElementById("ticketList");
  if (!list) return;
  try {
    const rows = await (await fetch("/api/tickets?limit=12")).json();
    if (!rows.length) {
      list.innerHTML = "<li class='dim'>还没有工单</li>";
      return;
    }
    list.innerHTML = rows
      .map((t) => `<li><strong>${t.id}</strong> · ${t.status}<div class="dim">${t.subject || ""}</div></li>`)
      .join("");
  } catch {
    /* ignore */
  }
}

chatForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  addMessage("user", message);
  chatInput.value = "";
  sendBtn.disabled = true;
  try {
    const data = await sendChat(message);
    addMessage("bot", data.answer, data);
  } catch (err) {
    addMessage("bot", `没发出去：${err.message}`);
  } finally {
    sendBtn.disabled = false;
    refreshHealth();
    refreshTickets();
  }
});

document.querySelectorAll(".quick button").forEach((btn) => {
  btn.addEventListener("click", () => {
    chatInput.value = btn.dataset.q;
    chatForm.requestSubmit();
  });
});

ingestForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const fd = new FormData(ingestForm);
  ingestHint.textContent = "在写…";
  try {
    const res = await fetch("/api/knowledge/ingest", {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        title: fd.get("title"),
        content: fd.get("content"),
        source: "ui",
        category: fd.get("category") || "support",
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "ingest failed");
    ingestHint.textContent = data.message;
    ingestForm.reset();
    if (adminTokenInput) adminTokenInput.value = localStorage.getItem("sage_admin_token") || "";
    refreshHealth();
    refreshEntities();
  } catch (err) {
    ingestHint.textContent = err.message;
  }
});

compareForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const query = document.getElementById("compareQuery").value.trim();
  if (!query) return;
  compareOut.textContent = "…";
  try {
    const res = await fetch("/api/retrieve/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: 5 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "compare failed");
    const vec = (data.vector_only || []).map((h, i) => `${i + 1}. ${h.title} [${h.channel}]`).join("\n");
    const hyb = (data.hybrid_graphrag || []).map((h, i) => `${i + 1}. ${h.title} [${h.channel}]`).join("\n");
    compareOut.textContent = `${data.summary}\n\n向量\n${vec}\n\n混合\n${hyb}`;
  } catch (err) {
    compareOut.textContent = err.message;
  }
});

evalBtn.addEventListener("click", async () => {
  evalOut.textContent = "在跑…";
  evalBtn.disabled = true;
  try {
    const res = await fetch("/api/eval/run", {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ mode: "both" }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    const agent = data.agent || {};
    const r = data.retrieval || {};
    evalOut.textContent = [
      `问答 ${agent.passed ?? "-"}/${agent.total ?? "-"}`,
      `Hit@3 向量=${r["vector_hit_rate@3"] ?? "-"} 混合=${r["hybrid_hit_rate@3"] ?? "-"}`,
      ...(agent.cases || []).map((c) => `${c.pass ? "ok" : "fail"}  ${c.q}`),
    ].join("\n");
  } catch (err) {
    evalOut.textContent = err.message;
  } finally {
    evalBtn.disabled = false;
  }
});

addMessage("bot", "知识库客服。产品、登录、退款、SLA 可以直接问，答不上来就转人工。");
refreshHealth();
refreshEntities();
refreshTickets();
setInterval(() => {
  refreshHealth();
  refreshTickets();
}, 20000);
