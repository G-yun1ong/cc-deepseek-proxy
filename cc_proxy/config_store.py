from __future__ import annotations

import copy
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any


CONFIG_FILENAME = "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "host": "127.0.0.1",
    "port": 8085,
    "provider_name": "DeepSeek",
    "base_url": "https://api.deepseek.com",
    "messages_path": "/anthropic/v1/messages",
    "api_key": "",
    "anthropic_version": "2023-06-01",
    "request_timeout_seconds": 120,
    "model_mapping": {
        "claude-4.6-opus": "deepseek-v4-pro",
        "claude-4.6-sonnet": "deepseek-v4-flash",
    },
}


def app_dir() -> Path:
    """Return the directory that should hold config files.

    In a PyInstaller build this is the exe folder. During development it is the
    current working directory, which keeps the app portable and easy to inspect.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_config_path() -> Path:
    return app_dir() / CONFIG_FILENAME


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge user config with defaults and coerce basic field types."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key == "model_mapping" and isinstance(value, dict):
                config[key] = {str(k): str(v) for k, v in value.items()}
            else:
                config[key] = value

    config["host"] = str(config.get("host") or DEFAULT_CONFIG["host"]).strip()
    config["provider_name"] = str(config.get("provider_name") or "").strip()
    config["base_url"] = str(config.get("base_url") or "").strip().rstrip("/")
    config["messages_path"] = "/" + str(config.get("messages_path") or "").strip().lstrip("/")
    config["api_key"] = str(config.get("api_key") or "").strip()
    config["anthropic_version"] = str(config.get("anthropic_version") or "").strip()

    try:
        config["port"] = int(config.get("port", DEFAULT_CONFIG["port"]))
    except (TypeError, ValueError):
        config["port"] = DEFAULT_CONFIG["port"]

    try:
        config["request_timeout_seconds"] = int(config.get("request_timeout_seconds", 120))
    except (TypeError, ValueError):
        config["request_timeout_seconds"] = 120

    if not isinstance(config.get("model_mapping"), dict):
        config["model_mapping"] = copy.deepcopy(DEFAULT_CONFIG["model_mapping"])

    return config


class ConfigStore:
    """Thread-safe JSON config store used by the GUI and proxy routes."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).resolve() if path else default_config_path()
        self._lock = threading.RLock()
        self._config = self._load_or_create()

    def get(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def runtime_snapshot(self) -> dict[str, Any]:
        """Return config for request handling.

        If the config file leaves api_key empty, an environment variable can be
        used without writing that secret back to disk.
        """
        config = self.get()
        if not config.get("api_key"):
            config["api_key"] = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        return config

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            merged = copy.deepcopy(self._config)
            merged.update(changes)
            self._config = normalize_config(merged)
            self._save_locked()
            return copy.deepcopy(self._config)

    def replace_model_mapping(self, mapping: dict[str, str]) -> dict[str, Any]:
        return self.update({"model_mapping": mapping})

    def _load_or_create(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            config = normalize_config(DEFAULT_CONFIG)
            self._write_json(config)
            return config

        try:
            with self.path.open("r", encoding="utf-8") as file:
                return normalize_config(json.load(file))
        except (OSError, json.JSONDecodeError):
            backup_path = self.path.with_suffix(self.path.suffix + ".broken")
            try:
                self.path.replace(backup_path)
            except OSError:
                pass
            config = normalize_config(DEFAULT_CONFIG)
            self._write_json(config)
            return config

    def _save_locked(self) -> None:
        self._write_json(self._config)

    def _write_json(self, config: dict[str, Any]) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(tmp_path, self.path)

