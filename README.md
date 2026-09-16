# 知识库客服

把文档放进 Neo4j，按问题做 **向量 + 关键词 + 图谱** 检索，再生成带引用的回答。答不上来可以转人工工单。

## 启动

```bash
cp .env.example .env
docker compose up -d neo4j
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
python backend/scripts/seed_kb.py --reset
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开前端（先起 API，再起 UI）：

```bash
cd frontend
npm install
npm run dev
```

浏览器 http://127.0.0.1:5173 （图标 Iconsax，卡片动效用了 React Bits 的 SpotlightCard）

打包进 FastAPI：

```bash
cd frontend
npm run build
```

然后只开 http://127.0.0.1:8000 即可。

示例文档在 `data/knowledge/`。评测：`python eval/run_eval.py`。
