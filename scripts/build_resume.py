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
        "GraphRAG 知识工程：Neo4j Vector Index + 词面召回 + 1-hop Graph Expansion；分数融合采用 RRF（k=60）；"
        "能基于自建评测集计算 Hit@3，并实测检索/端到端延迟。",
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
        "项目概述：面向企业知识库问答与售后支持，独立实现 GraphRAG 客服 Agent。"
        "检索层为 Vector + Lexical + 1-hop 图谱扩展，融合算法为 RRF（k=60）；编排层为 LangGraph 多工具闭环（检索/实体查询/转人工工单）。"
        "配套 FastAPI、Docker Neo4j、引用溯源与自建评测脚本，仓库可复现实验。",
    )
    add_body(doc, "核心成果：", bold=True)
    add_bullet(
        doc,
        "图谱建模：Document–Chunk–Entity（HAS_CHUNK / MENTIONS / RELATED_TO）；图扩展为 1-hop 共现实体邻居，避免 2-hop 引入噪声。",
    )
    add_bullet(
        doc,
        "检索与评测：三路召回经 RRF 融合。自建 8 条 FAQ 评测集，Hit@3 纯向量 50% → Hybrid GraphRAG 100%（+50pp）；"
        "检索 P95 约 45ms，端到端对话 P95 约 5.0s（含 DeepSeek 推理）。指标见 eval/metrics.json，非 Ragas 包装分数。",
    )
    add_bullet(
        doc,
        "Agent：LangGraph ReAct，工具 hybrid_search / entity_lookup / create_ticket；回答带 Citation 与 Tool Trace；证据不足转人工。同集 Agent 答题 8/8 命中关键事实。",
    )
    add_bullet(
        doc,
        "工程：FastAPI（对话/入库/A/B 对比/评测）、Docker 拉起 Neo4j、分类知识库与可选 X-Admin-Token 写保护。",
    )

    # Project 2 — Agent落地，但不写 Dify
    add_body(doc, "项目二：DeepResearch 多智能步竞品情报 Agent 落地系统", bold=True, size=11)
    add_body(
        doc,
        "技术栈：Python / LangGraph / LangChain / Tavily Search API / 网页正文抽取 / Map-Reduce 摘要",
        size=10,
    )
    add_body(
        doc,
        "项目概述：将竞品调研拆成可执行 Agent 状态机：问题拆解 → 检索规划 → Tavily 搜索 → 正文抽取 → 分段摘要 → 汇总成稿。"
        "定位是 Agent 落地，而不是单次 Chat。成本与压缩比未做生产级台账，不编造 Token/$ 数字。",
    )
    add_body(doc, "核心成果：", bold=True)
    add_bullet(
        doc,
        "编排：LangGraph 多步状态机，每步有明确输入输出；失败可中断而非一次 Prompt 撑完全程。",
    )
    add_bullet(
        doc,
        "信息获取：Tavily 拿实时检索结果；页面清洗用正文抽取（去导航/广告块的可读性启发式）后再送模型，避免整页 HTML 进上下文。",
    )
    add_bullet(
        doc,
        "长文：多源页面先 Map 再 Reduce 汇总，控制单次上下文长度；输出结构化 Markdown 报告。面试可讲方法，压缩率需按任务实测。",
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
