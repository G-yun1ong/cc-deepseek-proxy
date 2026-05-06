from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from .config_store import ConfigStore
from .log_bus import LogBus
from .proxy_server import ProxyServer


class ProxyGui:
    """Tkinter control window for the local proxy."""

    def __init__(self, root: tk.Tk, config_store: ConfigStore, log_bus: LogBus) -> None:
        self.root = root
        self.config_store = config_store
        self.log_bus = log_bus
        self.server = ProxyServer(config_store, log_bus)
        self.vars: dict[str, tk.StringVar] = {}
        self._loading = False
        self._save_after_id: str | None = None

        self.root.title("CC DeepSeek Proxy")
        self.root.minsize(920, 720)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._load_config_to_ui()
        self._poll_logs()
        self._refresh_status()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self._build_config_frame(main)
        self._build_mapping_frame(main)
        self._build_log_frame(main)

    def _build_config_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="代理配置", padding=10)
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        fields = [
            ("host", "监听地址", 0, 0),
            ("port", "端口", 0, 2),
            ("provider_name", "服务商", 1, 0),
            ("base_url", "Base URL", 1, 2),
            ("messages_path", "转发接口", 2, 0),
            ("anthropic_version", "Anthropic Version", 2, 2),
            ("api_key", "API Key", 3, 0),
        ]

        for key, label, row, col in fields:
            ttk.Label(frame, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=4)
            var = tk.StringVar()
            self.vars[key] = var
            show = "*" if key == "api_key" else ""
            entry = ttk.Entry(frame, textvariable=var, show=show)
            entry.grid(row=row, column=col + 1, sticky="ew", padx=(0, 12), pady=4)
            entry.bind("<FocusOut>", lambda _event: self._save_config_from_ui())
            entry.bind("<Return>", lambda _event: self._save_config_from_ui())
            var.trace_add("write", lambda *_args: self._schedule_save())
            if key == "api_key":
                self.api_key_entry = entry

        self.show_key_var = tk.BooleanVar(value=False)
        show_key = ttk.Checkbutton(
            frame,
            text="显示 API Key",
            variable=self.show_key_var,
            command=self._toggle_api_key,
        )
        show_key.grid(row=3, column=2, sticky="w", pady=4)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        button_frame.columnconfigure(4, weight=1)

        ttk.Button(button_frame, text="保存配置", command=self._save_config_from_ui).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(button_frame, text="启动代理", command=self._start_proxy).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(button_frame, text="停止代理", command=self._stop_proxy).grid(row=0, column=2, padx=(0, 8))

        self.status_var = tk.StringVar(value="未启动")
        ttk.Label(button_frame, textvariable=self.status_var).grid(row=0, column=4, sticky="e")

    def _build_mapping_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="模型映射", padding=10)
        frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        frame.columnconfigure(0, weight=1)

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=0, column=0, columnspan=5, sticky="ew")
        table_frame.columnconfigure(0, weight=1)

        self.mapping_tree = ttk.Treeview(
            table_frame,
            columns=("source", "target"),
            show="headings",
            height=6,
            selectmode="browse",
        )
        self.mapping_tree.heading("source", text="Claude Code 请求模型")
        self.mapping_tree.heading("target", text="转发目标模型")
        self.mapping_tree.column("source", width=320, anchor="w")
        self.mapping_tree.column("target", width=320, anchor="w")
        self.mapping_tree.grid(row=0, column=0, sticky="ew")
        self.mapping_tree.bind("<<TreeviewSelect>>", self._on_mapping_select)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.mapping_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.mapping_tree.configure(yscrollcommand=scrollbar.set)

        self.source_model_var = tk.StringVar()
        self.target_model_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.source_model_var).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.target_model_var).grid(row=1, column=1, sticky="ew", pady=(8, 0), padx=8)
        ttk.Button(frame, text="新增/更新", command=self._upsert_mapping).grid(row=1, column=2, pady=(8, 0))
        ttk.Button(frame, text="删除选中", command=self._delete_mapping).grid(row=1, column=3, pady=(8, 0), padx=8)
        ttk.Button(frame, text="清空输入", command=self._clear_mapping_inputs).grid(row=1, column=4, pady=(8, 0))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _build_log_frame(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="运行日志", padding=10)
        frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(frame, height=14, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        ttk.Button(frame, text="清空窗口日志", command=self._clear_logs).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _load_config_to_ui(self) -> None:
        self._loading = True
        config = self.config_store.get()
        for key, var in self.vars.items():
            var.set(str(config.get(key, "")))
        self._reload_mapping_table(config.get("model_mapping", {}))
        self._loading = False

    def _reload_mapping_table(self, mapping: dict[str, str]) -> None:
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        for source, target in mapping.items():
            self.mapping_tree.insert("", "end", values=(source, target))

    def _schedule_save(self) -> None:
        if self._loading:
            return
        if self._save_after_id:
            self.root.after_cancel(self._save_after_id)
        # Debounce text edits so config.json updates quickly without excessive IO.
        self._save_after_id = self.root.after(600, self._save_config_from_ui)

    def _save_config_from_ui(self) -> bool:
        if self._loading:
            return False
        if self._save_after_id:
            try:
                self.root.after_cancel(self._save_after_id)
            except tk.TclError:
                pass
            self._save_after_id = None
        try:
            port = int(self.vars["port"].get().strip())
            if port < 1 or port > 65535:
                raise ValueError
        except ValueError:
            self.status_var.set("端口无效，配置未保存")
            return False

        changes: dict[str, Any] = {key: var.get().strip() for key, var in self.vars.items()}
        changes["port"] = port
        self.config_store.update(changes)
        self.status_var.set(self._status_text("配置已保存"))
        return True

    def _current_mapping(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for item_id in self.mapping_tree.get_children():
            source, target = self.mapping_tree.item(item_id, "values")
            mapping[str(source)] = str(target)
        return mapping

    def _save_mapping(self) -> None:
        self.config_store.replace_model_mapping(self._current_mapping())
        self.status_var.set(self._status_text("模型映射已保存"))

    def _upsert_mapping(self) -> None:
        source = self.source_model_var.get().strip()
        target = self.target_model_var.get().strip()
        if not source or not target:
            messagebox.showwarning("模型映射", "请求模型和目标模型都不能为空。")
            return

        for item_id in self.mapping_tree.get_children():
            values = self.mapping_tree.item(item_id, "values")
            if values and values[0] == source:
                self.mapping_tree.item(item_id, values=(source, target))
                self._save_mapping()
                return

        self.mapping_tree.insert("", "end", values=(source, target))
        self._save_mapping()

    def _delete_mapping(self) -> None:
        selected = self.mapping_tree.selection()
        if not selected:
            return
        for item_id in selected:
            self.mapping_tree.delete(item_id)
        self._save_mapping()
        self._clear_mapping_inputs()

    def _on_mapping_select(self, _event: tk.Event) -> None:
        selected = self.mapping_tree.selection()
        if not selected:
            return
        source, target = self.mapping_tree.item(selected[0], "values")
        self.source_model_var.set(str(source))
        self.target_model_var.set(str(target))

    def _clear_mapping_inputs(self) -> None:
        self.source_model_var.set("")
        self.target_model_var.set("")

    def _toggle_api_key(self) -> None:
        self.api_key_entry.configure(show="" if self.show_key_var.get() else "*")

    def _start_proxy(self) -> None:
        if not self._save_config_from_ui():
            return
        try:
            self.server.start()
        except OSError:
            messagebox.showerror("启动失败", "端口可能已被占用，请换一个端口后重试。")
        self._refresh_status()

    def _stop_proxy(self) -> None:
        self.server.stop()
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.status_var.set(self._status_text())

    def _status_text(self, prefix: str | None = None) -> str:
        if self.server.running:
            base = f"运行中：http://{self.server.bound_host}:{self.server.bound_port}"
        else:
            base = "未启动"
        return f"{prefix}；{base}" if prefix else base

    def _poll_logs(self) -> None:
        for line in self.log_bus.drain():
            self._append_log(line)
        self.root.after(200, self._poll_logs)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        current_lines = int(self.log_text.index("end-1c").split(".")[0])
        if current_lines > 1000:
            self.log_text.delete("1.0", f"{current_lines - 1000}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        self.server.stop()
        self.root.destroy()


def run_gui(config_store: ConfigStore, log_bus: LogBus) -> None:
    root = tk.Tk()
    ProxyGui(root, config_store, log_bus)
    root.mainloop()
