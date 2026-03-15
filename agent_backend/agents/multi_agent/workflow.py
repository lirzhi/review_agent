from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, TypedDict

from agent.agent_backend.agents.multi_agent.prompt_manager import PromptManager
from agent.agent_backend.agents.multi_agent.roles import AgentRole, build_default_roles
from agent.agent_backend.common_tools.builtin.memory_tool import MemoryTool
from agent.agent_backend.llm.client import LLMClient

try:
    from langgraph.graph import END, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # pragma: no cover
    HAS_LANGGRAPH = False
    END = "__end__"
    StateGraph = None


class WorkflowState(TypedDict, total=False):
    doc_id: str
    section_id: str
    content: str
    memory_context: str
    memory_package: Dict[str, Any]
    related_rules: List[Dict[str, Any]]
    coordination_payload: Dict[str, Any]
    plan_steps: List[str]
    rule_evidence: List[str]
    shared_context: Dict[str, Any]
    findings_draft: List[str]
    findings_refined: List[str]
    findings: List[str]
    score: float
    conclusion: str
    trace: Dict[str, Any]


class MultiAgentPreReviewWorkflow:
    RISK_KEYWORDS: Dict[str, List[str]] = {
        "contraindication": ["contraindication", "禁忌"],
        "adverse_reaction": ["adverse reaction", "不良反应"],
        "dosage": ["dosage", "dose", "用法用量", "剂量"],
        "warning": ["warning", "precaution", "注意事项", "警告"],
        "interaction": ["drug interaction", "相互作用"],
    }

    def __init__(self, memory_tool: MemoryTool | None = None, roles: List[AgentRole] | None = None):
        self.memory_tool = memory_tool or MemoryTool()
        self.roles = roles or build_default_roles()
        self.prompts = PromptManager()
        self.llm = LLMClient()
        self.graph = self._build_graph() if HAS_LANGGRAPH else None

    def describe_roles(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": r.name,
                "description": r.description,
                "capabilities": r.capabilities,
                "collaboration_contract": r.collaboration_contract,
                "inputs": r.inputs,
                "outputs": r.outputs,
            }
            for r in self.roles
        ]

    @staticmethod
    def _uniq(items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for item in items:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            out.append(normalized)
        return out

    @staticmethod
    def _contains_any(source: str, words: List[str]) -> bool:
        low = (source or "").lower()
        return any(w.lower() in low for w in words)

    @staticmethod
    def _append_trace(state: WorkflowState, agent: str, payload: Dict[str, Any]) -> None:
        trace = state.setdefault("trace", {})
        steps = trace.setdefault("agent_steps", [])
        steps.append(
            {
                "agent": agent,
                "ts": datetime.utcnow().isoformat(),
                "payload": payload,
            }
        )

    def _safe_prompt(self, template_name: str, context: Dict[str, Any]) -> str:
        try:
            return self.prompts.render(template_name, context)
        except Exception as e:
            return f"[prompt_render_error] {template_name}: {str(e)}"

    def _llm_json(self, messages: List[Dict[str, str]], default: Dict[str, Any]) -> Dict[str, Any]:
        fallback = json.dumps(default, ensure_ascii=False)
        raw = self.llm.chat(messages=messages, default=fallback)
        data = self.llm.extract_json(raw)
        return data if isinstance(data, dict) else default

    def _rule_evidence_from_related(self, related_rules: List[Dict[str, Any]]) -> List[str]:
        evidence: List[str] = []
        for item in related_rules:
            doc_id = str(item.get("doc_id", "")).strip()
            cls = str(item.get("classification", "")).strip()
            score = item.get("score", None)
            content = str(item.get("content", "")).strip()
            if not (doc_id or content):
                continue
            score_part = ""
            if score is not None:
                try:
                    score_part = f"(score={float(score):.3f})"
                except Exception:
                    score_part = ""
            head = "/".join([x for x in [doc_id, cls] if x]) or "rule"
            evidence.append(f"{head}{score_part}: {content[:280]}")
        return self._uniq(evidence)[:12]

    def _build_shared_context(self, state: WorkflowState) -> Dict[str, Any]:
        mem_pkg = state.get("memory_package", {}) or {}
        return {
            "section_id": state.get("section_id", ""),
            "plan_steps": state.get("plan_steps", []),
            "memory_context": state.get("memory_context", "")[:1200],
            "memory_highlights": (mem_pkg.get("hits_by_type", {}) if isinstance(mem_pkg, dict) else {}),
            "rule_evidence": state.get("rule_evidence", []),
            "coordination_payload": state.get("coordination_payload", {}) or {},
        }

    def _plan_node(self, state: WorkflowState) -> WorkflowState:
        text = state.get("content", "")[:3000]
        prompt = self._safe_prompt(
            "planner.j2",
            {
                "section_id": state.get("section_id", ""),
                "content": text,
                "memory_context": state.get("memory_context", "")[:1200],
            },
        )
        default_steps: List[str] = [
            "识别本章节核心主题与监管风险点",
            "定位可疑表述并标记证据句",
            "与规则证据逐项比对",
            "输出可执行的审评结论",
        ]
        resp = self._llm_json(
            messages=[
                {"role": "system", "content": "你是药审预审Planner，只输出JSON。"},
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        "请输出JSON对象: {\"plan_steps\": [\"...\"], \"risk_focus\": [\"...\"]}"
                    ),
                },
            ],
            default={"plan_steps": default_steps, "risk_focus": []},
        )
        steps = self._uniq([str(x) for x in resp.get("plan_steps", [])]) or default_steps
        state["plan_steps"] = steps
        self._append_trace(state, "planner", {"plan_steps": steps, "prompt": prompt, "llm": resp})
        return state

    def _retrieve_node(self, state: WorkflowState) -> WorkflowState:
        evidence = self._rule_evidence_from_related(state.get("related_rules", []))
        prompt = self._safe_prompt(
            "retriever.j2",
            {"plan_steps": state.get("plan_steps", []), "related_rules": evidence},
        )

        resp = self._llm_json(
            messages=[
                {"role": "system", "content": "你是规则证据筛选器，只输出JSON。"},
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        "请输出JSON对象: {\"rule_evidence\": [\"...\"]}，"
                        "仅保留与当前章节直接相关的证据。"
                    ),
                },
            ],
            default={"rule_evidence": evidence[:8]},
        )
        ranked = self._uniq([str(x) for x in resp.get("rule_evidence", [])])
        state["rule_evidence"] = ranked[:10] if ranked else evidence[:10]
        self._append_trace(state, "retriever", {"rule_evidence": state["rule_evidence"], "prompt": prompt, "llm": resp})
        return state

    def _context_node(self, state: WorkflowState) -> WorkflowState:
        shared = self._build_shared_context(state)
        state["shared_context"] = shared
        preview = {
            "plan_steps": shared.get("plan_steps", [])[:4],
            "rule_evidence_count": len(shared.get("rule_evidence", [])),
            "memory_types": list((shared.get("memory_highlights", {}) or {}).keys()),
            "memory_context_preview": str(shared.get("memory_context", ""))[:300],
            "coordination_keys": list((shared.get("coordination_payload", {}) or {}).keys()),
        }
        self._append_trace(state, "context_builder", {"shared_context_preview": preview})
        return state

    def _review_node(self, state: WorkflowState) -> WorkflowState:
        text = state.get("content", "")[:3200]
        shared = state.get("shared_context", {}) or {}
        mem = str(shared.get("memory_context", state.get("memory_context", "")))[:1500]
        rule_evidence = shared.get("rule_evidence", state.get("rule_evidence", []))
        prompt = self._safe_prompt(
            "reviewer.j2",
            {"content": text, "memory_context": mem, "rule_evidence": rule_evidence},
        )

        resp = self._llm_json(
            messages=[
                {"role": "system", "content": "你是药审Reviewer，只输出JSON。"},
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        "请输出JSON对象: {\"findings_draft\": [\"...\"]}。"
                        "每条结论要具体、可定位、可核查。"
                    ),
                },
            ],
            default={"findings_draft": []},
        )

        findings = self._uniq([str(x) for x in resp.get("findings_draft", [])])

        if not findings:
            if self._contains_any(text, self.RISK_KEYWORDS["contraindication"]):
                findings.append("疑似缺少禁忌/适用限制的完整说明")
            if self._contains_any(text, self.RISK_KEYWORDS["adverse_reaction"]):
                findings.append("不良反应描述可能不完整，建议补充分级与发生率")
            if self._contains_any(text, self.RISK_KEYWORDS["dosage"]):
                findings.append("剂量或给药方案存在歧义，建议明确单位与调整条件")
        state["findings_draft"] = self._uniq(findings)
        self._append_trace(state, "reviewer", {"findings_draft": state["findings_draft"], "prompt": prompt, "llm": resp})
        return state

    def _reflect_node(self, state: WorkflowState) -> WorkflowState:
        prompt = self._safe_prompt(
            "reflector.j2",
            {
                "findings_draft": state.get("findings_draft", []),
                "rule_evidence": state.get("rule_evidence", []),
                "plan_steps": state.get("plan_steps", []),
            },
        )
        resp = self._llm_json(
            messages=[
                {"role": "system", "content": "你是反思校正器Reflector，只输出JSON。"},
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        "请输出JSON对象: {\"findings_refined\": [\"...\"], \"notes\": [\"...\"]}。"
                        "去重、去模糊、补充证据关联。"
                    ),
                },
            ],
            default={"findings_refined": state.get("findings_draft", []), "notes": []},
        )
        refined = self._uniq([str(x) for x in resp.get("findings_refined", [])])
        if not refined:
            refined = self._uniq(state.get("findings_draft", []))
        state["findings_refined"] = refined
        self._append_trace(state, "reflector", {"findings_refined": refined, "prompt": prompt, "llm": resp})
        return state

    def _solve_node(self, state: WorkflowState) -> WorkflowState:
        findings = self._uniq(state.get("findings_refined", []))
        evidence_count = len(state.get("rule_evidence", []))
        base_score = min(len(findings) / 8.0, 1.0)
        evidence_bonus = min(evidence_count * 0.03, 0.15)
        score = min(base_score + evidence_bonus, 1.0)

        prompt = self._safe_prompt("synthesizer.j2", {"findings": findings, "score": score})
        resp = self._llm_json(
            messages=[
                {"role": "system", "content": "你是结论综合器Synthesizer，只输出JSON。"},
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        "请输出JSON对象: {\"conclusion\": \"...\", \"score\": 0~1}。"
                    ),
                },
            ],
            default={"conclusion": "; ".join(findings) if findings else "No obvious issue found", "score": score},
        )

        final_conclusion = str(resp.get("conclusion", "")).strip() or (
            "; ".join(findings) if findings else "No obvious issue found"
        )
        try:
            score = float(resp.get("score", score))
        except Exception:
            pass
        score = max(0.0, min(1.0, score))

        state["findings"] = findings
        state["score"] = score
        state["conclusion"] = final_conclusion

        self._append_trace(
            state,
            "synthesizer",
            {"findings": findings, "score": score, "conclusion": final_conclusion, "prompt": prompt, "llm": resp},
        )
        trace = state.setdefault("trace", {})
        trace["workflow_version"] = "v4_collab_context"
        trace["summary"] = {
            "plan_steps": state.get("plan_steps", []),
            "rule_evidence_count": len(state.get("rule_evidence", [])),
            "findings_count": len(findings),
            "score": score,
        }
        return state

    def _build_graph(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("plan", self._plan_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("context", self._context_node)
        graph.add_node("review", self._review_node)
        graph.add_node("reflect", self._reflect_node)
        graph.add_node("solve", self._solve_node)
        graph.set_entry_point("plan")
        graph.add_edge("plan", "retrieve")
        graph.add_edge("retrieve", "context")
        graph.add_edge("context", "review")
        graph.add_edge("review", "reflect")
        graph.add_edge("reflect", "solve")
        graph.add_edge("solve", END)
        return graph.compile()

    def run(self, state: WorkflowState) -> WorkflowState:
        state.setdefault("trace", {})
        state["trace"]["started_at"] = datetime.utcnow().isoformat()
        if self.graph is not None:
            out = self.graph.invoke(state)
            out.setdefault("trace", {})["finished_at"] = datetime.utcnow().isoformat()
            return out
        s = self._plan_node(state)
        s = self._retrieve_node(s)
        s = self._context_node(s)
        s = self._review_node(s)
        s = self._reflect_node(s)
        s = self._solve_node(s)
        s.setdefault("trace", {})["finished_at"] = datetime.utcnow().isoformat()
        return s
