import { useEffect, useRef, useState } from "react";
import {
  MessageText,
  Ticket,
  Setting2,
  Send2,
  DocumentText,
  Graph,
  SearchNormal,
  Add,
} from "iconsax-react";
import SpotlightCard from "./bits/SpotlightCard.jsx";
import * as api from "./api.js";

const QUICK = [
  { q: "NovaDesk 有哪些核心模块？", label: "产品" },
  { q: "登录失败怎么排查？", label: "登录" },
  { q: "退款政策是什么？", label: "退款" },
  { q: "Enterprise 的 SLA 首响多久？", label: "SLA" },
  { q: "转人工，登录一直失败", label: "转人工" },
];

export default function App() {
  const [tab, setTab] = useState("chat");
  const [health, setHealth] = useState({});
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([
    { role: "bot", content: "知识库客服。产品、登录、退款、SLA 可以直接问。" },
  ]);
  const [ticketRows, setTicketRows] = useState([]);
  const [entityRows, setEntityRows] = useState([]);
  const [compareOut, setCompareOut] = useState("");
  const [evalOut, setEvalOut] = useState("");
  const [ingestHint, setIngestHint] = useState("");
  const sessionId = useRef(crypto.randomUUID());
  const listRef = useRef(null);

  async function refresh() {
    try {
      const h = await api.health();
      setHealth(h);
      setTicketRows(await api.tickets());
      setEntityRows(await api.entities());
    } catch {
      setHealth({ neo4j: "down" });
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 20000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo(0, listRef.current.scrollHeight);
  }, [messages]);

  async function send(text) {
    const message = (text || input).trim();
    if (!message || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setBusy(true);
    try {
      const data = await api.chat(message, sessionId.current);
      setMessages((m) => [...m, { role: "bot", content: data.answer, extra: data }]);
      refresh();
    } catch (err) {
      setMessages((m) => [...m, { role: "bot", content: `没发出去：${err.message}` }]);
    } finally {
      setBusy(false);
    }
  }

  const icon = { size: 18, variant: "Linear", color: "currentColor" };

  return (
    <>
      <header className="top">
        <div className="brand">
          <MessageText {...icon} variant="Bold" />
          <div>
            <strong>知识库客服</strong>
            <span className="dim">文档检索问答</span>
          </div>
        </div>
        <nav className="tabs">
          <button className={tab === "chat" ? "on" : ""} onClick={() => setTab("chat")}>
            <MessageText {...icon} /> 对话
          </button>
          <button className={tab === "tickets" ? "on" : ""} onClick={() => setTab("tickets")}>
            <Ticket {...icon} /> 工单
          </button>
          <button className={tab === "debug" ? "on" : ""} onClick={() => setTab("debug")}>
            <Setting2 {...icon} /> 调试
          </button>
        </nav>
        <div className="status">
          <span>Neo4j {health.neo4j || "…"}</span>
          <span>LLM {health.llm || "…"}</span>
        </div>
      </header>

      {tab === "chat" && (
        <main className="page chat-page">
          <SpotlightCard className="chat-shell" spotlightColor="rgba(31, 77, 58, 0.1)">
            <div className="messages" ref={listRef}>
              {messages.map((msg, i) => (
                <article key={i} className={`msg ${msg.role}`}>
                  <div>{msg.content}</div>
                  {msg.extra?.ticket_id && <div className="meta">{msg.extra.ticket_id}</div>}
                  {msg.extra?.pipeline?.length > 0 && (
                    <details className="pipe">
                      <summary>过程</summary>
                      {msg.extra.pipeline.map((s) => s.step).join(" → ")}
                    </details>
                  )}
                  {msg.extra?.citations?.map((c, j) => (
                    <div key={j} className="cite">
                      [{j + 1}] {(c.title || "")} {(c.snippet || "").slice(0, 160)}
                    </div>
                  ))}
                </article>
              ))}
              {busy && (
                <article className="msg bot">
                  <div>正在检索知识库…</div>
                </article>
              )}
            </div>
            <div className="quick">
              {QUICK.map((item) => (
                <button key={item.label} type="button" onClick={() => send(item.q)}>
                  {item.label}
                </button>
              ))}
            </div>
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="问知识库里的问题"
                required
              />
              <button type="submit" disabled={busy}>
                <Send2 {...icon} color="#f8faf7" />
                发送
              </button>
            </form>
          </SpotlightCard>
        </main>
      )}

      {tab === "tickets" && (
        <main className="page">
          <h1>
            <Ticket {...icon} /> 工单
          </h1>
          <p className="dim">转人工会记在这里。</p>
          <ul className="tickets">
            {ticketRows.length === 0 && <li className="dim">还没有工单</li>}
            {ticketRows.map((t) => (
              <li key={t.id}>
                <strong>{t.id}</strong> · {t.status}
                <div className="dim">{t.subject}</div>
              </li>
            ))}
          </ul>
        </main>
      )}

      {tab === "debug" && (
        <main className="page debug-grid">
          <SpotlightCard>
            <section className="pad">
              <h2>
                <Graph {...icon} /> 库
              </h2>
              <p>
                文档 {health.stats?.documents ?? 0} · 片段 {health.stats?.chunks ?? 0} · 实体{" "}
                {health.stats?.entities ?? 0}
              </p>
              <ul>
                {entityRows.map((e) => (
                  <li key={e.id || e.name}>
                    {e.name} <span className="dim">{e.type}</span>
                  </li>
                ))}
              </ul>
            </section>
          </SpotlightCard>
          <SpotlightCard>
            <section className="pad">
              <h2>
                <SearchNormal {...icon} /> 向量 vs 图谱
              </h2>
              <form
                className="stack"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const q = e.target.query.value.trim();
                  if (!q) return;
                  setCompareOut("…");
                  try {
                    const data = await api.compare(q);
                    const vec = (data.vector_only || [])
                      .map((h, i) => `${i + 1}. ${h.title} [${h.channel}]`)
                      .join("\n");
                    const hyb = (data.hybrid_graphrag || [])
                      .map((h, i) => `${i + 1}. ${h.title} [${h.channel}]`)
                      .join("\n");
                    setCompareOut(`${data.summary}\n\n向量\n${vec}\n\n混合\n${hyb}`);
                  } catch (err) {
                    setCompareOut(err.message);
                  }
                }}
              >
                <input name="query" placeholder="例如：Enterprise SLA" required />
                <button type="submit">对比</button>
              </form>
              <pre>{compareOut}</pre>
            </section>
          </SpotlightCard>
          <SpotlightCard>
            <section className="pad">
              <h2>
                <DocumentText {...icon} /> 评测
              </h2>
              <button
                type="button"
                onClick={async () => {
                  setEvalOut("在跑…");
                  try {
                    const data = await api.runEval(localStorage.getItem("kb_admin_token") || "");
                    const agent = data.agent || {};
                    const r = data.retrieval || {};
                    setEvalOut(
                      [
                        `问答 ${agent.passed ?? "-"}/${agent.total ?? "-"}`,
                        `Hit@3 向量=${r["vector_hit_rate@3"] ?? "-"} 混合=${r["hybrid_hit_rate@3"] ?? "-"}`,
                        ...(agent.cases || []).map((c) => `${c.pass ? "ok" : "fail"}  ${c.q}`),
                      ].join("\n")
                    );
                  } catch (err) {
                    setEvalOut(err.message);
                  }
                }}
              >
                跑一遍
              </button>
              <pre>{evalOut}</pre>
            </section>
          </SpotlightCard>
          <SpotlightCard>
            <section className="pad">
              <h2>
                <Add {...icon} /> 补一条知识
              </h2>
              <form
                className="stack"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const fd = new FormData(e.target);
                  const token = (fd.get("adminToken") || "").toString().trim();
                  if (token) localStorage.setItem("kb_admin_token", token);
                  setIngestHint("在写…");
                  try {
                    const data = await api.ingest(
                      {
                        title: fd.get("title"),
                        content: fd.get("content"),
                        source: "ui",
                        category: fd.get("category") || "support",
                      },
                      token
                    );
                    setIngestHint(data.message);
                    e.target.reset();
                    refresh();
                  } catch (err) {
                    setIngestHint(err.message);
                  }
                }}
              >
                <input name="title" placeholder="标题" required />
                <select name="category" defaultValue="support">
                  <option value="product">产品</option>
                  <option value="support">排障</option>
                  <option value="billing">退款</option>
                  <option value="sla">SLA</option>
                </select>
                <textarea name="content" rows={4} required />
                <input name="adminToken" placeholder="X-Admin-Token，空则用默认 change-me-in-production" />
                <button type="submit">写入</button>
                <p className="dim">{ingestHint}</p>
              </form>
            </section>
          </SpotlightCard>
        </main>
      )}
    </>
  );
}
