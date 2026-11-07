"""AegisOps configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "AegisOps"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = False

    # API
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM (Groq)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    llm_max_retries: int = 3
    llm_timeout_seconds: int = 30
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    use_llm_reasoner: bool = True

    # MLflow
    mlflow_enabled: bool = True
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    mlflow_experiment_name: str = "aegisops-anomaly"

    # RAG
    chroma_persist_dir: str = "./data/chroma"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    retriever_top_k: int = 10
    reranker_top_k: int = 5
    rag_enabled: bool = True

    # Database
    database_url: str = "sqlite:///./data/aegisops.db"

    # Guardrails
    pii_redaction_enabled: bool = True
    dangerous_commands_blocked: bool = True

    # Paths
    base_dir: Path = Path(__file__).resolve().parent
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    @property
    def incidents_dir(self) -> Path:
        return self.data_dir / "incidents"

    @property
    def runbooks_dir(self) -> Path:
        return self.data_dir / "runbooks"

    @property
    def metrics_dir(self) -> Path:
        return self.data_dir / "metrics"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def traces_dir(self) -> Path:
        return self.data_dir / "traces"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"


@lru_cache
def get_settings() -> Settings:
    return Settings()