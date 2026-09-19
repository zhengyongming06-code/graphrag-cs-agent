# GraphRAG 知识库客服

把 Markdown 文档写入 **Neo4j**，按问题做 **向量 + 词法 + 1-hop 图谱** 混合检索，再生成带引用的回答。证据不够或用户要转人工时，自动开票。

不是单轮 Chat + 向量库，也不是 Dify 画布。对话走 LangGraph 固定 SOP：

`memory → route → retrieve → ground → act → persist`

仓库：<https://github.com/zhengyongming06-code/graphrag-cs-agent>

## 能演示什么

1. 问「NovaDesk 有哪些核心模块？」→ 带 citation 的答案  
2. 问「Enterprise 的 SLA 首响多久？」→ 应答 5 分钟  
3. 问「转人工，登录一直失败」→ 生成 `TKT-…` 工单  
4. 调试页对比 **纯向量 vs Hybrid GraphRAG**

## 架构

```
文档 Markdown
  → 切分 Chunk + 规则抽实体
  → Neo4j: (Document)-[:HAS_CHUNK]->(Chunk)-[:MENTIONS]->(Entity)-[:RELATED_TO]-(Entity)

问题
  → LangGraph SOP
      memory    Neo4j 会话 Turn
      route     规则意图（转人工 / 政策 / 实体 / FAQ / 寒暄）
      retrieve  hybrid_search；entity 意图再 entity_lookup
      ground    词法重叠规则置信度（不是 NLI）
      act       生成回答 或 create_ticket
      persist   本轮写入图

检索
  1. Neo4j 向量索引
  2. 词法打分
  3. RRF(vector, lexical) 取 seed
  4. 1-hop: (seed)-[:MENTIONS]->(Entity)<-[:MENTIONS]-(邻接 Chunk)
  5. RRF 三路融合（k=60）
```

工具由**状态机节点调用**，不是模型自己 Function Calling。

## 自建评测（8 条，非 Ragas）

| 指标 | 纯向量 | Hybrid GraphRAG |
|------|--------|-----------------|
| keyword Hit@3 | 50% | 100% |

问答回归：8/8（答案或 citation 覆盖关键词）。详见 `eval/metrics.json`。

默认 embedding 是本地哈希向量（`USE_LOCAL_EMBEDDINGS=true`），方便离线起 Neo4j；不是线上 embedding 服务。

## 启动

需要 Docker（Neo4j）、Python 3.11+。前端可选（Node 18+）。有 DeepSeek / OpenAI 兼容 Key 才能看到完整生成；没有 Key，或模型连不上，会回落到检索片段，对话不会卡住。

```bash
copy .env.example .env          # macOS / Linux: cp .env.example .env
# 填写 LLM_API_KEY；DeepSeek：
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat

docker compose up -d neo4j
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
cd ..
python backend/scripts/seed_kb.py --reset
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

只起 Neo4j 即可，本机用 uvicorn。浏览器打开 http://127.0.0.1:8000 就是对话台。

前端（可选，端口 5173）：

```bash
cd frontend
npm install
npm run dev
```

Neo4j 浏览器：http://localhost:7475 （用户 `neo4j`，密码见 `.env.example`）。主机端口是 **7475 / 7688**，避免和本机其他 Neo4j 冲突。

```bash
python eval/run_eval.py
python -m pytest backend/tests/test_rrf.py -q
```

## 目录

```
backend/app/agent/   LangGraph SOP、门控、路由、Memory
backend/app/rag/      入库、混合检索、评测
data/knowledge/       示例文档（产品 / 登录 / 退款 / SLA）
eval/                 8 条 case + metrics.json
frontend/             React 对话台（Iconsax + SpotlightCard）
```

## 说明

这是实习作品演示：知识库是自建 NovaDesk 样例，评测集很小。图谱扩展是 **1-hop 共现**，不是多跳推理。
