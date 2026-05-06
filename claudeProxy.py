from __future__ import annotations

from cc_proxy.config_store import ConfigStore
from cc_proxy.log_bus import LogBus
from cc_proxy.proxy_server import create_app, run_headless


# Compatibility entry for tools that import `claudeProxy:app`.
config_store = ConfigStore()
log_bus = LogBus(echo=True)
app = create_app(config_store, log_bus)


if __name__ == "__main__":
    run_headless(config_store, log_bus)

