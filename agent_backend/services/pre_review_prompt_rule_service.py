from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from agent.agent_backend.config.settings import settings
from agent.agent_backend.database.mysql.db_model import PreReviewPromptRule
from agent.agent_backend.utils.file_util import ensure_dir_exists


SYSTEM_RULE_PROJECT_ID = "000000000000"

TASK_TEMPLATE_MAP = {
    "planner": "chapter_planner.j2",
    "reviewer": "chapter_reviewer.j2",
    "feedback_analyzer": "feedback_analyzer.j2",
    "feedback_optimizer": "feedback_optimizer.j2",
    "meta_reflector": "meta_reflector.j2",
}

DEFAULT_RULE_FILES: Dict[str, List[Dict[str, Any]]] = {
    "planner_rules.json": [
        {
            "task_type": "planner",
            "template_name": "chapter_planner.j2",
            "route_key": "pre_review/planner",
            "scope_type": "global",
            "rule_code": "planner_short_query_default",
            "rule_name": "Planner短Query约束",
            "priority": 10,
            "rule_text": "生成 query_list 时，优先使用药品名称、章节主题、产品类型和关注点；禁止只输出章节编号、目录编号或章节路径片段。",
        },
        {
            "task_type": "planner",
            "template_name": "chapter_planner.j2",
            "route_key": "pre_review/planner",
            "scope_type": "global",
            "rule_code": "planner_focus_first",
            "rule_name": "Planner关注点优先",
            "priority": 20,
            "rule_text": "当 focus_points 非空时，至少一半 query 必须直接围绕 focus_points 组织；当 focus_points 为空时，也不能复制大段原文，而应围绕 section_name 生成 3 到 5 条短 query。",
        },
    ],
    "reviewer_rules.json": [
        {
            "task_type": "reviewer",
            "template_name": "chapter_reviewer.j2",
            "route_key": "pre_review/reviewer",
            "scope_type": "global",
            "rule_code": "reviewer_focus_alignment",
            "rule_name": "Reviewer关注点对齐",
            "priority": 10,
            "rule_text": "输出 supported_points、missing_points、questions 时，必须逐条对照 focus_points；不能遗漏任何已给出的章节关注点。",
        },
        {
            "task_type": "reviewer",
            "template_name": "chapter_reviewer.j2",
            "route_key": "pre_review/reviewer",
            "scope_type": "global",
            "rule_code": "reviewer_evidence_boundary",
            "rule_name": "Reviewer证据边界",
            "priority": 20,
            "rule_text": "历史经验只能作为风险提醒，不得替代法规依据；若 retrieved_materials 和原文都不能直接支持结论，只能输出 insufficient_information 或提出补充问题。",
        },
    ],
    "feedback_analyzer_rules.json": [
        {
            "task_type": "feedback_analyzer",
            "template_name": "feedback_analyzer.j2",
            "route_key": "feedback/analyzer",
            "scope_type": "global",
            "rule_code": "feedback_taxonomy_fixed",
            "rule_name": "固定归因taxonomy",
            "priority": 10,
            "rule_text": "error_types 必须优先落在固定 taxonomy 中；如果 trace 中存在 retrieval_error_breakdown 和 effective_queries，应优先基于 trace 证据归因，而不是只复述用户反馈。",
        }
    ],
    "feedback_optimizer_rules.json": [
        {
            "task_type": "feedback_optimizer",
            "template_name": "feedback_optimizer.j2",
            "route_key": "feedback/optimizer",
            "scope_type": "global",
            "rule_code": "optimizer_min_patch_only",
            "rule_name": "最小Patch原则",
            "priority": 10,
            "rule_text": "只允许生成最小 patch；query 问题只改 planner，推理问题只改 reviewer，表达问题只改 wording，不得重写整份模板。",
        }
    ],
}


class PreReviewPromptRuleService:
    def __init__(self) -> None:
        self.rule_dir = Path(settings.rule_data_dir)
        ensure_dir_exists(str(self.rule_dir))
        self._ensure_seed_files()

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    def _ensure_seed_files(self) -> None:
        for file_name, rules in DEFAULT_RULE_FILES.items():
            path = self.rule_dir / file_name
            if path.exists():
                continue
            path.write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _load_seed_rules(self) -> List[Dict[str, Any]]:
        loaded: List[Dict[str, Any]] = []
        for path in sorted(self.rule_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, list):
                continue
            for item in payload:
                if not isinstance(item, dict):
                    continue
                loaded.append({**item, "_source_file": path.name})
        return loaded

    def bootstrap_system_rules(self, session) -> None:
        now = self._now()
        for item in self._load_seed_rules():
            task_type = str(item.get("task_type", "") or "").strip()
            template_name = str(item.get("template_name", "") or TASK_TEMPLATE_MAP.get(task_type, "")).strip()
            rule_text = str(item.get("rule_text", "") or "").strip()
            rule_code = str(item.get("rule_code", "") or "").strip()
            if not task_type or not template_name or not rule_text or not rule_code:
                continue
            existing = (
                session.query(PreReviewPromptRule)
                .filter(
                    PreReviewPromptRule.project_id == SYSTEM_RULE_PROJECT_ID,
                    PreReviewPromptRule.task_type == task_type,
                    PreReviewPromptRule.rule_code == rule_code,
                )
                .first()
            )
            if existing is None:
                session.add(
                    PreReviewPromptRule(
                        rule_id=f"rule_{uuid.uuid4().hex[:16]}",
                        project_id=SYSTEM_RULE_PROJECT_ID,
                        task_type=task_type,
                        template_name=template_name,
                        route_key=str(item.get("route_key", "") or "").strip(),
                        scope_type=str(item.get("scope_type", "") or "global").strip() or "global",
                        rule_code=rule_code,
                        rule_name=str(item.get("rule_name", "") or task_type).strip(),
                        section_id=str(item.get("section_id", "") or "").strip() or None,
                        section_name=str(item.get("section_name", "") or "").strip() or None,
                        review_domain=str(item.get("review_domain", "") or "").strip() or None,
                        product_type=str(item.get("product_type", "") or "").strip() or None,
                        registration_class=str(item.get("registration_class", "") or "").strip() or None,
                        priority=int(item.get("priority", 100) or 100),
                        rule_text=rule_text,
                        source_type="seed",
                        is_active=bool(item.get("is_active", True)),
                        payload_json=json.dumps(item, ensure_ascii=False),
                        create_time=now,
                        update_time=now,
                    )
                )
                continue
            existing.template_name = template_name
            existing.route_key = str(item.get("route_key", "") or "").strip()
            existing.scope_type = str(item.get("scope_type", "") or "global").strip() or "global"
            existing.rule_name = str(item.get("rule_name", "") or task_type).strip()
            existing.section_id = str(item.get("section_id", "") or "").strip() or None
            existing.section_name = str(item.get("section_name", "") or "").strip() or None
            existing.review_domain = str(item.get("review_domain", "") or "").strip() or None
            existing.product_type = str(item.get("product_type", "") or "").strip() or None
            existing.registration_class = str(item.get("registration_class", "") or "").strip() or None
            existing.priority = int(item.get("priority", 100) or 100)
            existing.rule_text = rule_text
            existing.is_active = bool(item.get("is_active", True))
            existing.payload_json = json.dumps(item, ensure_ascii=False)
            existing.update_time = now

    def ensure_project_rules(self, session, project_id: str) -> None:
        self.bootstrap_system_rules(session)
        existing = (
            session.query(PreReviewPromptRule)
            .filter(PreReviewPromptRule.project_id == project_id)
            .count()
        )
        if existing > 0:
            return
        system_rules = (
            session.query(PreReviewPromptRule)
            .filter(PreReviewPromptRule.project_id == SYSTEM_RULE_PROJECT_ID)
            .order_by(PreReviewPromptRule.priority.asc(), PreReviewPromptRule.id.asc())
            .all()
        )
        now = self._now()
        for item in system_rules:
            session.add(
                PreReviewPromptRule(
                    rule_id=f"rule_{uuid.uuid4().hex[:16]}",
                    project_id=project_id,
                    task_type=item.task_type,
                    template_name=item.template_name,
                    route_key=item.route_key,
                    scope_type="project" if item.scope_type == "global" else item.scope_type,
                    rule_code=item.rule_code,
                    rule_name=item.rule_name,
                    section_id=item.section_id,
                    section_name=item.section_name,
                    review_domain=item.review_domain,
                    product_type=item.product_type,
                    registration_class=item.registration_class,
                    priority=item.priority,
                    rule_text=item.rule_text,
                    source_type="project_copy",
                    is_active=bool(item.is_active),
                    payload_json=item.payload_json,
                    create_time=now,
                    update_time=now,
                )
            )

    @staticmethod
    def _scope_matches(rule: PreReviewPromptRule, section_id: str, section_name: str, review_domain: str, product_type: str, registration_class: str) -> bool:
        if rule.section_id and str(rule.section_id).strip() not in {"", "all"}:
            target = str(rule.section_id).strip()
            if section_id != target and not section_id.startswith(f"{target}."):
                return False
        if rule.section_name and str(rule.section_name).strip() not in {"", "all"}:
            target = str(rule.section_name).strip()
            if target not in section_name:
                return False
        if rule.review_domain and str(rule.review_domain).strip() not in {"", "all"}:
            if str(rule.review_domain).strip() != review_domain:
                return False
        if rule.product_type and str(rule.product_type).strip() not in {"", "all"}:
            if str(rule.product_type).strip() != product_type:
                return False
        if rule.registration_class and str(rule.registration_class).strip() not in {"", "all"}:
            if str(rule.registration_class).strip() not in registration_class:
                return False
        return True

    def resolve_rules(
        self,
        session,
        project_id: str,
        task_type: str,
        section_id: str = "",
        section_name: str = "",
        review_domain: str = "",
        product_type: str = "",
        registration_class: str = "",
    ) -> List[PreReviewPromptRule]:
        rows = (
            session.query(PreReviewPromptRule)
            .filter(
                PreReviewPromptRule.project_id == project_id,
                PreReviewPromptRule.is_active == 1,
                PreReviewPromptRule.task_type.in_([task_type, "all"]),
            )
            .order_by(PreReviewPromptRule.priority.asc(), PreReviewPromptRule.id.asc())
            .all()
        )
        return [
            row
            for row in rows
            if self._scope_matches(
                row,
                section_id=str(section_id or "").strip(),
                section_name=str(section_name or "").strip(),
                review_domain=str(review_domain or "").strip(),
                product_type=str(product_type or "").strip(),
                registration_class=str(registration_class or "").strip(),
            )
        ]

    def compose_prompt_config(
        self,
        session,
        project_id: str,
        base_prompt_config: Dict[str, Any] | None,
        task_type: str,
        section_id: str = "",
        section_name: str = "",
        review_domain: str = "",
        product_type: str = "",
        registration_class: str = "",
    ) -> Dict[str, Any]:
        self.ensure_project_rules(session, project_id)
        prompt_config = dict(base_prompt_config or {})
        bundle = prompt_config.get("prompt_bundle", {}) if isinstance(prompt_config.get("prompt_bundle", {}), dict) else {}
        bundle = dict(bundle)
        template_suffixes = bundle.get("template_suffixes", {}) if isinstance(bundle.get("template_suffixes", {}), dict) else {}
        template_suffixes = dict(template_suffixes)
        active_rules = bundle.get("active_rules", {}) if isinstance(bundle.get("active_rules", {}), dict) else {}
        active_rules = dict(active_rules)

        matched = self.resolve_rules(
            session=session,
            project_id=project_id,
            task_type=task_type,
            section_id=section_id,
            section_name=section_name,
            review_domain=review_domain,
            product_type=product_type,
            registration_class=registration_class,
        )
        template_name = TASK_TEMPLATE_MAP.get(task_type, "")
        suffix_lines = [str(item.rule_text).strip() for item in matched if str(item.rule_text or "").strip()]
        if template_name and suffix_lines:
            existing = str(template_suffixes.get(template_name, "") or "").strip()
            template_suffixes[template_name] = "\n".join([x for x in [existing, *suffix_lines] if x]).strip()
        active_rules[task_type] = [
            {
                "rule_id": str(item.rule_id or ""),
                "rule_code": str(item.rule_code or ""),
                "rule_name": str(item.rule_name or ""),
                "template_name": str(item.template_name or ""),
                "priority": int(item.priority or 0),
                "scope_type": str(item.scope_type or ""),
                "source_type": str(item.source_type or ""),
            }
            for item in matched
        ]
        bundle["template_suffixes"] = template_suffixes
        bundle["active_rules"] = active_rules
        prompt_config["prompt_bundle"] = bundle
        return prompt_config
