from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from agent.agent_backend.database.mysql.mysql_conn import Base, MysqlConnection


class FileInfo(Base):
    __tablename__ = "file_info"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(256), nullable=False, unique=True, index=True)
    file_name = Column(String(256), nullable=False)
    file_path = Column(String(512), nullable=False, unique=True)
    file_type = Column(String(64), nullable=False)
    classification = Column(String(128), nullable=False, default="other")
    affect_range = Column(String(128), nullable=False, default="other")
    profession_classification = Column(String(128), nullable=False, default="other")
    registration_scope = Column(String(128), nullable=False, default="other")
    registration_path = Column(Text, nullable=True)
    experience_type = Column(String(64), nullable=False, default="other")
    is_chunked = Column(Boolean, default=False)
    chunk_ids = Column(Text, nullable=True)
    chunk_size = Column(Integer, nullable=True)
    index_status = Column(String(32), default="pending")  # pending/running/completed/failed
    index_error = Column(Text, nullable=True)
    indexed_at = Column(DateTime, nullable=True)
    vector_count = Column(Integer, nullable=True)
    is_deleted = Column(Boolean, default=False)
    create_time = Column(String(64), nullable=False)
    review_status = Column(Integer, default=0)  # 0: not reviewed, 1: reviewed
    review_time = Column(DateTime, nullable=True)


class RequireInfo(Base):
    __tablename__ = "require_info"
    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(String(256), nullable=False, index=True)
    parent_section = Column(String(256), nullable=False, index=True)
    requirement = Column(String(1024), nullable=False)
    is_origin = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    create_time = Column(String(64), nullable=False)


class ReportContent(Base):
    __tablename__ = "report_content"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(256), nullable=False, index=True)
    section_id = Column(String(256), nullable=False, index=True)
    content = Column(Text, nullable=False)
    create_time = Column(DateTime, nullable=False)


class PharmacyInfo(Base):
    __tablename__ = "pharmacy_info"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False, unique=True)
    prescription = Column(Text, nullable=True)
    characteristic = Column(Text, nullable=True)
    identification = Column(Text, nullable=True)
    inspection = Column(Text, nullable=True)
    content_determination = Column(Text, nullable=True)
    category = Column(String(256), nullable=True)
    storage = Column(Text, nullable=True)
    preparation = Column(Text, nullable=True)
    specification = Column(String(256), nullable=True)


class QAInfo(Base):
    __tablename__ = "qa_info"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(256), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)


# ---------- Knowledge Base Domain ----------
class KnowledgeTag(Base):
    __tablename__ = "knowledge_tag"

    id = Column(Integer, primary_key=True, index=True)
    tag_name = Column(String(128), nullable=False, unique=True, index=True)
    description = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True)


class KnowledgeFileTag(Base):
    __tablename__ = "knowledge_file_tag"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(256), ForeignKey("file_info.doc_id"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("knowledge_tag.id"), nullable=False, index=True)


class PharmacopeiaEntry(Base):
    __tablename__ = "pharmacopeia_entry"
    __table_args__ = (
        UniqueConstraint("drug_name", "affect_range", name="uq_pharmacopeia_entry_name_range"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(String(64), nullable=False, unique=True, index=True)
    drug_name = Column(String(256), nullable=False, index=True)
    affect_range = Column(String(64), nullable=False, default="化学药", index=True)
    prescription = Column(Text, nullable=True)
    character = Column(Text, nullable=True)
    identification = Column(Text, nullable=True)
    inspection = Column(Text, nullable=True)
    inspection_variant = Column(Text, nullable=True)
    assay = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    storage = Column(Text, nullable=True)
    specification = Column(Text, nullable=True)
    related_substances = Column(Text, nullable=True)
    potency_assay = Column(Text, nullable=True)
    active_ingredient_content = Column(Text, nullable=True)
    preparation_method = Column(Text, nullable=True)
    preparation_requirement = Column(Text, nullable=True)
    dosage_form = Column(Text, nullable=True)
    prepared_into = Column(Text, nullable=True)
    production_requirement = Column(Text, nullable=True)
    labeling = Column(Text, nullable=True)
    other = Column(Text, nullable=True)
    raw_payload = Column(Text, nullable=True)
    source_file_name = Column(String(256), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=False)


# ---------- Pre-review Domain ----------
class PreReviewProject(Base):
    __tablename__ = "pre_review_project"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String(64), nullable=False, unique=True, index=True)
    project_name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    registration_scope = Column(String(64), nullable=True)
    registration_path = Column(Text, nullable=True)
    registration_leaf = Column(String(256), nullable=True)
    registration_description = Column(Text, nullable=True)
    status = Column(String(32), default="created")  # created/running/completed/archived
    progress = Column(Float, default=0.0)  # 0~1
    owner = Column(String(128), nullable=True)
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=False)
    is_deleted = Column(Boolean, default=False)


class PreReviewRun(Base):
    __tablename__ = "pre_review_run"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    project_id = Column(String(64), ForeignKey("pre_review_project.project_id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False, default=1)
    source_doc_id = Column(String(256), nullable=False, index=True)
    strategy = Column(String(128), default="plan_and_solve+reflection")
    accuracy = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    create_time = Column(DateTime, nullable=False)
    finish_time = Column(DateTime, nullable=True)


class PreReviewSectionConclusion(Base):
    __tablename__ = "pre_review_section_conclusion"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("pre_review_run.run_id"), nullable=False, index=True)
    section_id = Column(String(128), nullable=False, index=True)
    section_name = Column(String(256), nullable=False)
    conclusion = Column(Text, nullable=False)
    highlighted_issues = Column(Text, nullable=True)  # JSON string
    linked_rules = Column(Text, nullable=True)  # JSON string
    risk_level = Column(String(32), default="low")  # low/medium/high
    create_time = Column(DateTime, nullable=False)


class PreReviewSectionTrace(Base):
    __tablename__ = "pre_review_section_trace"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("pre_review_run.run_id"), nullable=False, index=True)
    section_id = Column(String(128), nullable=False, index=True)
    trace_json = Column(Text, nullable=False)  # JSON string of multi-agent trace
    create_time = Column(DateTime, nullable=False)


class PreReviewFeedback(Base):
    __tablename__ = "pre_review_feedback"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("pre_review_run.run_id"), nullable=False, index=True)
    section_id = Column(String(128), nullable=True, index=True)
    feedback_type = Column(String(32), nullable=False)  # valid/false_positive/missed
    feedback_text = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)
    operator = Column(String(128), nullable=True)
    create_time = Column(DateTime, nullable=False)


class PreReviewSubmissionFile(Base):
    __tablename__ = "pre_review_submission_file"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(256), nullable=False, unique=True, index=True)
    project_id = Column(String(64), ForeignKey("pre_review_project.project_id"), nullable=False, index=True)
    file_name = Column(String(256), nullable=False)
    file_path = Column(String(512), nullable=False, unique=True)
    file_type = Column(String(64), nullable=False)
    material_category = Column(String(64), nullable=False, default="other")
    section_id = Column(String(128), nullable=True, index=True)
    section_code = Column(String(128), nullable=True, index=True)
    section_name = Column(String(256), nullable=True)
    section_path = Column(Text, nullable=True)
    is_chunked = Column(Boolean, default=False)
    chunk_ids = Column(Text, nullable=True)
    chunk_size = Column(Integer, nullable=True)
    is_deleted = Column(Boolean, default=False)
    create_time = Column(DateTime, nullable=False)


class PreReviewSubmissionSectionContent(Base):
    __tablename__ = "pre_review_submission_section_content"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(256), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("pre_review_project.project_id"), nullable=False, index=True)
    section_id = Column(String(128), nullable=False, index=True)
    section_code = Column(String(128), nullable=True, index=True)
    section_name = Column(String(256), nullable=True)
    content = Column(Text, nullable=False)
    content_preview = Column(Text, nullable=True)
    source_parser = Column(String(64), nullable=True)
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=False)


class PreReviewSectionConcern(Base):
    __tablename__ = "pre_review_section_concern"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String(64), ForeignKey("pre_review_project.project_id"), nullable=False, index=True)
    section_id = Column(String(128), nullable=False, index=True)
    section_code = Column(String(128), nullable=True, index=True)
    section_name = Column(String(256), nullable=True)
    concern_points = Column(Text, nullable=False)  # JSON string
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=False)


class PreReviewPromptRule(Base):
    __tablename__ = "pre_review_prompt_rule"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(String(128), nullable=False, unique=True, index=True)
    project_id = Column(String(64), nullable=False, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    template_name = Column(String(128), nullable=False)
    route_key = Column(String(128), nullable=True, index=True)
    scope_type = Column(String(32), nullable=False, default="project", index=True)
    rule_code = Column(String(128), nullable=False, index=True)
    rule_name = Column(String(256), nullable=False)
    section_id = Column(String(128), nullable=True, index=True)
    section_name = Column(String(256), nullable=True, index=True)
    review_domain = Column(String(64), nullable=True, index=True)
    product_type = Column(String(64), nullable=True, index=True)
    registration_class = Column(String(256), nullable=True, index=True)
    priority = Column(Integer, nullable=False, default=100)
    rule_text = Column(Text, nullable=False)
    source_type = Column(String(32), nullable=False, default="seed")
    is_active = Column(Boolean, default=True, index=True)
    payload_json = Column(Text, nullable=True)
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=False)


class PreReviewSectionOutput(Base):
    __tablename__ = "pre_review_section_output"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("pre_review_run.run_id"), nullable=False, index=True)
    section_id = Column(String(128), nullable=False, index=True)
    section_name = Column(String(256), nullable=False)
    schema_version = Column(String(64), nullable=False, default="chapter_review_v1")
    output_json = Column(Text, nullable=False)
    create_time = Column(DateTime, nullable=False)


class PreReviewFeedbackAnalysisResult(Base):
    __tablename__ = "pre_review_feedback_analysis_result"

    id = Column(Integer, primary_key=True, index=True)
    feedback_key = Column(String(128), nullable=False, index=True)
    run_id = Column(String(64), nullable=False, index=True)
    section_id = Column(String(128), nullable=True, index=True)
    analysis_json = Column(Text, nullable=False)
    create_time = Column(DateTime, nullable=False)


class PreReviewPatchRegistry(Base):
    __tablename__ = "pre_review_patch_registry"

    id = Column(Integer, primary_key=True, index=True)
    patch_id = Column(String(128), nullable=False, unique=True, index=True)
    run_id = Column(String(64), nullable=False, index=True)
    section_id = Column(String(128), nullable=True, index=True)
    patch_type = Column(String(64), nullable=False)
    target_agent = Column(String(64), nullable=False)
    target_scope = Column(String(256), nullable=True)
    trigger_condition = Column(Text, nullable=True)
    patch_content = Column(Text, nullable=False)
    source_feedback_key = Column(String(128), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="candidate")
    version = Column(Integer, nullable=False, default=1)
    payload_json = Column(Text, nullable=True)
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=False)


class PreReviewExperienceMemory(Base):
    __tablename__ = "pre_review_experience_memory"

    id = Column(Integer, primary_key=True, index=True)
    experience_id = Column(String(128), nullable=False, unique=True, index=True)
    scope_type = Column(String(64), nullable=False, index=True)
    scope_key = Column(String(256), nullable=False, index=True)
    experience_type = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source_feedback_ids = Column(Text, nullable=True)
    trigger_conditions = Column(Text, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="active")
    payload_json = Column(Text, nullable=True)
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=False)


if __name__ == "__main__":
    db_conn = MysqlConnection()
    db_conn.recreate_all()

