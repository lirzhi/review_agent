from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from agent.agent_backend.database.mysql.db_model import PreReviewSectionConclusion, PreReviewSectionTrace


@dataclass
class SectionConclusionRecord:
    """Structured section conclusion payload used by repository adapters."""

    run_id: str
    section_id: str
    section_name: str
    conclusion: str
    highlighted_issues: List[Dict[str, Any]] = field(default_factory=list)
    linked_rules: List[str] = field(default_factory=list)
    risk_level: str = "low"
    create_time: datetime | None = None

    def to_entity(self) -> PreReviewSectionConclusion:
        """Build ORM entity for persistence."""
        return PreReviewSectionConclusion(
            run_id=self.run_id,
            section_id=self.section_id,
            section_name=self.section_name,
            conclusion=self.conclusion,
            highlighted_issues=json.dumps(self.highlighted_issues, ensure_ascii=False),
            linked_rules=json.dumps(self.linked_rules, ensure_ascii=False),
            risk_level=self.risk_level,
            create_time=self.create_time or datetime.now(),
        )

    @classmethod
    def from_entity(cls, entity: PreReviewSectionConclusion) -> "SectionConclusionRecord":
        """Convert ORM entity back to structured payload."""
        return cls(
            run_id=entity.run_id,
            section_id=entity.section_id,
            section_name=entity.section_name,
            conclusion=entity.conclusion,
            highlighted_issues=PreReviewRepository.load_findings(entity.highlighted_issues),
            linked_rules=PreReviewRepository.load_string_list(entity.linked_rules),
            risk_level=entity.risk_level or "low",
            create_time=entity.create_time,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize record for service/controller responses."""
        return {
            "run_id": self.run_id,
            "section_id": self.section_id,
            "section_name": self.section_name,
            "conclusion": self.conclusion,
            "highlighted_issues": list(self.highlighted_issues),
            "linked_rules": list(self.linked_rules),
            "risk_level": self.risk_level,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
        }


@dataclass
class SectionTraceRecord:
    """Structured section trace payload used by repository adapters."""

    run_id: str
    section_id: str
    trace_payload: Dict[str, Any]
    create_time: datetime | None = None

    def to_entity(self) -> PreReviewSectionTrace:
        """Build ORM entity for persistence."""
        return PreReviewSectionTrace(
            run_id=self.run_id,
            section_id=self.section_id,
            trace_json=PreReviewRepository.dump_trace_payload(self.trace_payload),
            create_time=self.create_time or datetime.now(),
        )

    @classmethod
    def from_entity(cls, entity: PreReviewSectionTrace) -> "SectionTraceRecord":
        """Convert ORM entity back to structured trace payload."""
        return cls(
            run_id=entity.run_id,
            section_id=entity.section_id,
            trace_payload=PreReviewRepository.load_trace_payload(entity.trace_json),
            create_time=entity.create_time,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trace record for responses."""
        payload = dict(self.trace_payload)
        payload.update(
            {
                "run_id": self.run_id,
                "section_id": self.section_id,
                "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
            }
        )
        return payload


class PreReviewRepository:
    """Structured serializer/deserializer for pre-review conclusions and traces."""

    @staticmethod
    def normalize_finding(item: Any) -> Dict[str, Any]:
        """Normalize legacy string or dict finding to a structured dict."""
        if isinstance(item, dict):
            title = str(item.get("title", "") or "").strip()
            if not title:
                return {}
            return {
                "title": title,
                "problem_type": str(item.get("problem_type", "") or "").strip(),
                "severity": str(item.get("severity", "low") or "low").strip().lower(),
                "evidence": str(item.get("evidence", "") or "").strip(),
                "recommendation": str(item.get("recommendation", "") or "").strip(),
                "metadata": item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {},
            }
        title = str(item or "").strip()
        if not title:
            return {}
        return {
            "title": title,
            "problem_type": "",
            "severity": "low",
            "evidence": "",
            "recommendation": "",
            "metadata": {},
        }

    @classmethod
    def load_findings(cls, raw: str | None) -> List[Dict[str, Any]]:
        """Load structured findings from JSON text."""
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            return []
        findings: List[Dict[str, Any]] = []
        for item in data if isinstance(data, list) else []:
            normalized = cls.normalize_finding(item)
            if normalized:
                findings.append(normalized)
        return findings

    @staticmethod
    def load_string_list(raw: str | None) -> List[str]:
        """Load a list of strings from JSON text."""
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            return []
        return [str(item) for item in data] if isinstance(data, list) else []

    @classmethod
    def dump_findings(cls, findings: List[Any]) -> str:
        """Dump structured findings to JSON text."""
        normalized = []
        for item in findings or []:
            payload = cls.normalize_finding(item)
            if payload:
                normalized.append(payload)
        return json.dumps(normalized, ensure_ascii=False)

    @classmethod
    def dump_trace_payload(cls, payload: Dict[str, Any]) -> str:
        """Dump trace payload and ensure `agent.findings` stays structured."""
        data = dict(payload or {})
        agent = data.get("agent", {})
        if isinstance(agent, dict):
            agent["findings"] = [cls.normalize_finding(item) for item in agent.get("findings", []) if cls.normalize_finding(item)]
            data["agent"] = agent
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def load_trace_payload(cls, raw: str | None) -> Dict[str, Any]:
        """Load trace payload and normalize `agent.findings`."""
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        agent = data.get("agent", {})
        if isinstance(agent, dict):
            agent["findings"] = [cls.normalize_finding(item) for item in agent.get("findings", []) if cls.normalize_finding(item)]
            data["agent"] = agent
        return data if isinstance(data, dict) else {}
