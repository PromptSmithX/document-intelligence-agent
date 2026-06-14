from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Document Intelligence Agent API"
    debug: bool = False


settings = Settings()
