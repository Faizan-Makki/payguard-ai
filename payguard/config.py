from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"


def load_project_env(path: str | Path = DOTENV_PATH) -> bool:
    """Load only this PayGuard project's .env; never search parent workspaces."""
    return load_dotenv(dotenv_path=Path(path), override=False)


DOTENV_LOADED = load_project_env()


@dataclass(frozen=True)
class Settings:
    dotenv_loaded: bool = DOTENV_LOADED
    data_source: str = os.getenv("PAYGUARD_DATA_SOURCE", "demo").strip().lower()
    paypal_client_id: str = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    paypal_client_secret: str = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
    paypal_base_url: str = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").strip().rstrip("/")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    db_path: str = os.getenv("PAYGUARD_DB_PATH", "payguard.db")

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id.strip() and self.paypal_client_secret.strip())


settings = Settings()

