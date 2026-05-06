from __future__ import annotations

import argparse

from cc_proxy.config_store import ConfigStore
from cc_proxy.gui import run_gui
from cc_proxy.log_bus import LogBus
from cc_proxy.proxy_server import run_headless


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude Code to provider proxy")
    parser.add_argument("--config", help="config.json path; defaults to exe/current directory")
    parser.add_argument("--headless", action="store_true", help="run without GUI")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_store = ConfigStore(args.config)
    log_bus = LogBus(echo=args.headless)
    if args.headless:
        run_headless(config_store, log_bus)
    else:
        run_gui(config_store, log_bus)


if __name__ == "__main__":
    main()

