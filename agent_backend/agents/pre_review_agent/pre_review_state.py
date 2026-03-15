from dataclasses import dataclass, field
from typing import List


@dataclass
class PreReviewState:
    doc_id: str
    section_id: str
    content: str
    memory_context: str = ""
    findings: List[str] = field(default_factory=list)
    score: float = 0.0

