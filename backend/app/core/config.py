from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Document Intelligence Agent API"
    debug: bool = False
    storage_dir: Path = Path(__file__).resolve().parents[3] / "storage"


settings = Settings()
