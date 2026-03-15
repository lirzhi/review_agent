from flask import Flask

from agent.agent_backend.controller.file_controller import file_bp
from agent.agent_backend.controller.knowledge_controller import knowledge_bp
from agent.agent_backend.controller.pre_review_controller import pre_review_bp
from agent.agent_backend.controller.qa_controller import qa_bp
from agent.agent_backend.controller.rl_controller import rl_bp


def register_controllers(app: Flask) -> None:
    print("[DEBUG] enter register_controllers | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    app.register_blueprint(file_bp)
    app.register_blueprint(knowledge_bp)
    app.register_blueprint(pre_review_bp)
    app.register_blueprint(qa_bp)
    app.register_blueprint(rl_bp)
