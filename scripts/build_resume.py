# -*- coding: utf-8 -*-
"""High-impact resume; avoid Dify (被视为掉价)."""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT_DOCX = Path(r"d:\Desktop\郑咏明-AI-Agent实习简历.docx")
OUT_PDF = Path(r"d:\Desktop\郑咏明-AI-Agent实习简历-高配版.pdf")


def set_run_font(run, name="微软雅黑", size=10.5, bold=False, color=None):
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if color is not None:
        run.font.color.rgb = color


def add_center_line(doc, text, size=11, bold=False, space_after=2):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.12
    set_run_font(p.add_run(text), size=size, bold=bold)


def add_section(doc, title):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.12
    set_run_font(p.add_run(title), size=12, bold=True, color=RGBColor(0x1F, 0x3A, 0x5F))
    pPr = p._p.get_or_add_pPr()
    pBdr = pPr.makeelement(qn("w:pBdr"), {})
    bottom = pBdr.makeelement(
        qn("w:bottom"),
        {qn("w:val"): "single", qn("w:sz"): "12", qn("w:space"): "1", qn("w:color"): "2DD4BF"},
    )
    pBdr.append(bottom)
    pPr.append(pBdr)


def add_body(doc, text, bold=False, size=10.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    set_run_font(p.add_run(text), size=size, bold=bold)


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    p.clear()
    set_run_font(p.add_run(text), size=10.5)


def main():
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(1.2)
        section.bottom_margin = Cm(1.2)
        section.left_margin = Cm(1.4)
        section.right_margin = Cm(1.4)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    set_run_font(p.add_run("郑咏明"), size=18, bold=True)

    add_center_line(doc, "求职意向：AI Agent / 大模型应用开发实习生", size=11, bold=True)
    add_center_line(
        doc,
        "18096270420  |  Jas-4ever@outlook.com  |  GitHub: zhengyongming06-code/graphrag-cs-agent",
        size=9.5,
        space_after=1,
    )

    add_section(doc, "教育背景")
    add_body(doc, "2025.09 — 2029.06　　天津城建大学　　计算机科学与技术　　本科在读", bold=True)

    add_section(doc, "专业技能")
    add_bullet(
        doc,
        "Agent 认知编排：精通 LangGraph / LangChain 状态机编排与多工具协同；掌握 Tool Calling、ReAct 决策环、"
        "任务规划、拒答策略与 Human-in-the-loop 人机协同闭环。",
    )
    add_bullet(
        doc,
        "GraphRAG 知识工程：掌握文档解析、语义切分、Embedding、Hybrid Retrieval；"
        "能基于 Neo4j 构建企业知识图谱并完成 Graph Expansion / 关系增强召回。",
    )
    add_bullet(
        doc,
        "LLM 应用工程化：FastAPI 服务化封装、Docker 容器化部署、前后端联调、工具调用可观测；"
        "具备从 0 到 1 交付可演示 Agent 系统的落地能力。",
    )

    add_section(doc, "项目经历")

    # Project 1
    add_body(doc, "项目一：企业级 GraphRAG 智能客服 Agent 中台（NovaDesk）", bold=True, size=11)
    add_body(
        doc,
        "技术栈：Python / FastAPI / LangGraph / Neo4j GraphRAG / DeepSeek / Docker / 可观测前端",
        size=10,
    )
    add_body(doc, "项目链接：https://github.com/zhengyongming06-code/graphrag-cs-agent", size=10)
    add_body(
        doc,
        "项目概述：面向企业私域知识治理与售后智能化场景，独立打造“知识中台 + 决策 Agent”一体化方案。"
        "以 GraphRAG 为检索内核、以 LangGraph 为编排中枢，打通知识入库、混合召回、工具调用、引用溯源与转人工升级的完整业务闭环，"
        "显著区别于传统单轮 RAG Demo。",
    )
    add_body(doc, "核心成果：", bold=True)
    add_bullet(
        doc,
        "知识中台建模：设计 Document–Chunk–Entity 多层图谱 Schema 与 HAS_CHUNK / MENTIONS / RELATED_TO 关系体系，"
        "完成非结构化文档的结构化升级，沉淀可复用的企业知识资产网络。",
    )
    add_bullet(
        doc,
        "GraphRAG 检索引擎：自研 Vector + Lexical + Graph Expansion 三路融合召回与分数融合策略，"
        "强化跨实体、跨政策类复杂问句的证据完整性，突破纯向量检索“语义近、关系断”的瓶颈。",
    )
    add_bullet(
        doc,
        "Agent 决策中枢：基于 LangGraph 构建 ReAct 多工具编排（hybrid_search / entity_lookup / create_ticket），"
        "实现动态规划式问答；引入 Citation Grounding 与低置信转人工机制，构建防幻觉护栏。",
    )
    add_bullet(
        doc,
        "平台化交付：完成 API 服务化（对话/入库/图谱查询/健康探针）、Docker 一键基础设施拉起、在线知识运营与回归评测，"
        "形成可对外演示、可二次扩展的 Agent 工程资产。",
    )

    # Project 2 — Agent落地，但不写 Dify
    add_body(doc, "项目二：DeepResearch 多智能步竞品情报 Agent 落地系统", bold=True, size=11)
    add_body(
        doc,
        "技术栈：Python / LangGraph / LangChain / Tavily Search API / 网页解析与清洗 / Map-Reduce 报告生成",
        size=10,
    )
    add_body(
        doc,
        "项目概述：针对商业调研“信息碎片化、人工周期长、结论难沉淀”痛点，落地一套可复用的 Deep Research Agent。"
        "以 LangGraph 多步状态机为控制面，以搜索/抓取/提炼工具为执行面，实现从选题到成稿的自动化情报生产闭环。",
    )
    add_body(doc, "核心成果：", bold=True)
    add_bullet(
        doc,
        "多智能步 Agent 编排：设计“意图拆解→检索规划→公网采集→正文净化→多源汇总→报告生成”状态机流水线，"
        "将一次性 Prompt 调用升级为可规划、可回溯、可扩展的 Agent 生产能力。",
    )
    add_bullet(
        doc,
        "实时情报工具矩阵：集成 Tavily 搜索与网页解析链路，突破模型参数知识的时效上限；"
        "对长页面做结构化清洗与噪声抑制，提升有效上下文密度与证据可用性。",
    )
    add_bullet(
        doc,
        "长上下文治理与成稿：采用 Map-Reduce 分层压缩与要点对齐，抑制 Token 膨胀与关键信息淹没，"
        "自动输出可直接用于汇报的结构化 Markdown 竞品情报报告，完成调研业务的 Agent 化落地。",
    )

    add_section(doc, "个人优势")
    add_bullet(
        doc,
        "结果导向的 Agent 落地能力：能把大模型能力封装成可演示系统，而不是停留在 Chat 调用与概念堆砌。",
    )
    add_bullet(
        doc,
        "兼顾效果与可控性：强调证据锚定、工具可追踪、异常转人工，追求“能上线”的 Agent，而不是只会炫技的 Demo。",
    )

    doc.save(OUT_DOCX)
    print(f"DOCX={OUT_DOCX}")


if __name__ == "__main__":
    main()
