import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
_load_env_file(ROOT / ".env")


def _resolve_data_path(path_str: str, default_path: Path) -> str:
    value = (path_str or "").strip()
    if not value:
        return str(default_path)
    p = Path(value)
    if p.is_absolute():
        return str(p)
    normalized = value.replace("\\", "/")
    if normalized.startswith("agent/"):
        return str(REPO_ROOT / p)
    return str(ROOT / p)


def _resolve_mysql_url(url: str) -> str:
    value = (url or "").strip()
    if not value.startswith("sqlite:///"):
        return value
    raw_path = value.replace("sqlite:///", "", 1).strip()
    p = Path(raw_path)
    if p.is_absolute():
        return value
    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("agent/"):
        return f"sqlite:///{(REPO_ROOT / p).as_posix()}"
    return f"sqlite:///{(ROOT / p).as_posix()}"


@dataclass
class Settings:
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "5001"))
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    upload_dir: str = _resolve_data_path(
        os.getenv("UPLOAD_DIR", ""),
        ROOT / "data" / "uploads",
    )
    parse_dir: str = _resolve_data_path(
        os.getenv("PARSE_DIR", ""),
        ROOT / "data" / "parsed",
    )
    submission_upload_dir: str = _resolve_data_path(
        os.getenv("SUBMISSION_UPLOAD_DIR", ""),
        ROOT / "data" / "submissions" / "uploads",
    )
    submission_parse_dir: str = _resolve_data_path(
        os.getenv("SUBMISSION_PARSE_DIR", ""),
        ROOT / "data" / "submissions" / "parsed",
    )
    report_dir: str = _resolve_data_path(
        os.getenv("REPORT_DIR", ""),
        ROOT / "data" / "reports",
    )

    mysql_url: str = _resolve_mysql_url(
        os.getenv("MYSQL_URL", f"sqlite:///{(ROOT / 'data' / 'agent.db').as_posix()}")
    )
    redis_host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

    es_url: str = os.getenv("ES_URL", "http://127.0.0.1:9200")
    vector_collection: str = os.getenv("VECTOR_COLLECTION", "agent_collection")


settings = Settings()
