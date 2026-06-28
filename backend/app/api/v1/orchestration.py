"""Read-only orchestration graph APIs backed by `.trae` assets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter()

PRIMARY_WORKFLOW_IDS = [
    "development_workflow",
    "news_workflow",
    "ecommerce_workflow",
    "self_optimization_workflow",
]
CEO_ORCHESTRATOR_AGENT_ID = "ceo-orchestrator-agent"
ROOT_COLUMN_GAP = 720
ROOT_ROW_GAP = 260
WORKFLOW_CHILD_ROW_GAP = 320
WORKFLOW_CAPABILITY_X = 760
WORKFLOW_CAPABILITY_COLUMN_GAP = 560
WORKFLOW_CAPABILITY_ROW_GAP = 320
WORKFLOW_LAYER_GAP = 520
WORKFLOW_NODE_ROW_GAP = 220


def _discover_repo_root() -> Path:
    configured_root = os.getenv("DYSHOP_REPO_ROOT")
    if configured_root:
        return Path(configured_root).resolve()

    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        if (parent / ".trae").is_dir():
            return parent

    # Local source checkout fallback: backend/app/api/v1/orchestration.py -> repo root.
    if len(current_file.parents) > 4:
        return current_file.parents[4]
    return current_file.parents[-1]


REPO_ROOT = _discover_repo_root()
TRAE_ROOT = Path(os.getenv("DYSHOP_TRAE_ROOT", REPO_ROOT / ".trae")).resolve()


def _read_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    data = yaml.safe_load(raw)
    return data if isinstance(data, dict) else {}


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _load_agents() -> dict[str, dict[str, Any]]:
    registry = _read_yaml_file(TRAE_ROOT / "registry" / "agent-catalog.yaml")
    agents: dict[str, dict[str, Any]] = {}
    for item in _as_list(registry.get("agents")):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        agents[item["id"]] = {
            "id": item["id"],
            "label": item["id"],
            "kind": "agent",
            "status": item.get("status", "unknown"),
            "roleType": item.get("role_type"),
            "layer": item.get("layer"),
            "workflowScopes": _as_list(item.get("workflow_scope")),
            "filePath": item.get("file"),
            "primaryInputs": _as_list(item.get("primary_inputs")),
            "primaryOutputs": _as_list(item.get("primary_outputs")),
            "defaultNext": _as_list(item.get("default_next")),
            "replacedBySkill": item.get("replaced_by_skill"),
        }
    return agents


def _load_skills() -> dict[str, dict[str, Any]]:
    registry = _read_yaml_file(TRAE_ROOT / "registry" / "skill-catalog.yaml")
    skills: dict[str, dict[str, Any]] = {}
    for item in _as_list(registry.get("skills")):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        skills[item["id"]] = {
            "id": item["id"],
            "label": item["id"],
            "kind": "skill",
            "status": item.get("status", "unknown"),
            "roleType": item.get("role_type"),
            "workflowScopes": _as_list(item.get("workflow_scope")),
            "filePath": item.get("file"),
            "replacesAgents": _as_list(item.get("replaces_agents")),
            "tools": [],
        }
    return skills


def _load_tools() -> dict[str, dict[str, Any]]:
    registry = _read_yaml_file(TRAE_ROOT / "registry" / "tool-catalog.yaml")
    tools: dict[str, dict[str, Any]] = {}
    for item in _as_list(registry.get("tools")):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        tools[item["id"]] = {
            "id": item["id"],
            "label": item.get("invoke_name") or item["id"],
            "kind": "tool",
            "status": item.get("status", "unknown"),
            "toolType": item.get("tool_type"),
            "filePath": item.get("file"),
            "implementation": item.get("implementation"),
            "backendEntry": item.get("backend_entry"),
            "commandEntry": item.get("command_entry"),
            "invokeName": item.get("invoke_name"),
            "usedBySkills": _as_list(item.get("used_by_skills")),
            "primaryInputs": _as_list(item.get("primary_inputs")),
            "primaryOutputs": _as_list(item.get("primary_outputs")),
        }
    return tools


def _load_workflows() -> dict[str, dict[str, Any]]:
    workflows: dict[str, dict[str, Any]] = {}
    workflow_dir = TRAE_ROOT / "workflows"
    for file_path in sorted(workflow_dir.glob("*.yaml")):
        data = _read_yaml_file(file_path)
        workflow_id = data.get("workflow_id")
        if not workflow_id:
            continue
        nodes = [node for node in _as_list(data.get("nodes")) if isinstance(node, dict)]
        edges = [edge for edge in _as_list(data.get("edges")) if isinstance(edge, dict)]
        roles = [role for role in _as_list(data.get("roles")) if isinstance(role, dict)]
        workflows[workflow_id] = {
            "id": workflow_id,
            "label": data.get("name") or workflow_id,
            "kind": "workflow",
            "department": data.get("department"),
            "description": data.get("description"),
            "parentWorkflow": data.get("parent_workflow"),
            "childWorkflows": _as_list(data.get("child_department_workflows")),
            "ministerRole": data.get("minister_role"),
            "workflowController": data.get("workflow_controller"),
            "entryRules": _as_list(data.get("entry_rules")),
            "successCriteria": _as_list(data.get("success_criteria")),
            "filePath": _relative_path(file_path),
            "roles": roles,
            "nodes": nodes,
            "edges": edges,
        }
    for workflow_id, workflow in workflows.items():
        for child_id in workflow.get("childWorkflows", []):
            if child_id in workflows and not workflows[child_id].get("parentWorkflow"):
                workflows[child_id]["parentWorkflow"] = workflow_id
    return workflows


def _build_agent_relations(
    agents: dict[str, dict[str, Any]],
    workflows: dict[str, dict[str, Any]],
    skills: dict[str, dict[str, Any]],
    tools: dict[str, dict[str, Any]],
) -> None:
    skills_by_workflow: dict[str, set[str]] = {workflow_id: set() for workflow_id in workflows}
    workflows_by_agent: dict[str, set[str]] = {agent_id: set() for agent_id in agents}

    for skill_id, skill in skills.items():
        for workflow_id in skill.get("workflowScopes", []):
            if workflow_id in workflows:
                skills_by_workflow.setdefault(workflow_id, set()).add(skill_id)

    for workflow_id, workflow in workflows.items():
        for node in workflow["nodes"]:
            if node.get("skill"):
                skills_by_workflow.setdefault(workflow_id, set()).add(node["skill"])
            if node.get("agent"):
                workflows_by_agent.setdefault(node["agent"], set()).add(workflow_id)

    tools_by_skill: dict[str, list[str]] = {}
    for tool_id, tool in tools.items():
        for skill_id in tool.get("usedBySkills", []):
            tools_by_skill.setdefault(skill_id, []).append(tool_id)
            if skill_id in skills:
                skills[skill_id].setdefault("tools", []).append(tool_id)

    for agent_id, agent in agents.items():
        related_workflows = sorted(workflows_by_agent.get(agent_id, set()) or set(agent.get("workflowScopes", [])))
        related_skills: set[str] = set()
        for workflow_id in related_workflows:
            related_skills.update(skills_by_workflow.get(workflow_id, set()))
        if agent.get("replacedBySkill"):
            related_skills.add(agent["replacedBySkill"])
        related_tools: set[str] = set()
        for skill_id in related_skills:
            related_tools.update(tools_by_skill.get(skill_id, []))
        agent["relatedWorkflows"] = related_workflows
        agent["relatedSkills"] = sorted(skill_id for skill_id in related_skills if skill_id in skills)
        agent["relatedTools"] = sorted(tool_id for tool_id in related_tools if tool_id in tools)


def _root_layout_position(index: int, column: int) -> dict[str, int]:
    return {"x": column * ROOT_COLUMN_GAP, "y": index * ROOT_ROW_GAP}


def _workflow_node_data(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": workflow["id"],
        "kind": "workflow",
        "label": workflow["label"],
        "subtitle": workflow.get("department"),
        "description": workflow.get("description"),
        "status": "active",
        "filePath": workflow.get("filePath"),
        "nodeCount": len(workflow.get("nodes", [])),
        "edgeCount": len(workflow.get("edges", [])),
        "relatedWorkflows": workflow.get("childWorkflows", []),
    }


def _build_root_graph(
    agents: dict[str, dict[str, Any]],
    workflows: dict[str, dict[str, Any]],
    skills: dict[str, dict[str, Any]],
    tools: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    primary_workflow_ids = [workflow_id for workflow_id in PRIMARY_WORKFLOW_IDS if workflow_id in workflows]
    if not primary_workflow_ids:
        primary_workflow_ids = sorted(
            workflow_id
            for workflow_id, workflow in workflows.items()
            if not workflow.get("parentWorkflow")
        )

    ceo_agent = agents.get(CEO_ORCHESTRATOR_AGENT_ID)
    if ceo_agent:
        nodes.append(
            {
                "id": f"agent:{CEO_ORCHESTRATOR_AGENT_ID}",
                "type": "orchestrationNode",
                "position": _root_layout_position(1, 0),
                "data": {
                    "id": CEO_ORCHESTRATOR_AGENT_ID,
                    "kind": "agent",
                    "label": CEO_ORCHESTRATOR_AGENT_ID,
                    "subtitle": ceo_agent.get("roleType"),
                    "status": ceo_agent.get("status"),
                    "filePath": ceo_agent.get("filePath"),
                    "roleType": ceo_agent.get("roleType"),
                    "layer": ceo_agent.get("layer"),
                    "primaryInputs": ceo_agent.get("primaryInputs", []),
                    "primaryOutputs": ceo_agent.get("primaryOutputs", []),
                    "defaultNext": primary_workflow_ids,
                    "relatedWorkflows": primary_workflow_ids,
                    "relatedSkills": [],
                    "relatedTools": [],
                },
            }
        )

    for index, workflow_id in enumerate(primary_workflow_ids):
        workflow = workflows[workflow_id]
        nodes.append(
            {
                "id": f"workflow:{workflow_id}",
                "type": "orchestrationNode",
                "position": _root_layout_position(index, 1),
                "data": _workflow_node_data(workflow),
            }
        )

    if ceo_agent:
        for workflow_id in primary_workflow_ids:
            edges.append(
                {
                    "id": f"agent:{CEO_ORCHESTRATOR_AGENT_ID}->workflow:{workflow_id}",
                    "source": f"agent:{CEO_ORCHESTRATOR_AGENT_ID}",
                    "target": f"workflow:{workflow_id}",
                    "label": "一级选流",
                    "animated": False,
                }
            )

    _apply_parallel_edge_metadata(edges)
    return {"nodes": nodes, "edges": edges}


def _workflow_node_position(index: int) -> dict[str, int]:
    return {
        "x": WORKFLOW_CAPABILITY_X + (index % 3) * WORKFLOW_CAPABILITY_COLUMN_GAP,
        "y": (index // 3) * WORKFLOW_CAPABILITY_ROW_GAP,
    }


def _workflow_child_position(index: int) -> dict[str, int]:
    return {
        "x": WORKFLOW_CAPABILITY_X + WORKFLOW_CAPABILITY_COLUMN_GAP * (index + 1),
        "y": -220 + index * 180,
    }


def _workflow_capability_position(index: int) -> dict[str, int]:
    return _workflow_node_position(index)


def _merge_unique_values(current: list[Any], incoming: list[Any]) -> list[Any]:
    merged = list(current)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    return merged


def _edge_display_props() -> dict[str, Any]:
    return {
        "type": "floatingBezier",
        "labelBgPadding": [10, 6],
        "labelBgBorderRadius": 10,
        "labelBgStyle": {"fill": "rgba(255, 255, 255, 0.92)", "fillOpacity": 0.92},
        "labelStyle": {"fontSize": 11, "fontWeight": 600, "fill": "#7c5f6d"},
        "style": {"strokeWidth": 1.8, "stroke": "#d6a6be"},
    }


def _apply_parallel_edge_metadata(edges: list[dict[str, Any]]) -> None:
    """Separate multiple edges between the same two unique nodes in the UI."""
    grouped_edges: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        grouped_edges.setdefault((source, target), []).append(edge)

    for (source, target), group in grouped_edges.items():
        total = len(group)
        for index, edge in enumerate(group):
            offset = (index - (total - 1) / 2) * 44
            edge["type"] = "floatingBezier"
            edge_data = edge.setdefault("data", {})
            if not isinstance(edge_data, dict):
                edge_data = {}
                edge["data"] = edge_data
            edge_data.update(
                {
                    "parallelIndex": index,
                    "parallelCount": total,
                    "parallelOffset": offset,
                    "isSelfLoop": source == target,
                }
            )


def _apply_readable_workflow_layout(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    controller_node_id: str | None,
) -> None:
    """Lay out the default graph as a left-to-right human-readable flow."""
    if not nodes:
        return

    node_ids = {node["id"] for node in nodes}
    ranks: dict[str, int] = {node_id: 0 for node_id in node_ids}
    if controller_node_id in node_ids:
        ranks[controller_node_id] = 0

    for _ in range(len(nodes)):
        changed = False
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source not in node_ids or target not in node_ids or source == target:
                continue
            next_rank = ranks[source] + 1
            if ranks[target] < next_rank:
                ranks[target] = next_rank
                changed = True
        if not changed:
            break

    grouped_nodes: dict[int, list[dict[str, Any]]] = {}
    for node in nodes:
        grouped_nodes.setdefault(ranks.get(node["id"], 0), []).append(node)

    for rank, rank_nodes in grouped_nodes.items():
        rank_nodes.sort(key=lambda item: item.get("data", {}).get("nodeKey") or item["id"])
        total = len(rank_nodes)
        for index, node in enumerate(rank_nodes):
            node["position"] = {
                "x": rank * WORKFLOW_LAYER_GAP,
                "y": int((index - (total - 1) / 2) * WORKFLOW_NODE_ROW_GAP),
            }


def _is_forward_workflow_edge(edge: dict[str, Any], workflow_node_order: dict[str, int]) -> bool:
    source_key = edge.get("from")
    target_key = edge.get("to")
    if source_key not in workflow_node_order or target_key not in workflow_node_order:
        return True
    return workflow_node_order[target_key] > workflow_node_order[source_key]


def _build_workflow_graph(
    workflow: dict[str, Any],
    agents: dict[str, dict[str, Any]],
    skills: dict[str, dict[str, Any]],
    tools: dict[str, dict[str, Any]],
    workflows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_by_id: dict[str, dict[str, Any]] = {}
    node_key_to_graph_id: dict[str, str] = {}
    workflow_node_order = {
        node.get("key"): index
        for index, node in enumerate(workflow.get("nodes", []))
        if isinstance(node, dict) and node.get("key")
    }

    def add_or_merge_node(graph_node: dict[str, Any], node_key: str | None, role: str | None) -> None:
        graph_node_id = graph_node["id"]
        if node_key:
            node_key_to_graph_id[node_key] = graph_node_id
        if graph_node_id not in node_by_id:
            data = graph_node.setdefault("data", {})
            workflow_nodes = []
            if node_key:
                workflow_nodes.append({"key": node_key, "role": role})
            data["nodeKeys"] = [node_key] if node_key else []
            data["workflowNodes"] = workflow_nodes
            node_by_id[graph_node_id] = graph_node
            nodes.append(graph_node)
            return

        existing_data = node_by_id[graph_node_id]["data"]
        incoming_data = graph_node.get("data", {})
        if node_key:
            existing_data["nodeKeys"] = _merge_unique_values(existing_data.get("nodeKeys", []), [node_key])
            existing_data.setdefault("workflowNodes", []).append({"key": node_key, "role": role})
            if not existing_data.get("nodeKey"):
                existing_data["nodeKey"] = node_key

        roles = _merge_unique_values(
            [item for item in [existing_data.get("role")] if item],
            [item for item in [role] if item],
        )
        if roles:
            existing_data["role"] = " / ".join(roles)
        subtitles = _merge_unique_values(
            [item for item in [existing_data.get("subtitle")] if item],
            [item for item in [incoming_data.get("subtitle")] if item],
        )
        if subtitles:
            existing_data["subtitle"] = " / ".join(subtitles)
        existing_data["relatedSkills"] = _merge_unique_values(
            existing_data.get("relatedSkills", []),
            incoming_data.get("relatedSkills", []),
        )
        existing_data["relatedTools"] = _merge_unique_values(
            existing_data.get("relatedTools", []),
            incoming_data.get("relatedTools", []),
        )

    child_workflow_ids = [
        child_id for child_id in workflow.get("childWorkflows", []) if child_id in workflows
    ]
    for index, child_id in enumerate(child_workflow_ids):
        child_workflow = workflows[child_id]
        add_or_merge_node(
            {
                "id": f"workflow:{child_id}",
                "type": "orchestrationNode",
                "position": _workflow_child_position(index),
                "data": {
                    **_workflow_node_data(child_workflow),
                    "nodeKey": child_id,
                    "role": "child_workflow",
                    "workflowId": workflow["id"],
                },
            },
            child_id,
            "child_workflow",
        )

    for index, node in enumerate(workflow.get("nodes", [])):
        agent_id = node.get("agent")
        skill_id = node.get("skill")
        child_workflow_id = node.get("workflow")
        kind = "agent" if agent_id else "skill" if skill_id else "workflow" if child_workflow_id else "node"
        capability_id = agent_id or skill_id or child_workflow_id or node.get("key")
        catalog_item = agents.get(agent_id or "") or skills.get(skill_id or "") or workflows.get(child_workflow_id or "") or {}
        related_tools = []
        if skill_id:
            related_tools = skills.get(skill_id, {}).get("tools", [])
        if agent_id:
            related_tools = agents.get(agent_id, {}).get("relatedTools", [])
        graph_node_id = f"{kind}:{capability_id}"
        add_or_merge_node(
            {
                "id": graph_node_id,
                "type": "orchestrationNode",
                "position": _workflow_capability_position(index),
                "data": {
                    "id": capability_id,
                    "nodeKey": node.get("key"),
                    "kind": kind,
                    "label": capability_id,
                    "subtitle": node.get("role") or catalog_item.get("roleType"),
                    "status": catalog_item.get("status", "active"),
                    "filePath": catalog_item.get("filePath"),
                    "role": node.get("role"),
                    "workflowId": workflow["id"],
                    "relatedSkills": agents.get(agent_id or "", {}).get("relatedSkills", []),
                    "relatedTools": related_tools,
                    "primaryInputs": catalog_item.get("primaryInputs", []),
                    "primaryOutputs": catalog_item.get("primaryOutputs", []),
                    "defaultNext": catalog_item.get("defaultNext", []),
                },
            },
            node.get("key"),
            node.get("role"),
        )

    declared_node_ids = {node["id"] for node in nodes}
    controller_node_id = next(
        (
            node["id"]
            for node in nodes
            if node["data"].get("id") in {workflow.get("workflowController"), workflow.get("ministerRole")}
        ),
        nodes[0]["id"] if nodes else None,
    )
    if controller_node_id:
        for child_id in child_workflow_ids:
            child_node_id = f"workflow:{child_id}"
            if child_node_id in declared_node_ids:
                edges.append(
                    {
                        "id": f"{workflow['id']}:{controller_node_id}->{child_node_id}:child_workflow",
                        "source": controller_node_id,
                        "target": child_node_id,
                        "label": "child workflow",
                        "animated": False,
                        **_edge_display_props(),
                    }
                )

    for index, edge in enumerate(workflow.get("edges", [])):
        if not _is_forward_workflow_edge(edge, workflow_node_order):
            continue
        source_key = edge.get("from")
        target_key = edge.get("to")
        source = node_key_to_graph_id.get(source_key)
        target = node_key_to_graph_id.get(target_key)
        if source not in declared_node_ids or target not in declared_node_ids:
            continue
        edges.append(
            {
                "id": f"{workflow['id']}:{source_key}->{target_key}:{index}",
                "source": source,
                "target": target,
                "label": edge.get("when"),
                "data": {
                    "fromNodeKey": source_key,
                    "toNodeKey": target_key,
                    "input": _as_list(edge.get("input")),
                    "output": _as_list(edge.get("output")),
                },
                **_edge_display_props(),
            }
        )

    _apply_parallel_edge_metadata(edges)
    _apply_readable_workflow_layout(nodes, edges, controller_node_id)
    return {
        "workflowId": workflow["id"],
        "label": workflow["label"],
        "description": workflow.get("description"),
        "department": workflow.get("department"),
        "parentWorkflow": workflow.get("parentWorkflow"),
        "childWorkflows": workflow.get("childWorkflows", []),
        "ministerRole": workflow.get("ministerRole"),
        "workflowController": workflow.get("workflowController"),
        "entryRules": workflow.get("entryRules", []),
        "successCriteria": workflow.get("successCriteria", []),
        "filePath": workflow.get("filePath"),
        "roles": workflow.get("roles", []),
        "nodes": nodes,
        "edges": edges,
    }


def _build_payload() -> dict[str, Any]:
    agents = _load_agents()
    skills = _load_skills()
    tools = _load_tools()
    workflows = _load_workflows()
    _build_agent_relations(agents, workflows, skills, tools)

    workflow_graphs = {
        workflow_id: _build_workflow_graph(workflow, agents, skills, tools, workflows)
        for workflow_id, workflow in workflows.items()
    }

    return {
        "source": {
            "registry": ".trae/registry",
            "workflows": ".trae/workflows",
            "generatedFrom": "filesystem",
        },
        "summary": {
            "agentCount": len(agents),
            "activeAgentCount": len([item for item in agents.values() if item.get("status") == "active"]),
            "workflowCount": len(workflows),
            "skillCount": len(skills),
            "toolCount": len(tools),
        },
        "agents": sorted(agents.values(), key=lambda item: item["id"]),
        "skills": sorted(skills.values(), key=lambda item: item["id"]),
        "tools": sorted(tools.values(), key=lambda item: item["id"]),
        "workflows": sorted(
            [
                {
                    key: value
                    for key, value in workflow.items()
                    if key not in {"nodes", "edges", "roles"}
                }
                for workflow in workflows.values()
            ],
            key=lambda item: item["id"],
        ),
        "rootGraph": _build_root_graph(agents, workflows, skills, tools),
        "workflowGraphs": workflow_graphs,
    }


@router.get("/graph")
async def get_orchestration_graph():
    """Return current `.trae` agent/workflow/skill/tool orchestration graph."""
    if not TRAE_ROOT.exists():
        raise HTTPException(status_code=404, detail=".trae directory not found")
    return _build_payload()
