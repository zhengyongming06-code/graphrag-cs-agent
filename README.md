# NovaDesk GraphRAG CS Agent

面向 **Agent 实习** 的可演示商业化项目：自建知识库智能客服，核心检索层使用 **Neo4j GraphRAG**（向量检索 + 关键词 + 图谱扩展），编排层使用 **LangGraph** 多工具 Agent。

## 简历可写技术点

- Neo4j 知识图谱：`Document / Chunk / Entity`，关系 `HAS_CHUNK / MENTIONS / RELATED_TO`
- GraphRAG 混合检索：Vector Index + Lexical + Graph Expansion
- LangGraph Agent：`hybrid_search` / `entity_lookup` / `create_ticket`
- FastAPI 服务 + 客服聊天 UI + 在线入库
- Docker Compose 一键拉起 Neo4j
- 离线演示模式（无 LLM Key 也能跑检索）

## 快速开始

### 1. 启动 Neo4j

```bash
docker compose up -d
```

浏览器可打开 http://localhost:7474 （用户 `neo4j` / 密码见 `.env.example`）。

### 2. 配置环境

```bash
cp .env.example .env
# 可选：填写 LLM_API_KEY（OpenAI 兼容：OpenAI / DeepSeek / Moonshot 等）
```

### 3. 安装依赖并灌库

```bash
cd backend
python -m venv .venv
# Windows:
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

## 目录结构

```
backend/app/
  agent/          # LangGraph Agent + tools
  rag/            # Neo4j / ingest / hybrid retriever / embeddings
  main.py         # FastAPI
backend/static/   # 客服前端
data/knowledge/   # 样例知识库（NovaDesk SaaS）
eval/run_eval.py  # 简易回归评测
docker-compose.yml
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | Neo4j / LLM / 统计 |
| POST | `/api/chat` | 智能客服对话 |
| POST | `/api/knowledge/ingest` | 文本入库构图 |
| POST | `/api/knowledge/upload` | 文件入库（md/txt/pdf） |
| GET | `/api/graph/entities` | 图谱实体 |

## 评测

```bash
python eval/run_eval.py
```

## 面试讲解建议

1. 为什么用 Neo4j：客服知识不是纯扁平文档，政策/产品/故障之间有关系，图扩展能补全向量漏检。
2. Agent 为什么比单次 RAG 强：可先检索再查实体，不够时建工单转人工。
3. 可继续扩展：Reranker、多租户、对话记忆、LangSmith 观测、评测集 CI。
