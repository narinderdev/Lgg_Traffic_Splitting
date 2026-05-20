from __future__ import annotations

import pytest

from app.core.config import Settings


def test_cors_origin_list_supports_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    settings = Settings(_env_file=None)

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_production_rejects_default_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("INGEST_API_KEY", raising=False)

    with pytest.raises(ValueError):
        Settings(_env_file=None)
