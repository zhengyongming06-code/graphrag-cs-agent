const messagesEl = document.getElementById("messages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const ingestForm = document.getElementById("ingestForm");
const ingestHint = document.getElementById("ingestHint");
const sessionId = crypto.randomUUID();

function addMessage(role, content, extra = null) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = content;
  if (extra) {
    if (extra.mode || (extra.tool_trace && extra.tool_trace.length)) {
      const meta = document.createElement("div");
      meta.className = "meta";
      const tools = (extra.tool_trace || []).join(" · ") || "no-tools";
      meta.textContent = `mode=${extra.mode || "?"} · ${tools}`;
      div.appendChild(meta);
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: fd.get("title"),
        content: fd.get("content"),
        source: "ui",
        category: "manual",
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "ingest failed");
    ingestHint.textContent = data.message;
    ingestForm.reset();
    refreshHealth();
    refreshEntities();
  } catch (err) {
    ingestHint.textContent = err.message;
  }
});

addMessage(
  "bot",
  "你好，我是 NovaDesk 智能客服小舟。知识库跑在 Neo4j GraphRAG 上：向量检索 + 图谱扩展 + Agent 工具调用。先问我一个产品/政策问题吧。"
);
refreshHealth();
refreshEntities();
setInterval(refreshHealth, 15000);
