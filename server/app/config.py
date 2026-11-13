"""Configuracao da Plataforma (Trilho B).

Le variaveis de ambiente do .env (nunca commitado). Nada de credenciais
hardcoded aqui; segredos vivem so no ambiente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # carregamento opcional do .env; ausencia nao quebra producao
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv e conveniencia de dev
    pass


def _db_path_from_url(url: str) -> str:
    """Aceita DATABASE_URL no formato sqlite:///./arquivo.db ou um caminho puro."""
    prefix = "sqlite:///"
    if url.startswith(prefix):
        return url[len(prefix) :]
    return url


@dataclass(frozen=True)
class Settings:
    database_path: str
    aws_region: str
    bedrock_model_id: str | None
    # Perfis bloqueados sincronamente no POST /campaigns (403 imediato).
    block_intrusive: bool = True
    # Modelo do planejador (decide a cada lance: precisa ser rapido).
    planner_model_id: str | None = None

    @property
    def llm_enabled(self) -> bool:
        return bool(self.bedrock_model_id)


DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-5-5"
DEFAULT_PLANNER_MODEL_ID = "us.anthropic.claude-haiku-5-5"


def _aws_credentials_available() -> bool:
    try:
        import boto3

        return boto3.Session().get_credentials() is not None
    except Exception:  # pragma: no cover
        return False


def load_settings() -> Settings:
    # IA ligada se houver BEDROCK_MODEL_ID ou credenciais da AWS no ambiente.
    # Desligue explicitamente com LLM_ENABLED=false.
    model_id = os.getenv("BEDROCK_MODEL_ID") or None
    disabled = os.getenv("LLM_ENABLED", "").strip().lower() in ("0", "false", "no", "nao")
    if model_id is None and not disabled and _aws_credentials_available():
        model_id = DEFAULT_MODEL_ID
    return Settings(
        database_path=_db_path_from_url(
            os.getenv("DATABASE_URL", "sqlite:///./pentest_chess.db")
        ),
        aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
        bedrock_model_id=None if disabled else model_id,
        planner_model_id=None if disabled or model_id is None
        else (os.getenv("PLANNER_MODEL_ID") or DEFAULT_PLANNER_MODEL_ID),
    )


DEFAULT_CORS = "http://localhost:5173,http://127.0.0.1:5173"


def cors_origins() -> list[str]:
    """Origens da tela autorizadas (HTTP via CORS e WebSocket via checagem manual).

    ``CORS_ORIGINS=*`` libera qualquer origem (retorna ['*']): util quando o
    front e hospedado em um endereco qualquer. Mais aberto, menos seguro."""
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS)
    parts = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return ["*"] if "*" in parts else parts
