import pytest
from pydantic import ValidationError

from app.config import Settings


def test_env_file_wins_over_the_machine_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "old-key-from-the-machine")
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=key-from-dotenv\nOPENAI_MODEL=m1\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]
    assert settings.openai_api_key.get_secret_value() == "key-from-dotenv"
    assert settings.openai_model == "m1"


def test_empty_line_in_env_file_does_not_hide_a_real_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "key-from-the-machine")
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
    assert Settings(_env_file=env_file).openai_api_key.get_secret_value() == "key-from-the-machine"  # type: ignore[call-arg]


def test_missing_key_is_an_error_and_the_key_is_never_printed(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
    settings = Settings(openai_api_key="sk-very-secret", _env_file=None)  # type: ignore[call-arg]
    assert "sk-very-secret" not in repr(settings) and "sk-very-secret" not in str(settings.model_dump())


def test_env_file_saved_by_notepad_with_a_bom_is_read(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=key-after-bom\n", encoding="utf-8-sig")
    assert Settings(_env_file=env_file).openai_api_key.get_secret_value() == "key-after-bom"  # type: ignore[call-arg]


def test_bad_values_are_rejected_at_startup(monkeypatch) -> None:
    with pytest.raises(ValidationError):
        Settings(openai_api_key="k", log_level="LOUD", _env_file=None)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Settings(openai_api_key="k", openai_timeout_s=0, _env_file=None)  # type: ignore[call-arg]
