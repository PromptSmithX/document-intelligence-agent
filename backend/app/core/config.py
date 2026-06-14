from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "Document Intelligence Agent API"
    debug: bool = False
    storage_dir: Path = PROJECT_ROOT / "storage"


settings = Settings()
