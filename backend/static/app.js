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

const savedToken = localStorage.getItem("novadesk_admin_token") || "";
if (adminTokenInput) adminTokenInput.value = savedToken;

function adminHeaders(extra = {}) {
  const token = (adminTokenInput?.value || "").trim();
  if (token) localStorage.setItem("novadesk_admin_token", token);
  const headers = { ...extra };
  if (token) headers["X-Admin-Token"] = token;
  return headers;
}

function addMessage(role, content, extra = null) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = content;
  if (extra) {
    if (extra.mode) {
      const meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = `mode=${extra.mode}`;
      div.appendChild(meta);
    }
    if (extra.tool_trace && extra.tool_trace.length) {
      const box = document.createElement("div");
      box.className = "trace-list";
      extra.tool_trace.forEach((t) => {
        const item = document.createElement("div");
        item.className = "trace-item";
        item.textContent = `tool · ${t}`;
        box.appendChild(item);
      });
      div.appendChild(box);
    }
    if (extra.citations && extra.citations.length) {
      const box = document.createElement("div");
      box.className = "citations";
      extra.citations.forEach((c, i) => {
        const item = document.createElement("div");
        item.className = "cite";
        item.textContent = `[${i + 1}] ${c.title || "chunk"} · score=${c.score} · ${c.snippet}`;
        box.appendChild(item);
      });
      div.appendChild(box);
    }
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function refreshHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const neo = document.getElementById("pillNeo");
    const llm = document.getElementById("pillLlm");
    const emb = document.getElementById("pillEmb");
    neo.textContent = `Neo4j ${data.neo4j}`;
    neo.className = `pill ${data.neo4j === "up" ? "ok" : "bad"}`;
    llm.textContent = `LLM ${data.llm}`;
    llm.className = `pill ${data.llm === "configured" ? "ok" : "warn"}`;
    emb.textContent = `Emb ${data.embedding}`;
    emb.className = "pill ok";
    if (data.stats) {
      document.getElementById("statDocs").textContent = data.stats.documents ?? 0;
      document.getElementById("statChunks").textContent = data.stats.chunks ?? 0;
      document.getElementById("statEntities").textContent = data.stats.entities ?? 0;
      document.getElementById("statRels").textContent = data.stats.relations ?? 0;
    }
    const catList = document.getElementById("catList");
    catList.innerHTML = "";
    (data.categories || []).forEach((c) => {
      const chip = document.createElement("span");
      chip.className = "cat-chip";
      chip.textContent = `${c.category}: ${c.documents}`;
      catList.appendChild(chip);
    });
  } catch {
    document.getElementById("pillNeo").textContent = "API down";
    document.getElementById("pillNeo").className = "pill bad";
  }
}

async function refreshEntities() {
  try {
    const res = await fetch("/api/graph/entities?limit=12");
    if (!res.ok) return;
    const rows = await res.json();
    const list = document.getElementById("entityList");
    list.innerHTML = "";
    rows.forEach((e) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${e.name}</span><span class="type">${e.type} · d=${e.degree}</span>`;
      list.appendChild(li);
    });
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
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "chat failed");
    addMessage("bot", data.answer, data);
  } catch (err) {
    addMessage("bot", `请求失败：${err.message}`);
  } finally {
    sendBtn.disabled = false;
    refreshHealth();
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
  ingestHint.textContent = "写入中…";
  try {
    const res = await fetch("/api/knowledge/ingest", {
      method: "POST",
      headers: adminHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        title: fd.get("title"),
        content: fd.get("content"),
        source: "ui",
        category: fd.get("category") || "manual",
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "ingest failed");
    ingestHint.textContent = data.message;
    ingestForm.reset();
    if (adminTokenInput) adminTokenInput.value = localStorage.getItem("novadesk_admin_token") || "";
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
  compareOut.textContent = "对比中…";
  try {
    const res = await fetch("/api/retrieve/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: 5 }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "compare failed");
    const vec = (data.vector_only || [])
      .map((h, i) => `  ${i + 1}. [${h.channel}] ${h.title} (${h.score})`)
      .join("\n");
    const hyb = (data.hybrid_graphrag || [])
      .map((h, i) => `  ${i + 1}. [${h.channel}] ${h.title} (${h.score})`)
      .join("\n");
    compareOut.textContent =
      `${data.summary}\n\n[Vector Only]\n${vec || "  (empty)"}\n\n[Hybrid GraphRAG]\n${hyb || "  (empty)"}`;
  } catch (err) {
    compareOut.textContent = err.message;
  }
});

evalBtn.addEventListener("click", async () => {
  evalOut.textContent = "评测运行中（可能需要几十秒）…";
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
    const retrieval = data.retrieval || {};
    const lines = [
      `Agent: ${agent.passed ?? "-"}/${agent.total ?? "-"}  pass_rate=${agent.pass_rate ?? "-"}`,
      `Retrieval hybrid_unique_wins: ${retrieval.hybrid_unique_wins ?? "-"} / ${retrieval.total ?? "-"}`,
      "",
      "Agent cases:",
      ...((agent.cases || []).map((c) => `  ${c.pass ? "PASS" : "FAIL"} · ${c.q}`)),
      "",
      "Retrieval cases:",
      ...((retrieval.cases || []).map(
        (c) => `  vec=${c.vector_cover} hyb=${c.hybrid_cover} · ${c.q}`
      )),
    ];
    evalOut.textContent = lines.join("\n");
  } catch (err) {
    evalOut.textContent = err.message;
  } finally {
    evalBtn.disabled = false;
  }
});

addMessage(
  "bot",
  "你好，我是 NovaDesk GraphRAG Agent。支持：混合检索对话、纯向量 vs GraphRAG 对比、回归评测、分类知识入库。先问一个产品/政策问题，或右侧跑对比/评测。"
);
refreshHealth();
refreshEntities();
setInterval(refreshHealth, 15000);
