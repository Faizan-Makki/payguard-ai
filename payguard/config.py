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
    paypal_return_url: str = os.getenv("PAYPAL_RETURN_URL", "http://localhost:8501/").strip()
    paypal_cancel_url: str = os.getenv("PAYPAL_CANCEL_URL", "http://localhost:8501/").strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    db_path: str = os.getenv("PAYGUARD_DB_PATH", "payguard.db")

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id.strip() and self.paypal_client_secret.strip())


settings = Settings()

