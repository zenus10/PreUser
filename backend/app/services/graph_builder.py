"""Knowledge graph builder service - Chain 2 (block extraction) + Chain 2.5 (global fusion)."""

import asyncio
import json
import logging

from app.llm.client import llm_call
from app.models.schema import GraphFragment, FullGraph, GraphNode, GraphEdge
from app.prompts.chain2_extract import (
    CHAIN2_SYSTEM_PROMPT,
    CHAIN2_USER_PROMPT,
    CHAIN2_RETRY_PROMPT,
)
from app.prompts.chain25_merge import (
    CHAIN25_SYSTEM_PROMPT,
    CHAIN25_USER_PROMPT,
    CHAIN25_RETRY_PROMPT,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

# Valid entity/relation types for validation
VALID_NODE_TYPES = {"scene", "role", "action", "touchpoint", "constraint", "emotion_expect"}
VALID_EDGE_TYPES = {"triggers", "performs", "interacts_with", "requires", "conflicts_with", "leads_to"}
VALID_CONFLICT_TYPES = {"permission", "flow_break", "state_inconsistency", "assumption"}


async def build_graph(
    skeleton: dict,
    doc_text: str,
    paragraphs: list[str],
    progress_callback=None,
) -> dict:
    """Build full knowledge graph from document skeleton.

    Args:
        skeleton: Chain 1 output (DocumentSkeleton)
        doc_text: Full document text with paragraph numbers
        paragraphs: List of paragraph strings
        progress_callback: Optional callback(progress, message, preview) for progress updates

    Returns:
        FullGraph as dict
    """
    blocks = skeleton["blocks"]

    # --- Chain 2: Concurrent block extraction ---
    if progress_callback:
        progress_callback(0.1, f"正在并发抽取 {len(blocks)} 个文档块...")

    tasks = [
        _extract_block(block, paragraphs)
        for block in blocks
    ]
    fragments = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any failed extractions
    valid_fragments = []
    for i, frag in enumerate(fragments):
        if isinstance(frag, Exception):
            logger.error(f"Block extraction failed for {blocks[i].get('block_id')}: {frag}")
            valid_fragments.append({"nodes": [], "edges": []})
        else:
            valid_fragments.append(frag)

    if progress_callback:
        total_nodes = sum(len(f["nodes"]) for f in valid_fragments)
        total_edges = sum(len(f["edges"]) for f in valid_fragments)
        progress_callback(0.5, f"分块抽取完成：{total_nodes} 个实体，{total_edges} 条关系",
                          {"entities": total_nodes, "relations": total_edges})

    # --- Merge all fragments ---
    merged = _merge_fragments(valid_fragments)

    if progress_callback:
        progress_callback(0.6, "正在进行全局融合与冲突检测...")

    # --- Chain 2.5: Global fusion ---
    full_graph_data = await _global_fusion(merged, skeleton)

    if progress_callback:
        total = len(full_graph_data.get("nodes", [])) + len(full_graph_data.get("edges", []))
        conflicts = len(full_graph_data.get("conflicts", []))
        paths = len(full_graph_data.get("core_paths", []))
        progress_callback(1.0,
                          f"图谱构建完成：{len(full_graph_data.get('nodes', []))} 实体，"
                          f"{len(full_graph_data.get('edges', []))} 关系，"
                          f"{conflicts} 冲突，{paths} 核心路径",
                          {"entities": len(full_graph_data.get("nodes", [])),
                           "relations": len(full_graph_data.get("edges", [])),
                           "conflicts": conflicts,
                           "core_paths": paths})

    return full_graph_data


async def _extract_block(block: dict, paragraphs: list[str]) -> dict:
    """Extract entities and relations from a single document block (Chain 2)."""
    block_id = block["block_id"]
    block_type = block["type"]
    block_title = block["title"]
    source_range = block["source_range"]

    # Extract text slice based on source_range
    text_slice = _get_text_range(paragraphs, source_range)

    if not text_slice.strip():
        logger.warning(f"Empty text for block {block_id}, skipping extraction")
        return {"nodes": [], "edges": []}

    user_prompt = CHAIN2_USER_PROMPT.format(
        block_id=block_id,
        block_type=block_type,
        block_title=block_title,
        text=text_slice,
    )

    result = await llm_call(
        prompt=user_prompt,
        system_prompt=CHAIN2_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.3,
    )

    # Validate and retry
    for attempt in range(MAX_RETRIES):
        errors = _validate_fragment(result, block_id)
        if not errors:
            break

        logger.warning(f"Chain 2 validation failed for {block_id} (attempt {attempt + 1}): {errors}")
        retry_prompt = CHAIN2_RETRY_PROMPT.format(
            errors="\n".join(f"- {e}" for e in errors),
            block_id=block_id,
            block_type=block_type,
            block_title=block_title,
            text=text_slice,
        )
        result = await llm_call(
            prompt=retry_prompt,
            system_prompt=CHAIN2_SYSTEM_PROMPT,
            output_format="json",
            temperature=0.2,
        )

    # Ensure source_block_id is set on all nodes
    for node in result.get("nodes", []):
        node["source_block_id"] = block_id

    # Validate with Pydantic
    fragment = GraphFragment(**result)
    return fragment.model_dump()


def _get_text_range(paragraphs: list[str], source_range: list[int]) -> str:
    """Extract text from paragraph list based on source_range [start, end]."""
    start, end = source_range
    start = max(0, start)
    end = min(len(paragraphs), end + 1)  # inclusive end
    selected = paragraphs[start:end]
    return "\n\n".join(f"[{i + start}] {p}" for i, p in enumerate(selected))


def _validate_fragment(data: dict, block_id: str) -> list[str]:
    """Validate a Chain 2 graph fragment output."""
    errors = []

    if "nodes" not in data:
        errors.append("缺少 'nodes' 字段")
    if "edges" not in data:
        errors.append("缺少 'edges' 字段")
    if errors:
        return errors

    node_ids = set()
    for node in data.get("nodes", []):
        nid = node.get("id", "")
        if not nid:
            errors.append("实体缺少 id")
            continue
        if nid in node_ids:
            errors.append(f"重复的实体 id: {nid}")
        node_ids.add(nid)

        ntype = node.get("type", "")
        if ntype not in VALID_NODE_TYPES:
            errors.append(f"无效的实体类型: {ntype} (id: {nid})")

        for field in ("name", "description"):
            if not node.get(field):
                errors.append(f"实体 {nid} 缺少 {field}")

    for edge in data.get("edges", []):
        fid = edge.get("from_id", "")
        tid = edge.get("to_id", "")
        if fid not in node_ids:
            errors.append(f"关系 from_id '{fid}' 不存在于实体列表中")
        if tid not in node_ids:
            errors.append(f"关系 to_id '{tid}' 不存在于实体列表中")

        rtype = edge.get("relation_type", "")
        if rtype not in VALID_EDGE_TYPES:
            errors.append(f"无效的关系类型: {rtype}")

        conf = edge.get("confidence")
        if conf is not None and not (0 <= conf <= 1):
            errors.append(f"confidence 超出范围 [0,1]: {conf}")

    return errors


def _merge_fragments(fragments: list[dict]) -> dict:
    """Merge multiple graph fragments into a single graph."""
    all_nodes = []
    all_edges = []

    seen_node_ids = set()
    for frag in fragments:
        for node in frag.get("nodes", []):
            nid = node.get("id", "")
            if nid and nid not in seen_node_ids:
                all_nodes.append(node)
                seen_node_ids.add(nid)

        for edge in frag.get("edges", []):
            all_edges.append(edge)

    return {"nodes": all_nodes, "edges": all_edges}


async def _global_fusion(merged: dict, skeleton: dict) -> dict:
    """Run Chain 2.5: Global fusion, conflict detection, and core path extraction."""
    nodes = merged["nodes"]
    edges = merged["edges"]

    skeleton_json = json.dumps(skeleton, ensure_ascii=False, indent=2)
    nodes_json = json.dumps(nodes, ensure_ascii=False, indent=2)
    edges_json = json.dumps(edges, ensure_ascii=False, indent=2)

    user_prompt = CHAIN25_USER_PROMPT.format(
        skeleton_json=skeleton_json,
        node_count=len(nodes),
        nodes_json=nodes_json,
        edge_count=len(edges),
        edges_json=edges_json,
    )

    result = await llm_call(
        prompt=user_prompt,
        system_prompt=CHAIN25_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.3,
    )

    # Validate and retry
    valid_node_ids = {n["id"] for n in nodes}
    for attempt in range(MAX_RETRIES):
        errors = _validate_fusion(result, valid_node_ids)
        if not errors:
            break

        logger.warning(f"Chain 2.5 validation failed (attempt {attempt + 1}): {errors}")
        retry_prompt = CHAIN25_RETRY_PROMPT.format(
            errors="\n".join(f"- {e}" for e in errors),
            valid_ids=json.dumps(sorted(valid_node_ids), ensure_ascii=False),
            original_input=user_prompt[:3000],  # Truncate to avoid token overflow
        )
        result = await llm_call(
            prompt=retry_prompt,
            system_prompt=CHAIN25_SYSTEM_PROMPT,
            output_format="json",
            temperature=0.2,
        )

    # Build full graph: merge original nodes/edges with fusion results
    new_edges = result.get("new_edges", [])
    conflicts = result.get("conflicts", [])
    core_paths = result.get("core_paths", [])

    full_graph_data = {
        "nodes": nodes,
        "edges": edges + new_edges,
        "new_edges": new_edges,
        "conflicts": conflicts,
        "core_paths": core_paths,
    }

    # Validate with Pydantic
    full_graph = FullGraph(**full_graph_data)
    return full_graph.model_dump()


def _validate_fusion(data: dict, valid_node_ids: set[str]) -> list[str]:
    """Validate Chain 2.5 global fusion output."""
    errors = []

    # Validate new_edges
    for edge in data.get("new_edges", []):
        fid = edge.get("from_id", "")
        tid = edge.get("to_id", "")
        if fid not in valid_node_ids:
            errors.append(f"new_edges: from_id '{fid}' 不存在于实体列表中")
        if tid not in valid_node_ids:
            errors.append(f"new_edges: to_id '{tid}' 不存在于实体列表中")

        rtype = edge.get("relation_type", "")
        if rtype not in VALID_EDGE_TYPES:
            errors.append(f"new_edges: 无效的关系类型 '{rtype}'")

    # Validate conflicts
    for conflict in data.get("conflicts", []):
        ctype = conflict.get("type", "")
        if ctype not in VALID_CONFLICT_TYPES:
            errors.append(f"conflicts: 无效的冲突类型 '{ctype}'")

        severity = conflict.get("severity", "")
        if severity not in ("high", "medium", "low"):
            errors.append(f"conflicts: 无效的 severity '{severity}'")

    # Validate core_paths
    for path in data.get("core_paths", []):
        for nid in path.get("node_sequence", []):
            if nid not in valid_node_ids:
                errors.append(f"core_paths: node_sequence 中 '{nid}' 不存在于实体列表中")
        for tid in path.get("critical_touchpoints", []):
            if tid not in valid_node_ids:
                errors.append(f"core_paths: critical_touchpoints 中 '{tid}' 不存在于实体列表中")
        for rid in path.get("risk_points", []):
            if rid not in valid_node_ids:
                errors.append(f"core_paths: risk_points 中 '{rid}' 不存在于实体列表中")

    return errors
