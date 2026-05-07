from __future__ import annotations

import threading
import traceback
from typing import Any

import requests
from flask import Flask, Response, request
from werkzeug.exceptions import HTTPException
from werkzeug.serving import WSGIRequestHandler, make_server

from .config_store import ConfigStore
from .log_bus import LogBus


class QuietRequestHandler(WSGIRequestHandler):
    """Suppress Werkzeug console access logs; the GUI owns runtime logging."""

    def log(self, type: str, message: str, *args: Any) -> None:  # noqa: A002
        return None


def _clip_text(text: str, max_length: int = 600) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "...[truncated]"


def _error_payload(error_type: str, message: str, **extra: Any) -> dict[str, Any]:
    error: dict[str, Any] = {"type": error_type, "message": message}
    error.update(extra)
    return {"type": "error", "error": error}


def _target_url(config: dict[str, Any]) -> str:
    return config["base_url"].rstrip("/") + "/" + config["messages_path"].lstrip("/")


def _fallback_model(config: dict[str, Any], requested_model: str) -> str:
    mapping = config.get("model_mapping") or {}
    if mapping:
        return next(iter(mapping.values()))
    return requested_model


def _sanitize_payload(data: dict[str, Any]) -> None:
    """Keep the existing user_id cleanup behavior from the original script."""
    metadata = data.get("metadata")
    if isinstance(metadata, dict) and "user_id" in metadata:
        metadata["user_id"] = "default_user"
    if "user_id" in data:
        data["user_id"] = "default_user"


def create_app(config_store: ConfigStore, log_bus: LogBus) -> Flask:
    app = Flask(__name__)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException) -> tuple[dict[str, Any], int]:
        status_code = exc.code or 500
        if status_code == 404:
            error_type = "not_found"
            log_bus.emit(f"请求路径不存在：{request.method} {request.path}", "WARN")
        else:
            error_type = "http_error"
            log_bus.emit(f"HTTP 错误：{status_code} {request.method} {request.path} - {exc.description}", "WARN")
        return (
            _error_payload(
                error_type,
                str(exc.description),
                status_code=status_code,
                method=request.method,
                path=request.path,
            ),
            status_code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception) -> tuple[dict[str, Any], int]:
        log_bus.emit(f"未处理异常：{exc}", "ERROR")
        log_bus.emit(_clip_text(traceback.format_exc()), "ERROR")
        return _error_payload("internal_error", str(exc)), 500

    @app.get("/")
    def index() -> tuple[dict[str, Any], int]:
        config = config_store.get()
        return {
            "ok": True,
            "service": "cc-deepseek-proxy",
            "provider": config.get("provider_name"),
            "listen": f"http://{config.get('host')}:{config.get('port')}",
        }, 200

    @app.get("/health")
    def health() -> tuple[dict[str, Any], int]:
        return {"ok": True, "service": "cc-deepseek-proxy"}, 200

    @app.get("/v1/models")
    def models() -> tuple[dict[str, Any], int]:
        config = config_store.get()
        model_ids = list((config.get("model_mapping") or {}).keys())
        if not model_ids:
            model_ids = list((config.get("model_mapping") or {}).values())
        return {
            "object": "list",
            "data": [
                {
                    "id": model_id,
                    "object": "model",
                    "created": 0,
                    "owned_by": "cc-deepseek-proxy",
                }
                for model_id in model_ids
            ],
        }, 200

    @app.post("/v1/messages/count_tokens")
    def count_tokens() -> tuple[dict[str, int], int]:
        # Claude Code only needs a valid-looking response here; the original
        # script also returned a fixed fake count to avoid plugin-side 404s.
        return {"input_tokens": 10}, 200

    @app.post("/v1/messages")
    def proxy() -> Response | tuple[dict[str, str], int] | tuple[str, int]:
        try:
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return _error_payload("invalid_request_error", "No JSON data received"), 400

            config = config_store.runtime_snapshot()
            api_key = config.get("api_key", "")
            if not api_key:
                log_bus.emit("请求被拒绝：config.json 中未配置 api_key", "ERROR")
                return _error_payload("authentication_error", "Missing api_key in config.json"), 400

            _sanitize_payload(data)
            requested_model = str(data.get("model") or "claude-4.6-opus")
            model_mapping = config.get("model_mapping") or {}
            target_model = model_mapping.get(requested_model, _fallback_model(config, requested_model))
            data["model"] = target_model

            provider = config.get("provider_name") or "provider"
            target = _target_url(config)
            log_bus.emit(f"路由匹配：{requested_model} -> {target_model}，转发到 {provider}")

            headers = {
                "x-api-key": api_key,
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }
            if config.get("anthropic_version"):
                headers["anthropic-version"] = str(config["anthropic_version"])

            try:
                response = requests.post(
                    target,
                    json=data,
                    headers=headers,
                    stream=True,
                    timeout=(10, int(config.get("request_timeout_seconds", 120))),
                )
            except requests.Timeout as exc:
                log_bus.emit(f"{provider} 请求超时：{exc}", "ERROR")
                return _error_payload("timeout_error", f"{provider} request timed out"), 504
            except requests.RequestException as exc:
                log_bus.emit(f"{provider} 请求失败：{exc}", "ERROR")
                return _error_payload("bad_gateway", f"{provider} request failed: {exc}"), 502

            if response.status_code != 200:
                body = _clip_text(response.text)
                log_bus.emit(f"{provider} 返回错误：{response.status_code} - {body}", "ERROR")
                return (
                    _error_payload(
                        "provider_error",
                        f"{provider} returned HTTP {response.status_code}",
                        provider=provider,
                        provider_status=response.status_code,
                        provider_body=body,
                    ),
                    response.status_code,
                )

            def generate():
                try:
                    for chunk in response.iter_content(chunk_size=None):
                        if chunk:
                            yield chunk
                except Exception as exc:  # pragma: no cover - network stream edge
                    log_bus.emit(f"流传输中断：{exc}", "ERROR")
                finally:
                    response.close()

            content_type = response.headers.get("Content-Type", "application/json")
            return Response(generate(), content_type=content_type)

        except Exception as exc:
            log_bus.emit(f"代理内部错误：{exc}", "ERROR")
            log_bus.emit(_clip_text(traceback.format_exc()), "ERROR")
            return _error_payload("internal_error", str(exc)), 500

    return app


class ProxyServer:
    """Start and stop the Flask app from a background thread."""

    def __init__(self, config_store: ConfigStore, log_bus: LogBus) -> None:
        self.config_store = config_store
        self.log_bus = log_bus
        self._server = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self.bound_host: str | None = None
        self.bound_port: int | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.running:
                self.log_bus.emit("代理已经在运行")
                return

            config = self.config_store.get()
            host = str(config["host"])
            port = int(config["port"])
            app = create_app(self.config_store, self.log_bus)

            try:
                self._server = make_server(
                    host,
                    port,
                    app,
                    threaded=True,
                    request_handler=QuietRequestHandler,
                )
            except OSError as exc:
                self.log_bus.emit(f"启动失败：{host}:{port} 无法监听，{exc}", "ERROR")
                raise

            self.bound_host = host
            self.bound_port = port
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self.log_bus.emit(f"代理已启动：http://{host}:{port}")

    def stop(self) -> None:
        with self._lock:
            if not self._server:
                return
            self.log_bus.emit("正在停止代理...")
            self._server.shutdown()
            self._server.server_close()
            if self._thread:
                self._thread.join(timeout=3)
            self._server = None
            self._thread = None
            self.bound_host = None
            self.bound_port = None
            self.log_bus.emit("代理已停止")


def run_headless(config_store: ConfigStore, log_bus: LogBus) -> None:
    server = ProxyServer(config_store, log_bus)
    server.start()
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        server.stop()
