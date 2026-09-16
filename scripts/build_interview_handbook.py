# -*- coding: utf-8 -*-
"""Generate AI Agent internship interview study handbook (DOCX + PDF)."""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT_DOCX = Path(r"d:\Desktop\AI-Agent实习面试学习手册.docx")
OUT_PDF = Path(r"d:\Desktop\AI-Agent实习面试学习手册.pdf")


def set_run_font(run, name="微软雅黑", size=10.5, bold=False, color=None):
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if color is not None:
        run.font.color.rgb = color


def p_fmt(p, before=2, after=4, line=1.2):
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = line


def add_title(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fmt(p, 0, 6)
    set_run_font(p.add_run(text), size=18, bold=True)


def add_subtitle(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fmt(p, 0, 10)
    set_run_font(p.add_run(text), size=10, color=RGBColor(0x55, 0x65, 0x7A))


def add_h1(doc, text):
    p = doc.add_paragraph()
    p_fmt(p, 14, 6)
    set_run_font(p.add_run(text), size=14, bold=True, color=RGBColor(0x1F, 0x3A, 0x5F))
    pPr = p._p.get_or_add_pPr()
    pBdr = pPr.makeelement(qn("w:pBdr"), {})
    bottom = pBdr.makeelement(
        qn("w:bottom"),
        {qn("w:val"): "single", qn("w:sz"): "12", qn("w:space"): "1", qn("w:color"): "2DD4BF"},
    )
    pBdr.append(bottom)
    pPr.append(pBdr)


def add_h2(doc, text):
    p = doc.add_paragraph()
    p_fmt(p, 10, 4)
    set_run_font(p.add_run(text), size=12, bold=True, color=RGBColor(0x0F, 0x76, 0x6E))


def add_h3(doc, text):
    p = doc.add_paragraph()
    p_fmt(p, 8, 3)
    set_run_font(p.add_run(text), size=11, bold=True)


def add_body(doc, text, bold=False, size=10.5):
    p = doc.add_paragraph()
    p_fmt(p)
    set_run_font(p.add_run(text), size=size, bold=bold)


def add_bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    p_fmt(p, 1, 2)
    p.clear()
    if bold_prefix:
        set_run_font(p.add_run(bold_prefix), size=10.5, bold=True)
        set_run_font(p.add_run(text), size=10.5)
    else:
        set_run_font(p.add_run(text), size=10.5)


def add_qa(doc, q, a):
    p = doc.add_paragraph()
    p_fmt(p, 6, 2)
    set_run_font(p.add_run("Q：" + q), size=10.5, bold=True)
    p2 = doc.add_paragraph()
    p_fmt(p2, 0, 4)
    set_run_font(p2.add_run("A：" + a), size=10.5)


def add_codeish(doc, text):
    p = doc.add_paragraph()
    p_fmt(p, 2, 4, 1.15)
    run = p.add_run(text)
    set_run_font(run, name="Consolas", size=9)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")


def build():
    doc = Document()
    for s in doc.sections:
        s.top_margin = Cm(1.5)
        s.bottom_margin = Cm(1.5)
        s.left_margin = Cm(1.7)
        s.right_margin = Cm(1.7)

    add_title(doc, "AI Agent 实习面试学习手册")
    add_subtitle(
        doc,
        "结合项目：知识库 GraphRAG 客服  |  github.com/zhengyongming06-code/graphrag-cs-agent",
    )
    add_body(
        doc,
        "使用说明：先把第1–2章背熟（项目口述+链路），再刷第3–6章问答；第7章当查词表，第8章入职第一周对照做。",
        bold=True,
    )

    # ========== 1 ==========
    add_h1(doc, "一、2 分钟项目口述稿（必背）")
    add_body(
        doc,
        "我做了一个可本地运行的企业知识库智能客服 Agent。知识存在 Neo4j 里，做成 GraphRAG："
        "文档切成 Chunk 并向量化，同时抽实体建图。用户提问时，Agent 用 LangGraph 决定调用工具——"
        "先做向量+关键词+图谱扩展的混合检索，必要时查实体关系；证据够了再生成回答并带引用，"
        "不够就创建工单转人工。后端是 FastAPI，模型接 DeepSeek，Neo4j 用 Docker 启动，"
        "仓库可以直接跑起来演示。",
    )
    add_h2(doc, "30 秒精简版")
    add_body(
        doc,
        "自研 GraphRAG 客服 Agent：Neo4j 存知识图谱，LangGraph 做工具调用，"
        "混合检索后带引用回答，支持转人工；FastAPI + Docker 可演示。",
    )
    add_h2(doc, "口述时主动抛出的 4 个技术点")
    add_bullet(doc, "数据模型：Document / Chunk / Entity，关系 HAS_CHUNK、MENTIONS、RELATED_TO")
    add_bullet(doc, "检索：Vector Index + Lexical + Graph Expansion 融合")
    add_bullet(doc, "Agent 工具：hybrid_search / entity_lookup / create_ticket")
    add_bullet(doc, "工程：FastAPI、Docker Compose、引用 citation、工具轨迹 trace")

    # ========== 2 ==========
    add_h1(doc, "二、核心链路一张图（闭眼能画）")
    add_h2(doc, "2.1 RAG 标准链路")
    add_codeish(
        doc,
        "文档 → 清洗/切分(Chunk) → Embedding → 写入向量/图库\n"
        "用户问题 → Embedding → 检索 Top-K → 拼 Prompt → LLM → 回答(+引用)",
    )
    add_h2(doc, "2.2 你项目的 GraphRAG + Agent 链路")
    add_codeish(
        doc,
        "问题\n  → LangGraph Agent\n    → hybrid_search（向量+关键词+图谱扩展）\n"
        "    → entity_lookup（查实体与邻居）\n    →（可选）create_ticket\n"
        "  → 基于证据生成回答 + citations\n  → 证据不足则拒答/转人工",
    )
    add_h2(doc, "2.3 为什么要 Agent，而不是一次 RAG？")
    add_bullet(doc, "一次 RAG：固定“检索→生成”，不会中途改策略。")
    add_bullet(doc, "Agent：可多步决策——先搜、不够再查实体、仍不够再转人工。")
    add_bullet(doc, "客服场景经常需要“查关系/查政策/建工单”，适合工具调用。")

    # ========== 3 ==========
    add_h1(doc, "三、必须吃透的基础概念")
    add_h2(doc, "3.1 LLM 基础")
    add_bullet(doc, "Token：模型计费和上下文的基本单位；上下文有上限，检索结果不能无限塞。", None)
    add_bullet(doc, "Temperature：越高越随机；客服/问答通常偏低（更稳）。")
    add_bullet(doc, "幻觉：模型编造事实。对策：先检索、强制引用、无证据拒答、工具拿真数据。")
    add_bullet(doc, "OpenAI 兼容接口：很多国产模型（如 DeepSeek）可用同一套 Chat Completions / Tool Calling 协议。")

    add_h2(doc, "3.2 Embedding 与向量检索")
    add_bullet(doc, "Embedding：把文本映射成向量，语义相近则向量接近。")
    add_bullet(doc, "相似度：常用余弦相似度（cosine）。")
    add_bullet(doc, "Top-K：取最相近的 K 条 Chunk 作为证据。")
    add_bullet(doc, "局限：纯向量可能漏掉精确专有名词/编号；所以要混合关键词检索。")

    add_h2(doc, "3.3 Chunk（切分）")
    add_bullet(doc, "太短：丢上下文；太长：噪声多、占 Token。")
    add_bullet(doc, "常用：按段落/标题切，设 chunk_size 与 overlap（重叠）。")
    add_bullet(doc, "面试口径：先保证语义完整，再用重叠减少边界切断。")

    add_h2(doc, "3.4 混合检索 Hybrid")
    add_bullet(doc, "稠密检索（向量）：懂语义，如“退钱规则”≈“退款政策”。")
    add_bullet(doc, "稀疏检索（关键词/BM25）：抓专名、型号、政策原文用词。")
    add_bullet(doc, "融合：两边结果合并去重、加权打分，再取 Top-K。")

    add_h2(doc, "3.5 GraphRAG / 知识图谱")
    add_bullet(doc, "图 = 节点（实体）+ 边（关系）。适合表达产品-政策-故障之间的关联。")
    add_bullet(doc, "你的做法：Chunk MENTIONS Entity；Entity RELATED_TO Entity；再从命中 Chunk 扩展邻居 Chunk。")
    add_bullet(doc, "价值：向量找到入口后，沿关系把相关政策/模块补全，减少“只答一半”。")
    add_bullet(doc, "不要吹“全面知识推理”；如实说是检索增强，不是强推理引擎。")

    add_h2(doc, "3.6 Prompt Engineering")
    add_bullet(doc, "System：角色、边界、格式、拒答规则。")
    add_bullet(doc, "User：当前问题。")
    add_bullet(doc, "中间：检索证据（带编号），要求按证据回答并标注 [1][2]。")
    add_bullet(doc, "好 Prompt 特征：约束清晰、输出结构固定、失败时有行为（转人工）。")

    add_h2(doc, "3.7 Tool Calling / Function Calling")
    add_bullet(doc, "模型不直接执行代码，而是输出：要调哪个工具 + 参数。")
    add_bullet(doc, "你的程序执行工具，把结果作为 tool 消息返回，模型再继续生成。")
    add_bullet(doc, "典型循环：Thought/Action/Observation（ReAct 思想）。")
    add_bullet(doc, "注意：tool 消息必须对应前面的 tool_calls，顺序乱了会 400（你项目修过）。")

    add_h2(doc, "3.8 LangGraph（概念）")
    add_bullet(doc, "把 Agent 做成状态图：节点（agent/tools）+ 边（条件跳转）。")
    add_bullet(doc, "messages 用 add_messages 归约，追加而不是整表覆盖。")
    add_bullet(doc, "停止条件：模型不再发起 tool_calls，就输出最终回答。")

    add_h2(doc, "3.9 Neo4j / Cypher 最低限度")
    add_bullet(doc, "MATCH 查询；MERGE 有则复用无则创建；SET 写属性；RETURN 返回。")
    add_codeish(
        doc,
        "// 查实体\nMATCH (e:Entity) WHERE e.name CONTAINS 'SLA' RETURN e LIMIT 10\n\n"
        "// 从 Chunk 看提到的实体\nMATCH (c:Chunk)-[:MENTIONS]->(e:Entity)\n"
        "WHERE c.id = $id RETURN e.name, e.type",
    )

    add_h2(doc, "3.10 工程与部署")
    add_bullet(doc, "FastAPI：REST API；/health、/chat、/knowledge/ingest。")
    add_bullet(doc, ".env：密钥、模型地址、Neo4j 连接；绝不提交到 Git。")
    add_bullet(doc, "Docker Compose：一键起 Neo4j；注意端口冲突。")
    add_bullet(doc, "日志：看 uvicorn traceback；先复现再改。")

    # ========== 4 ==========
    add_h1(doc, "四、项目深挖问答（最高频）")
    add_qa(
        doc,
        "为什么用 Neo4j 而不是只用 Chroma/FAISS？",
        "客服知识有结构化关系（模块-SLA-退款政策）。纯向量擅长语义相似，弱于关系跳转。"
        "Neo4j 既能存 Chunk 向量，又能存实体关系，便于图谱扩展补全证据。",
    )
    add_qa(
        doc,
        "你们 GraphRAG 具体怎么检索？",
        "三路：① Neo4j 向量索引查相似 Chunk；② 关键词/词面重叠打分；③ 从命中 Chunk 经 MENTIONS 跳到共现实体再找邻居 Chunk。"
        "最后融合排序取 Top-K 给 Agent。",
    )
    add_qa(
        doc,
        "实体怎么抽的？有没有用大模型抽取？",
        "当前是规则/词典型抽取（产品名、套餐、SLA、常见故障词等），成本低、可控、易演示。"
        "若继续迭代，可换成 LLM 抽取三元组，但要加校验与去重，避免图谱噪声。",
    )
    add_qa(
        doc,
        "如何降低幻觉？",
        "① 先工具检索再答；② Prompt 要求依据证据并引用；③ 无命中则说明不确定并转人工；"
        "④ 工单工具写入 Neo4j，避免模型假装已处理。",
    )
    add_qa(
        doc,
        "Agent 有哪些工具？为什么这样拆？",
        "hybrid_search 负责找证据；entity_lookup 负责图上的关系问题；create_ticket 负责无法闭环时的业务动作。"
        "拆分是为了单一职责，便于追踪 tool_trace。",
    )
    add_qa(
        doc,
        "没有 LLM Key 时系统怎么跑？",
        "离线模式：仍走 Neo4j 混合检索，把命中片段整理返回，用于演示检索链路；配置 DeepSeek 后切换到 LangGraph Agent。",
    )
    add_qa(
        doc,
        "如何评价效果？",
        "做了简易回归 case（产品模块、登录、退款、SLA 等），检查答案或 citation 是否覆盖关键点。"
        "进阶可加：检索命中率、拒答准确率、人工满意度；这是可坦白的后续工作。",
    )
    add_qa(
        doc,
        "最大难点/踩坑？",
        "LangGraph 消息状态若整表覆盖，tool 消息顺序会坏，DeepSeek 返回 400。"
        "修复是用 add_messages，节点只返回增量消息。另外本机 Neo4j 端口冲突，改到 7475/7688。",
    )
    add_qa(
        doc,
        "如果让你继续做两周，做什么？",
        "① 加 rerank；② 多轮会话摘要 Memory；③ LLM 实体抽取+人工校验；"
        "④ 更完整评测集与 CI；⑤ 观测（延迟/token/工具失败率）。",
    )
    add_qa(
        doc,
        "和 LangChain 模板项目有什么不同？",
        "不是只调库演示：有独立图谱模型、混合检索实现、可运行服务与 UI、入库与工单落库、可公开仓库。",
    )

    # ========== 5 ==========
    add_h1(doc, "五、通用面试题（RAG / Agent / 工程）")
    add_h2(doc, "5.1 RAG 类")
    add_qa(
        doc,
        "RAG 解决什么问题？",
        "把私有/最新知识通过检索注入 Prompt，减少模型靠参数“瞎编”，并提高可追溯性。",
    )
    add_qa(
        doc,
        "检索差怎么排查？",
        "看切分是否切坏；Embedding 模型是否匹配语言；Top-K 是否过小；是否缺关键词通道；"
        "query 是否改写；是否需要路由到不同知识库。",
    )
    add_qa(
        doc,
        "召回和精排区别？",
        "召回：从大库快速找候选；精排：对候选精细打分（交叉编码器/业务规则）再送给 LLM。",
    )
    add_qa(
        doc,
        "如何防止 Prompt 注入？",
        "工具权限最小化；系统指令与用户输入隔离；对工具参数校验；敏感操作二次确认；检索内容当数据不当指令。",
    )

    add_h2(doc, "5.2 Agent 类")
    add_qa(
        doc,
        "什么时候上 Agent，什么时候普通 RAG 就够？",
        "单次问答+固定知识：RAG 够。需要多步、调 API、分支决策、人机协作：上 Agent。",
    )
    add_qa(
        doc,
        "Agent 死循环怎么办？",
        "限制最大步数；重复工具调用熔断；超时；强制结束并转人工。",
    )
    add_qa(
        doc,
        "多 Agent 了解吗？",
        "知道有分工（检索Agent/写作Agent），但实习项目应先把单 Agent 工具闭环做稳；"
        "多 Agent 增加协调成本，不先吹这个。",
    )

    add_h2(doc, "5.3 工程类")
    add_qa(
        doc,
        "密钥怎么管理？",
        "放环境变量/.env，不进仓库；不同环境不同密钥；泄露立即轮换（聊天里发过 Key 要换）。",
    )
    add_qa(
        doc,
        "如何做流式输出？",
        "SSE/WebSocket 把 token 推到前端；注意工具调用阶段先不流式最终答案，或分阶段展示状态。",
    )
    add_qa(
        doc,
        "延迟高怎么优化？",
        "减少重复检索；缓存热问；并行工具；缩小 Prompt；更小/更快模型做路由；异步IO。",
    )
    add_qa(
        doc,
        "如何跟业务同学协作？",
        "先对齐知识来源与拒答边界；用真实工单/FAQ 做评测集；上线灰度；坏case回流改知识库或规则。",
    )

    # ========== 6 ==========
    add_h1(doc, "六、行为面 / 实习面常见问法")
    add_qa(
        doc,
        "为什么投 Agent 实习？",
        "喜欢把模型接到真实业务闭环。已经独立做出可演示 GraphRAG 客服，想在真实数据与规范下继续打磨检索、评测与工程化。",
    )
    add_qa(
        doc,
        "遇到不会的怎么办？",
        "先最小复现+查文档/日志；形成 1–2 个方案再问导师，问法带上下文与取舍，不空手问“怎么做”。",
    )
    add_qa(
        doc,
        "能实习多久 / 每周到岗？",
        "按真实情况答，别夸大。强调可远程联调、沟通响应快。",
    )
    add_qa(
        doc,
        "项目是否抄的？",
        "架构参考业界常见 GraphRAG/Agent 思路，但数据模型、检索融合、服务与前端是自己实现并可演示；能指着仓库讲代码。",
    )
    add_h2(doc, "不会就诚实说的句式")
    add_body(
        doc,
        "“这块我还没在生产落过，我目前理解是……；若在团队里我会先……验证。”"
        "——有边界、有理解、有行动，比硬编强。",
    )

    # ========== 7 ==========
    add_h1(doc, "七、名词速查表（复习用）")
    pairs = [
        ("RAG", "检索增强生成：先查资料再生成"),
        ("GraphRAG", "用知识图谱增强的 RAG（实体关系扩展）"),
        ("Embedding", "文本向量化"),
        ("Chunk", "文档切分后的片段"),
        ("Top-K", "取相似度最高的 K 条"),
        ("Hybrid Search", "向量 + 关键词等混合检索"),
        ("Rerank", "对初检结果精排"),
        ("Tool Calling", "模型选择并调用外部工具"),
        ("ReAct", "推理-行动-观察循环"),
        ("LangGraph", "用图状态机编排 Agent"),
        ("Cypher", "Neo4j 查询语言"),
        ("Hallucination", "幻觉：编造事实"),
        ("Citation/Grounding", "回答锚定到证据/引用"),
        ("Memory", "多轮对话记忆（原聊天/摘要/向量记忆）"),
        ("Guardrail", "安全与拒答约束"),
        ("SSE", "服务端推流，常用于流式回答"),
        ("Latency", "延迟"),
        ("Eval", "评测"),
    ]
    for k, v in pairs:
        add_bullet(doc, f"：{v}", bold_prefix=k)

    # ========== 8 ==========
    add_h1(doc, "八、入职第一周生存清单")
    add_bullet(doc, "Day1：跑通环境；找到对话入口、配置、日志位置；能发一版改动。")
    add_bullet(doc, "Day2：画出现有系统架构图（自己画一遍比看文档更管用）。")
    add_bullet(doc, "Day3：跟一个小 bug/小需求：改 Prompt、调 Top-K、加一条解析。")
    add_bullet(doc, "Day4：整理 10 条坏 case，标注是检索问题还是生成问题。")
    add_bullet(doc, "Day5：给导师同步本周理解 + 下周想做的一点改进。")
    add_h2(doc, "日常加分动作")
    add_bullet(doc, "每次改动写清：现象、原因、改法、验证方式。")
    add_bullet(doc, "关键改动留截图/trace（工具调用列表）。")
    add_bullet(doc, "不懂业务词先问清楚再改知识库，避免“技术正确但业务错误”。")

    # ========== 9 ==========
    add_h1(doc, "九、手写/白板可能让你画的东西")
    add_bullet(doc, "RAG 流程图")
    add_bullet(doc, "你的 GraphRAG 数据模型（Document-Chunk-Entity）")
    add_bullet(doc, "LangGraph：START→agent⇄tools→END")
    add_bullet(doc, "一次 Tool Calling 的消息序列：system/user/assistant(tool_calls)/tool/assistant")
    add_h2(doc, "消息序列示例")
    add_codeish(
        doc,
        "system: 你是客服...\nuser: Pro 的 SLA？\n"
        "assistant: tool_calls=[hybrid_search(query=...)]\n"
        "tool: [检索结果...]\nassistant: Pro 为 7x16，首响15分钟 [1]",
    )

    # ========== 10 ==========
    add_h1(doc, "十、临考前 1 小时 checklist")
    add_bullet(doc, "能不看稿讲 2 分钟项目")
    add_bullet(doc, "能说出三个工具名与作用")
    add_bullet(doc, "能解释混合检索三路")
    add_bullet(doc, "能说两个踩坑与修复")
    add_bullet(doc, "GitHub 能打开，本地或录屏能演示")
    add_bullet(doc, "简历技术词与仓库一致（FastAPI/LangGraph/Neo4j/DeepSeek）")
    add_bullet(doc, "准备 1 个“下一步迭代”避免被问停住")
    add_body(doc, "")
    add_body(
        doc,
        "最后提醒：实习面试更看“链路清楚 + 能动手 + 诚实边界”。"
        "把本手册第1、2、4章吃透，已经超过多数只会堆名词的候选人。",
        bold=True,
    )

    doc.save(OUT_DOCX)
    print(f"DOCX={OUT_DOCX}")


if __name__ == "__main__":
    build()
