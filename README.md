# NovaDesk GraphRAG CS Agent

基于 **Neo4j GraphRAG** 的企业知识库智能客服 Agent 中台：混合检索（向量 + 关键词 + 图谱扩展）+ **LangGraph** 多工具编排 + FastAPI 服务 + 可观测前端。

## 能力一览（可演示）

- GraphRAG 知识中台：`Document / Chunk / Entity` + `HAS_CHUNK / MENTIONS / RELATED_TO`
- 三路融合检索：Vector Index + Lexical + **1-hop** Graph Expansion，分数融合 **RRF(k=60)**
- LangGraph Agent：`hybrid_search` / `entity_lookup` / `create_ticket`
- **检索 A/B 对比**：纯向量 vs Hybrid GraphRAG（`/api/retrieve/compare`）
- **回归评测**：Agent 命中率 + 检索覆盖对比（`/api/eval/run`）
- **多分类知识库**：product / support / billing / sla …
- **管理鉴权**：写接口支持 `X-Admin-Token`（`APP_SECRET`）
- Citation 引用 + Tool Trace 可观测
- Docker Compose 一键拉起 Neo4j

## 快速开始

### 1. 启动 Neo4j

```bash
docker compose up -d
```

浏览器：http://localhost:7475 （用户 `neo4j` / 密码见 `.env.example`）  
> 默认映射主机 `7475/7688`，避免与本机其他 Neo4j 冲突。

### 2. 配置环境

```bash
cp .env.example .env
# 填写 LLM_API_KEY（DeepSeek / OpenAI 兼容均可）
# 可选：修改 APP_SECRET，启用入库/评测鉴权
```

### 3. 安装依赖并灌库

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
python backend/scripts/seed_kb.py
```

### 4. 启动服务

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 http://127.0.0.1:8000

## 实测指标（自建 8 条评测集）

```bash
python eval/run_eval.py
```

结果写入 `eval/metrics.json`。

| 指标 | 数值 | 说明 |
|------|------|------|
| Hit@3 纯向量 | 50% | Top-3 是否覆盖金标关键词/文档 |
| Hit@3 Hybrid GraphRAG | 100% | Vector + Lexical + 1-hop + RRF |
| Hit@3 提升 | +50pp | 相对纯向量 |
| 检索 P95 | ~45ms | 不含 LLM |
| 端到端对话 P95 | ~5.0s | 含 DeepSeek Tool Calling |
| Agent 事实命中 | 8/8 | 答案或引用含关键事实 |

这是自建 **keyword Hit@3**，不是 Ragas Faithfulness，面试不要混称。

## 关键 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | Neo4j / LLM / 分类统计 |
| POST | `/api/chat` | Agent 对话 |
| POST | `/api/retrieve/compare` | 纯向量 vs GraphRAG 对比 |
| POST | `/api/eval/run` | 回归评测（agent/retrieval/both） |
| GET | `/api/knowledge/categories` | 知识库分类 |
| GET | `/api/knowledge/documents` | 文档列表 |
| POST | `/api/knowledge/ingest` | 文本入库（可鉴权） |

## 评测

```bash
python eval/run_eval.py
# 或在前端点击「运行评测」
```

报告输出：`eval/last_report.json`

## 目录结构

```
backend/app/
  agent/          # LangGraph Agent + tools
  rag/            # Neo4j / ingest / hybrid / eval_suite
  main.py         # FastAPI
backend/static/   # 中台前端（对话/对比/评测）
data/knowledge/   # 样例知识库
eval/             # cases + reports
docker-compose.yml
```

## 设计说明

1. 客服知识有关系结构，Graph Expansion 可补纯向量漏检。  
2. Agent 比单次 RAG 更适合多步决策与转人工。  
3. A/B 对比与评测集，方便面试时讲清「为什么 Hybrid 更好」。  
