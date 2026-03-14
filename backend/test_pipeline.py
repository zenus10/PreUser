"""Full end-to-end test script (Phase 1 + Phase 2).

Usage:
    python test_pipeline.py <prd_file_path>
    python test_pipeline.py  # Uses built-in sample PRD

Outputs complete analysis JSON (graph + personas + simulations + report).
"""

import asyncio
import json
import logging
import sys
import os

# Configure logging — only show WARNING+ (suppress litellm verbose output)
logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s: %(message)s")

# Ensure app modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from app.services.parser import parse_document
from app.services.graph_builder import build_graph
from app.services.persona_gen import generate_personas
from app.services.simulator import run_simulation
from app.services.reporter import generate_report
from app.llm.client import llm_call
from app.prompts.chain1_structure import CHAIN1_SYSTEM_PROMPT, CHAIN1_USER_PROMPT
from app.llm.output_parser import validate_block_ids, validate_source_ranges


SAMPLE_PRD = """# 智能记账本 - 产品需求文档

## 1. 产品概述
智能记账本是一款面向年轻上班族的个人理财工具。核心目标是帮助用户以最小的操作成本完成日常记账，并通过智能分析帮助用户发现消费习惯中的问题。

目标用户：22-35岁的城市上班族，有记账意愿但觉得传统记账太麻烦。

### 核心价值主张
- 3秒完成一笔记账（语音/拍照/快捷输入）
- 自动分类，无需手动选择类别
- 月度消费洞察报告，发现你不知道的消费习惯

## 2. 用户故事

### US-001: 快速记账
作为一个刚吃完午饭的上班族，我希望在走回工位的路上用3秒钟记录这笔消费，这样我就不用担心忘记。

### US-002: 语音记账
作为一个正在开车的用户，我希望通过语音说"加油站加了300块油"就能完成记账，这样我不用停下来操作手机。

### US-003: 月度报告
作为一个想省钱的用户，我希望每月初看到上个月的消费分析报告，这样我能知道钱都花在了哪里。

## 3. 功能规格

### 3.1 快捷记账
- 首页下拉即进入记账界面
- 支持三种输入方式：手动输入金额、语音输入、拍照识别小票
- 自动识别消费类别（餐饮/交通/购物/娱乐/生活缴费/其他）
- 支持修改自动识别结果
- 记账完成后显示今日累计消费

### 3.2 语音记账
- 长按首页麦克风按钮激活
- 支持自然语言输入，如"星巴克35块"、"打车去机场花了120"
- 语音识别后显示确认卡片：金额、类别、备注
- 用户确认后入账，也可修改后再确认

### 3.3 消费分析
- 月度消费总额趋势图（近6个月）
- 各类别消费占比饼图
- 消费高峰时段分析
- "消费洞察"：系统主动发现异常消费模式
  - 例如："你本月咖啡消费比上月增加了40%"
  - 例如："你周末的外卖支出占餐饮总额的65%"

## 4. 数据模型

### 消费记录
| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 唯一标识 |
| amount | Decimal | 金额 |
| category | Enum | 消费类别 |
| input_method | Enum | 输入方式(manual/voice/photo) |
| raw_input | Text | 原始输入（语音文本/图片URL） |
| note | Text | 备注 |
| created_at | DateTime | 记录时间 |

## 5. 业务规则
- 单笔记账金额上限 99999 元
- 语音记账最长录音 30 秒
- 消费类别不可自定义（第一期），后续版本开放
- 月度报告在每月1日凌晨自动生成
- 数据仅存储在本地（第一期），不支持云同步

## 6. 非功能需求
- 语音识别响应时间 < 2秒
- 拍照识别响应时间 < 3秒
- 支持离线记账，联网后自动同步分类结果
- 最低支持 iOS 14 / Android 10
- 本地数据加密存储

## 7. 页面流程
首页（消费概览）→ 下拉进入记账 → 选择输入方式 → 确认入账 → 返回首页
首页 → 点击"月度报告" → 查看分析图表 → 点击洞察卡片查看详情
设置页 → 导出数据（CSV）→ 分享
"""


async def run_test(file_path: str | None = None):
    """Run the full Phase 1 + Phase 2 pipeline test."""

    # Load document
    if file_path:
        print(f"📄 Loading document: {file_path}")
        with open(file_path, "rb") as f:
            content = f.read()
        filename = os.path.basename(file_path)
    else:
        print("📄 Using built-in sample PRD (智能记账本)")
        content = SAMPLE_PRD.encode("utf-8")
        filename = "sample_prd.md"

    # ===== Phase 1 =====

    # Step 1: Parse document
    print("\n" + "=" * 60)
    print("Step 1: Document Parsing")
    print("=" * 60)

    doc_data = parse_document(content, filename)
    print(f"  Paragraphs: {len(doc_data['paragraphs'])}")
    print(f"  Headers: {len(doc_data['headers'])}")
    print(f"  Page count: {doc_data['page_count']}")
    for h in doc_data["headers"]:
        indent = "  " * h["level"]
        print(f"  {indent}[{h['para_index']}] {'#' * h['level']} {h['text']}")

    # Step 2: Chain 1 - Structure Sensing
    print("\n" + "=" * 60)
    print("Step 2: Chain 1 - Structure Sensing")
    print("=" * 60)

    user_prompt = CHAIN1_USER_PROMPT.format(doc_text=doc_data["text"])
    skeleton_result = await llm_call(
        prompt=user_prompt,
        system_prompt=CHAIN1_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.3,
    )

    # Validate
    block_errors = validate_block_ids(skeleton_result.get("blocks", []))
    range_errors = validate_source_ranges(skeleton_result.get("blocks", []))
    all_errors = block_errors + range_errors

    if all_errors:
        print(f"  ⚠️  Validation errors: {all_errors}")
    else:
        print("  ✅ Validation passed")

    blocks = skeleton_result.get("blocks", [])
    print(f"  Blocks identified: {len(blocks)}")
    for b in blocks:
        print(f"    {b['block_id']}: [{b['type']}] {b['title']} (paragraphs {b['source_range']})")
        if b.get("dependencies"):
            print(f"      → depends on: {b['dependencies']}")

    # Step 3: Chain 2 + 2.5 - Graph Building
    print("\n" + "=" * 60)
    print("Step 3: Chain 2 + 2.5 - Knowledge Graph Building")
    print("=" * 60)

    def progress_cb(progress, message, preview=None):
        print(f"  [{progress:.0%}] {message}")

    full_graph = await build_graph(
        skeleton=skeleton_result,
        doc_text=doc_data["text"],
        paragraphs=doc_data["paragraphs"],
        progress_callback=progress_cb,
    )

    # Phase 1 results
    nodes = full_graph.get("nodes", [])
    edges = full_graph.get("edges", [])
    new_edges = full_graph.get("new_edges", [])
    conflicts = full_graph.get("conflicts", [])
    core_paths = full_graph.get("core_paths", [])

    print(f"\n  Entities: {len(nodes)}")
    for ntype in ("scene", "role", "action", "touchpoint", "constraint", "emotion_expect"):
        count = sum(1 for n in nodes if n["type"] == ntype)
        if count:
            print(f"    - {ntype}: {count}")

    print(f"  Relations: {len(edges)} (original: {len(edges) - len(new_edges)}, cross-module: {len(new_edges)})")
    print(f"  Conflicts: {len(conflicts)}")
    for c in conflicts:
        print(f"    - [{c['severity']}] {c['type']}: {c['description']}")

    print(f"  Core Paths: {len(core_paths)}")
    for p in core_paths:
        print(f"    - {p['path_id']}: {p['name']}")
        print(f"      nodes: {' → '.join(p['node_sequence'][:5])}{'...' if len(p['node_sequence']) > 5 else ''}")

    # ===== Phase 2 =====

    # Step 4: Chain 3 - Persona Generation
    print("\n" + "=" * 60)
    print("Step 4: Chain 3 - Persona Generation")
    print("=" * 60)

    personas_data = await generate_personas(
        graph=full_graph,
        progress_callback=progress_cb,
    )

    personas = personas_data.get("personas", [])
    print(f"\n  Generated {len(personas)} personas:")
    for p in personas:
        dims = p.get("dimensions", {})
        print(f"    [{p['type']}] {p['persona_id']}: {p['name']} ({p['age']}岁, {p['occupation']})")
        print(f"      态度: {p['attitude_tag']}")
        print(f"      参数: 技术={dims.get('tech_sensitivity')}, "
              f"耐心={dims.get('patience_threshold')}, "
              f"付费={dims.get('pay_willingness')}, "
              f"替代品={dims.get('alt_dependency')}")
        print(f"      心智模型: {p['cognitive_model'][:60]}...")
        print(f"      预判摩擦点: {p.get('expected_friction_points', [])[:3]}")

    # Step 5: Chain 4 - Narrative Simulation
    print("\n" + "=" * 60)
    print("Step 5: Chain 4 - Narrative Simulation")
    print("=" * 60)

    simulations = await run_simulation(
        graph=full_graph,
        personas=personas_data,
        progress_callback=progress_cb,
    )

    print(f"\n  Completed {len(simulations)} simulations:")
    for sim in simulations:
        pid = sim["persona_id"]
        pname = next((p["name"] for p in personas if p["persona_id"] == pid), pid)
        print(f"\n    【{pname}】({pid})")
        print(f"      结果: {sim['outcome']} | NPS: {sim['nps_score']}/10")
        print(f"      情绪曲线: {sim['emotion_curve']}")
        print(f"      摩擦点: {len(sim.get('friction_points', []))} 个")
        for fp in sim.get("friction_points", [])[:3]:
            print(f"        - [{fp['severity']}] {fp['type']}: {fp['description'][:50]}...")
        print(f"      叙事摘要: {sim['narrative'][:100]}...")
        wtr = sim.get("willingness_to_return", {})
        print(f"      是否回来: {'是' if wtr.get('will_return') else '否'} - {wtr.get('reason', '')[:50]}")

    # Step 6: Chain 5 - Report Generation
    print("\n" + "=" * 60)
    print("Step 6: Chain 5 - Report Generation")
    print("=" * 60)

    report = await generate_report(
        graph=full_graph,
        personas=personas_data,
        simulations=simulations,
        progress_callback=progress_cb,
    )

    print(f"\n  === 压测报告 ===")
    print(f"  模拟 NPS: {report.get('nps_average', 0):.1f}")
    print(f"  流失归因: {report.get('churn_attribution', {})}")

    print(f"\n  📌 设计盲区 ({len(report.get('blind_spots', []))}):")
    for bs in report.get("blind_spots", []):
        print(f"    - {bs['title']}")
        print(f"      {bs['description'][:80]}...")
        print(f"      影响: {bs['affected_personas']}")
        print(f"      建议: {bs['recommendation'][:80]}...")

    print(f"\n  🚧 体验瓶颈 ({len(report.get('bottlenecks', []))}):")
    for bn in report.get("bottlenecks", []):
        print(f"    - [{bn['severity']}] {bn['title']} (影响 {bn['affected_count']} 人)")
        print(f"      {bn['description'][:80]}...")
        if bn.get("quotes"):
            print(f"      原话: \"{bn['quotes'][0][:60]}...\"")

    print(f"\n  ⚠️  假设风险 ({len(report.get('assumption_risks', []))}):")
    for ar in report.get("assumption_risks", []):
        print(f"    - [{ar['risk_level']}] {ar['assumption'][:60]}...")
        print(f"      反证: {ar['counter_evidence'][:60]}...")
        print(f"      后果: {ar['if_wrong'][:60]}...")

    # Save full output to file
    output_file = "test_output_full.json"
    with open(output_file, "w", encoding="utf-8") as f:
        output = {
            "skeleton": skeleton_result,
            "graph": full_graph,
            "personas": personas_data,
            "simulations": simulations,
            "report": report,
        }
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n📁 Full analysis JSON saved to: {output_file}")


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_test(file_path))
