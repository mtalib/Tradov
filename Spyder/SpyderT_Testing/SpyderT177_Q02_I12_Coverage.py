#!/usr/bin/env python3
"""Coverage tests for Q02 environment validation and I12 module registry."""

from __future__ import annotations

from types import ModuleType, SimpleNamespace

import pytest

from Spyder.SpyderI_Integration import SpyderI12_ModuleRegistry as i12
from Spyder.SpyderQ_Scripts import SpyderQ02_ValidateEnv as q02


def test_q02_validate_env_file_present_and_missing(monkeypatch, capsys):
    monkeypatch.setattr(q02.Path, "exists", lambda _self: False)
    assert q02.validate_env_file() is False
    assert ".env file not found" in capsys.readouterr().out

    monkeypatch.setattr(q02.Path, "exists", lambda _self: True)
    assert q02.validate_env_file() is True
    assert ".env file found" in capsys.readouterr().out


def test_q02_validate_trading_mode_branches(monkeypatch, capsys):
    monkeypatch.delenv("TRADING_MODE", raising=False)
    errors, warnings = q02.validate_trading_mode()
    assert errors == ["TRADING_MODE not set"]
    assert warnings == []

    monkeypatch.setenv("TRADING_MODE", "paper")
    errors, warnings = q02.validate_trading_mode()
    assert errors == []
    assert warnings == []
    assert "SAFE" in capsys.readouterr().out

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("LIVE_TRADING_CONFIRMED", "false")
    monkeypatch.setenv("REQUIRE_LIVE_CONFIRMATION", "true")
    errors, warnings = q02.validate_trading_mode()
    assert "LIVE mode requires LIVE_TRADING_CONFIRMED=true" in errors

    monkeypatch.setenv("REQUIRE_LIVE_CONFIRMATION", "false")
    errors, warnings = q02.validate_trading_mode()
    assert errors == []
    assert warnings == ["REQUIRE_LIVE_CONFIRMATION=false (unsafe — strongly discouraged)"]


def test_q02_validate_tradier_config_paths(monkeypatch, capsys):
    monkeypatch.delenv("TRADIER_API_KEY", raising=False)
    monkeypatch.delenv("TRADIER_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "weird")
    errors, warnings = q02.validate_tradier_config()
    assert "TRADIER_API_KEY not set" in errors
    assert "TRADIER_ACCOUNT_ID not set" in errors
    assert any("TRADIER_ENVIRONMENT='weird'" in error for error in errors)
    assert warnings == []

    monkeypatch.setenv("TRADIER_API_KEY", "your_tradier_api_key_here")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "acct-1")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "production")
    monkeypatch.setenv("TRADING_MODE", "paper")
    errors, warnings = q02.validate_tradier_config()
    assert "TRADIER_API_KEY is still the placeholder value" in errors
    assert warnings == [
        "TRADIER_ENVIRONMENT=production but TRADING_MODE='paper' — set TRADING_MODE=live or switch to sandbox"
    ]
    assert "LIVE" in capsys.readouterr().out


def test_q02_validate_massive_system_notifications_and_summary(monkeypatch, capsys):
    monkeypatch.setenv("MASSIVE_API_KEY", "massive-key")
    monkeypatch.setenv("MASSIVE_BASE_URL", "https://example.test")
    monkeypatch.setenv("DATA_PROVIDER", "other")
    errors, warnings = q02.validate_massive_config()
    assert errors == []
    assert warnings == ["DATA_PROVIDER='other' — expected 'massive'"]

    monkeypatch.setenv("DEBUG_MODE", "true")
    errors, warnings = q02.validate_system_config()
    assert errors == []
    assert warnings == []

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setenv("EMAIL_ADDRESS", "user@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    errors, warnings = q02.validate_notifications()
    assert errors == []
    assert warnings == []

    assert q02.print_summary([[]], [[]]) is True
    assert q02.print_summary([["bad"]], [["warn"]]) is False
    assert q02.print_summary([[]], [["warn"]]) is True
    output = capsys.readouterr().out
    assert "CONFIGURATION VALID" in output
    assert "CONFIGURATION INVALID" in output
    assert "warning(s) found" in output


def test_q02_main_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(q02, "validate_env_file", lambda: False)
    with pytest.raises(SystemExit) as excinfo:
        q02.main()
    assert excinfo.value.code == 1

    monkeypatch.setattr(q02, "validate_env_file", lambda: True)
    monkeypatch.setattr(q02, "validate_trading_mode", lambda: ([], []))
    monkeypatch.setattr(q02, "validate_tradier_config", lambda: ([], []))
    monkeypatch.setattr(q02, "validate_massive_config", lambda: ([], []))
    monkeypatch.setattr(q02, "validate_system_config", lambda: ([], []))
    monkeypatch.setattr(q02, "validate_notifications", lambda: ([], []))
    monkeypatch.setattr(q02, "print_summary", lambda _errors, _warnings: True)
    with pytest.raises(SystemExit) as excinfo:
        q02.main()
    assert excinfo.value.code == 0
    assert "Next Steps:" in capsys.readouterr().out

    monkeypatch.setattr(q02, "print_summary", lambda _errors, _warnings: False)
    with pytest.raises(SystemExit) as excinfo:
        q02.main()
    assert excinfo.value.code == 1


def test_i12_module_record_import_path_and_availability(monkeypatch):
    record = i12.ModuleRecord(
        module_id="Z99",
        package="SpyderZ_Test",
        filename="SpyderZ99_TestModule",
        primary_class="Thing",
        description="desc",
        series="Z",
    )
    assert record.import_path == "Spyder.SpyderZ_Test.SpyderZ99_TestModule.Thing"

    monkeypatch.setattr(
        i12.importlib,
        "import_module",
        lambda _name: SimpleNamespace(Thing=object),
    )
    assert record.is_available() is True

    monkeypatch.setattr(i12.importlib, "import_module", lambda _name: SimpleNamespace())
    assert record.is_available() is False

    def _boom(_name: str):
        raise RuntimeError("import failed")

    monkeypatch.setattr(i12.importlib, "import_module", _boom)
    assert record.is_available() is False


def test_i12_module_registry_queries_and_runtime_registration(monkeypatch):
    a_record = i12.ModuleRecord("A01", "Pkg", "FileA", "ThingA", "desc", "A", tags=["alpha"])
    b_record = i12.ModuleRecord(
        "B02", "Pkg", "FileB", "ThingB", "desc", "B", status="beta", tags=["beta"]
    )
    registry = i12.ModuleRegistry({"A01": a_record, "B02": b_record})

    assert registry.get("A01") is a_record
    assert registry.get("missing") is None
    assert registry.by_series("a") == [a_record]
    assert registry.by_status("beta") == [b_record]
    assert registry.by_tag("alpha") == [a_record]
    assert registry.all_modules() == [a_record, b_record]
    assert len(registry) == 2
    assert "A01" in registry

    monkeypatch.setattr(i12.ModuleRecord, "is_available", lambda self: self.module_id == "A01")
    assert registry.available_modules() == [a_record]
    assert registry.missing_modules() == [b_record]

    new_record = i12.ModuleRecord("C03", "Pkg", "FileC", "ThingC", "desc", "C")
    registry.register_module(new_record)
    assert registry.get("C03") is new_record
    summary = registry.summary()
    assert summary["total_registered"] == 3
    assert summary["by_series"]["A"] == 1
    assert summary["by_series"]["B"] == 1
    assert summary["by_series"]["C"] == 1
    assert summary["by_status"]["production"] == 2
    assert summary["by_status"]["beta"] == 1


def test_i12_singleton_helpers(monkeypatch):
    monkeypatch.setattr(i12, "_registry_instance", None)
    first = i12.get_module_registry()
    second = i12.get_module_registry()
    assert first is second

    record = i12.ModuleRecord("T01", "Pkg", "FileT", "ThingT", "desc", "T")
    i12.register_module(record)
    assert i12.get_module_registry().get("T01") is record