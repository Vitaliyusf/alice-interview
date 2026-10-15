"""Settings come from .env and the environment, are validated once, and are typed everywhere else."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

ENV_FILE = (
    Path(__file__).resolve().parent.parent / ".env"
)  # next to requirements.txt, whatever the working directory


class Settings(BaseSettings):
    """Typed settings; the OpenAI key is required, everything else has a default."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8-sig",  # also reads a file that Notepad saved with a BOM
        env_ignore_empty=True,  # an empty OPENAI_API_KEY= line counts as "not set"
        extra="ignore",
    )

    openai_api_key: SecretStr = Field(min_length=1)  # SecretStr: never shown in logs, repr or error pages
    openai_model: str = "gpt-6-luna"
    openai_timeout_s: float = Field(default=30.0, gt=0)
    openai_max_retries: int = Field(default=2, ge=0)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # .env before the machine's environment: the key pasted for this project wins over an old one
        return init_settings, dotenv_settings, env_settings, file_secret_settings


@lru_cache
def get_settings() -> Settings:
    """The settings, read once per process."""
    return Settings()  # type: ignore[call-arg]  # the values come from .env and the environment
