from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
from typing import Any

from .config_store import ConfigStore
from .log_bus import LogBus
from .proxy_server import ProxyServer


# Claude-inspired warm palette. English text keeps Poppins/Lora when installed;
# Chinese UI text prefers Microsoft YaHei or the system default.
PALETTE = {
    "dark": "#141413",
    "light": "#FAF9F5",
    "pampas": "#F4F3EE",
    "orange": "#D97757",
    "crail": "#C15F3C",
    "green": "#788C5D",
    "mid_gray": "#B0AEA5",
    "cloudy": "#B1ADA1",
    "light_gray": "#E8E6DC",
}

TITLE_FONT = "Poppins"
BODY_FONT = "Lora"
CJK_FONT = "Microsoft YaHei"
FALLBACK_TITLE_FONT = "Segoe UI"
FALLBACK_BODY_FONT = "Georgia"
FALLBACK_CJK_FONT = "TkDefaultFont"


def _pick_font(preferred: str, fallback: str) -> str:
    families = set(tkfont.families())
    if preferred in families:
        return preferred
    if fallback in families:
        return fallback
    return "TkDefaultFont"


def _pick_cjk_font() -> str:
    families = set(tkfont.families())
    for family in (
        "Microsoft YaHei",
        "\u5fae\u8f6f\u96c5\u9ed1",
        "Microsoft YaHei UI",
        "Segoe UI",
    ):
        if family in families:
            return family
    return FALLBACK_CJK_FONT


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _ui_font(text: str, size: int = 10, weight: str = "normal", title: bool = False) -> tuple[str, int, str]:
    if _contains_cjk(text):
        return (CJK_FONT, size, weight)
    return (TITLE_FONT if title else BODY_FONT, size, weight)


def _round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> None:
    """Draw a rounded rectangle with a smoothed polygon."""
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    canvas.create_polygon(points, smooth=True, splinesteps=16, **kwargs)


class RoundedPanel(tk.Frame):
    """Lightweight rounded section container."""

    def __init__(self, parent: tk.Misc, title: str, radius: int = 18) -> None:
        super().__init__(parent, bg=PALETTE["light"], highlightthickness=0)
        self.radius = radius
        self._last_draw_size: tuple[int, int] | None = None
        self.canvas = tk.Canvas(self, bg=PALETTE["light"], highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.body = tk.Frame(self, bg=PALETTE["pampas"], highlightthickness=0)
        self.body.grid(row=0, column=0, sticky="nsew", padx=18, pady=16)

        self.title_label = tk.Label(
            self.body,
            text=title,
            bg=PALETTE["pampas"],
            fg=PALETTE["dark"],
            font=_ui_font(title, 12, "bold", title=True),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.content = tk.Frame(self.body, bg=PALETTE["pampas"], highlightthickness=0)
        self.content.grid(row=1, column=0, sticky="nsew")

        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas.tk.call("lower", self.canvas._w)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event: tk.Event | None = None) -> None:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        size = (width, height)
        if size == self._last_draw_size:
            return
        self._last_draw_size = size
        self.canvas.delete("all")
        _round_rect(
            self.canvas,
            2,
            2,
            width - 3,
            height - 3,
            self.radius,
            fill=PALETTE["pampas"],
            outline=PALETTE["light_gray"],
            width=1,
        )
        self.canvas.create_line(8, 18, 8, height - 18, fill=PALETTE["orange"], width=5, capstyle=tk.ROUND)


class RoundedEntry(tk.Frame):
    """Rounded input shell with a native Entry inside."""

    def __init__(self, parent: tk.Misc, textvariable: tk.StringVar, show: str = "") -> None:
        super().__init__(parent, bg=PALETTE["pampas"], height=36, highlightthickness=0)
        self.radius = 12
        self._focused = False
        self._last_draw_state: tuple[int, int, bool] | None = None
        self.canvas = tk.Canvas(self, bg=PALETTE["pampas"], highlightthickness=0, bd=0, height=36)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
            show=show,
            bg=PALETTE["light"],
            fg=PALETTE["dark"],
            insertbackground=PALETTE["dark"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(BODY_FONT, 10),
        )
        self.entry.place(x=13, y=7, relwidth=1, width=-26, height=22)
        self.grid_propagate(False)
        self.bind("<Configure>", self._redraw)
        self.entry.bind("<FocusIn>", self._on_focus_in, add="+")
        self.entry.bind("<FocusOut>", self._on_focus_out, add="+")

    def set_show(self, show: str) -> None:
        self.entry.configure(show=show)

    def _on_focus_in(self, _event: tk.Event) -> None:
        self._focused = True
        self._redraw()

    def _on_focus_out(self, _event: tk.Event) -> None:
        self._focused = False
        self._redraw()

    def _redraw(self, _event: tk.Event | None = None) -> None:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 36)
        state = (width, height, self._focused)
        if state == self._last_draw_state:
            return
        self._last_draw_state = state
        self.canvas.delete("all")
        border_width = 2 if self._focused else 1
        _round_rect(
            self.canvas,
            1,
            1,
            width - 2,
            height - 2,
            self.radius,
            fill=PALETTE["light"],
            outline=PALETTE["orange"] if self._focused else PALETTE["mid_gray"],
            width=border_width,
        )


class RoundedButton(tk.Canvas):
    """Canvas button with rounded border and no image assets."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Any,
        width: int = 104,
        primary: bool = False,
        surface: str | None = None,
    ) -> None:
        self.surface = surface or PALETTE["pampas"]
        super().__init__(
            parent,
            width=width,
            height=36,
            bg=self.surface,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.primary = primary
        self._hover = False
        self._last_draw_state: tuple[int, int, bool, bool, str] | None = None
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Configure>", lambda _event: self._redraw())
        self._redraw()

    def _colors(self) -> tuple[str, str, str]:
        if self.primary or self._hover:
            return PALETTE["orange"], PALETTE["orange"], PALETTE["light"]
        return self.surface, PALETTE["mid_gray"], PALETTE["dark"]

    def _redraw(self) -> None:
        width = max(int(self["width"]), self.winfo_width(), 1)
        height = max(int(self["height"]), self.winfo_height(), 1)
        state = (width, height, self._hover, self.primary, self.text)
        if state == self._last_draw_state:
            return
        self._last_draw_state = state
        self.delete("all")
        fill, outline, text_color = self._colors()
        _round_rect(self, 1, 1, width - 2, height - 2, 14, fill=fill, outline=outline, width=1)
        self.create_text(
            width // 2,
            height // 2,
            text=self.text,
            fill=text_color,
            font=_ui_font(self.text, 10, "bold" if self.primary else "normal", title=True),
        )

    def _click(self, _event: tk.Event) -> None:
        if self.command:
            self.command()

    def _enter(self, _event: tk.Event) -> None:
        self._hover = True
        self._redraw()

    def _leave(self, _event: tk.Event) -> None:
        self._hover = False
        self._redraw()


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
        self._resize_after_id: str | None = None
        self._pending_resize_size: tuple[int, int] | None = None
        self._last_root_size: tuple[int, int] | None = None
        self._last_column_widths: tuple[int, int] | None = None
        self.status_var = tk.StringVar(value="未启动")

        self.root.title("CC DeepSeek Proxy")
        self.root.minsize(980, 660)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._configure_style()
        self._build_ui()
        self._load_config_to_ui()
        self._poll_logs()
        self._refresh_status()
        self.root.bind("<Configure>", self._on_resize)

    def _configure_style(self) -> None:
        self.root.configure(bg=PALETTE["light"])
        global TITLE_FONT, BODY_FONT, CJK_FONT
        TITLE_FONT = _pick_font(TITLE_FONT, FALLBACK_TITLE_FONT)
        BODY_FONT = _pick_font(BODY_FONT, FALLBACK_BODY_FONT)
        CJK_FONT = _pick_cjk_font()
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=(BODY_FONT, 10))
        style.configure("App.TFrame", background=PALETTE["light"])
        style.configure("Card.TFrame", background=PALETTE["pampas"])
        style.configure("Status.TLabel", background=PALETTE["pampas"], foreground=PALETTE["crail"], font=(CJK_FONT, 10))
        style.configure("TCheckbutton", background=PALETTE["pampas"], foreground=PALETTE["dark"], font=(CJK_FONT, 10))
        style.map("TCheckbutton", background=[("active", PALETTE["pampas"])])
        style.configure(
            "Treeview",
            background=PALETTE["light"],
            fieldbackground=PALETTE["light"],
            foreground=PALETTE["dark"],
            rowheight=26,
            bordercolor=PALETTE["light_gray"],
            lightcolor=PALETTE["light_gray"],
            darkcolor=PALETTE["light_gray"],
            font=(BODY_FONT, 10),
        )
        style.configure(
            "Treeview.Heading",
            background=PALETTE["pampas"],
            foreground=PALETTE["dark"],
            font=(CJK_FONT, 10, "bold"),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", PALETTE["orange"])],
            foreground=[("selected", PALETTE["light"])],
        )
        style.configure(
            "Sage.Vertical.TScrollbar",
            gripcount=0,
            width=12,
            arrowsize=11,
            background=PALETTE["orange"],
            troughcolor=PALETTE["pampas"],
            bordercolor=PALETTE["pampas"],
            darkcolor=PALETTE["orange"],
            lightcolor=PALETTE["orange"],
            arrowcolor=PALETTE["dark"],
            relief="flat",
        )
        style.map(
            "Sage.Vertical.TScrollbar",
            background=[("active", PALETTE["crail"]), ("pressed", PALETTE["crail"])],
        )

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=16, style="App.TFrame")
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_header(main)

        content = ttk.Frame(main, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=5)
        content.columnconfigure(1, weight=7)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content, style="App.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        right = ttk.Frame(content, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self._build_config_frame(left, row=0)
        self._build_mapping_frame(left, row=1)
        self._build_log_frame(right, row=0)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = tk.Frame(parent, bg=PALETTE["light"], highlightthickness=0)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)
        tk.Label(
            header,
            text="CC DeepSeek Proxy",
            bg=PALETTE["light"],
            fg=PALETTE["dark"],
            font=(TITLE_FONT, 18, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text="本地兼容代理",
            bg=PALETTE["light"],
            fg=PALETTE["cloudy"],
            font=_ui_font("本地兼容代理", 10),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions = tk.Frame(header, bg=PALETTE["light"], highlightthickness=0)
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        for column in range(3):
            actions.columnconfigure(column, weight=0)

        tk.Label(
            actions,
            textvariable=self.status_var,
            bg=PALETTE["light"],
            fg=PALETTE["crail"],
            font=_ui_font("未启动", 10, "bold"),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=(0, 12))
        RoundedButton(actions, "启动", self._start_proxy, width=78, primary=True, surface=PALETTE["light"]).grid(
            row=0, column=1, padx=(0, 8)
        )
        RoundedButton(actions, "停止", self._stop_proxy, width=78, surface=PALETTE["light"]).grid(row=0, column=2)

    def _add_vertical_entry(
        self,
        parent: tk.Misc,
        key: str,
        label: str,
        row: int,
        col: int = 0,
        show: str = "",
        columnspan: int = 1,
    ) -> RoundedEntry:
        padx = (0, 10) if col == 0 and columnspan == 1 else (0, 0)
        tk.Label(
            parent,
            text=label,
            bg=PALETTE["pampas"],
            fg=PALETTE["cloudy"],
            font=_ui_font(label, 10),
            anchor="w",
        ).grid(row=row, column=col, columnspan=columnspan, sticky="ew", padx=padx, pady=(0, 4))
        var = tk.StringVar()
        self.vars[key] = var
        entry = RoundedEntry(parent, var, show=show)
        entry.grid(row=row + 1, column=col, columnspan=columnspan, sticky="ew", padx=padx, pady=(0, 10))
        entry.entry.bind("<FocusOut>", lambda _event: self._save_config_from_ui())
        entry.entry.bind("<Return>", lambda _event: self._save_config_from_ui())
        var.trace_add("write", lambda *_args: self._schedule_save())
        return entry

    def _build_config_frame(self, parent: ttk.Frame, row: int) -> None:
        panel = RoundedPanel(parent, "代理配置")
        panel.grid(row=row, column=0, sticky="ew")
        frame = panel.content
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        fields = [
            ("host", "监听地址", 0, 0, 1, ""),
            ("port", "端口", 0, 1, 1, ""),
            ("provider_name", "服务商", 2, 0, 1, ""),
            ("anthropic_version", "Anthropic Version", 2, 1, 1, ""),
            ("base_url", "Base URL", 4, 0, 2, ""),
            ("messages_path", "转发接口", 6, 0, 2, ""),
            ("api_key", "API Key", 8, 0, 2, "*"),
        ]

        for key, label, field_row, field_col, columnspan, show in fields:
            entry = self._add_vertical_entry(frame, key, label, field_row, field_col, show, columnspan)
            if key == "api_key":
                self.api_key_entry = entry

        config_actions = tk.Frame(frame, bg=PALETTE["pampas"], highlightthickness=0)
        config_actions.grid(row=10, column=0, columnspan=2, sticky="ew")
        config_actions.columnconfigure(0, weight=1)
        config_actions.columnconfigure(1, weight=0)
        self.show_key_var = tk.BooleanVar(value=False)
        show_key = ttk.Checkbutton(
            config_actions,
            text="显示 API Key",
            variable=self.show_key_var,
            command=self._toggle_api_key,
        )
        show_key.grid(row=0, column=0, sticky="w")
        RoundedButton(config_actions, "保存配置", self._save_config_from_ui, width=104, primary=True).grid(
            row=0, column=1, sticky="e"
        )

    def _build_mapping_frame(self, parent: ttk.Frame, row: int) -> None:
        panel = RoundedPanel(parent, "模型映射")
        panel.grid(row=row, column=0, sticky="nsew", pady=(12, 0))
        frame = panel.content
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1, minsize=154)

        table_frame = tk.Frame(frame, bg=PALETTE["pampas"], highlightthickness=0)
        table_frame.grid(row=0, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1, minsize=142)

        self.mapping_tree = ttk.Treeview(
            table_frame,
            columns=("source", "target"),
            show="headings",
            height=5,
            selectmode="browse",
        )
        self.mapping_tree.heading("source", text="请求模型")
        self.mapping_tree.heading("target", text="目标模型")
        self.mapping_tree.column("source", width=320, anchor="w")
        self.mapping_tree.column("target", width=320, anchor="w")
        self.mapping_tree.grid(row=0, column=0, sticky="nsew")
        self.mapping_tree.bind("<<TreeviewSelect>>", self._on_mapping_select)

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.mapping_tree.yview,
            style="Sage.Vertical.TScrollbar",
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.mapping_tree.configure(yscrollcommand=scrollbar.set)

        self.source_model_var = tk.StringVar()
        self.target_model_var = tk.StringVar()
        inputs = tk.Frame(frame, bg=PALETTE["pampas"], highlightthickness=0)
        inputs.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        inputs.columnconfigure(0, weight=1, uniform="mapping_inputs")
        inputs.columnconfigure(1, weight=1, uniform="mapping_inputs")
        tk.Label(
            inputs,
            text="请求模型",
            bg=PALETTE["pampas"],
            fg=PALETTE["cloudy"],
            font=_ui_font("请求模型", 10),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 4))
        tk.Label(
            inputs,
            text="转发目标模型",
            bg=PALETTE["pampas"],
            fg=PALETTE["cloudy"],
            font=_ui_font("转发目标模型", 10),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))
        RoundedEntry(inputs, self.source_model_var).grid(row=1, column=0, sticky="ew", padx=(0, 8))
        RoundedEntry(inputs, self.target_model_var).grid(row=1, column=1, sticky="ew", padx=(8, 0))

        mapping_buttons = tk.Frame(frame, bg=PALETTE["pampas"], highlightthickness=0)
        mapping_buttons.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        mapping_buttons.columnconfigure(0, weight=1, uniform="mapping_buttons")
        mapping_buttons.columnconfigure(1, weight=1, uniform="mapping_buttons")
        mapping_buttons.columnconfigure(2, weight=1, uniform="mapping_buttons")
        RoundedButton(mapping_buttons, "新增/更新", self._upsert_mapping, width=120, primary=True).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        RoundedButton(mapping_buttons, "删除选中", self._delete_mapping, width=120).grid(
            row=0, column=1, sticky="ew", padx=(4, 4)
        )
        RoundedButton(mapping_buttons, "清空输入", self._clear_mapping_inputs, width=120).grid(
            row=0, column=2, sticky="ew", padx=(8, 0)
        )
        frame.columnconfigure(0, weight=1)

    def _build_log_frame(self, parent: ttk.Frame, row: int) -> None:
        panel = RoundedPanel(parent, "运行日志")
        panel.grid(row=row, column=0, sticky="nsew")
        frame = panel.content
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            frame,
            height=14,
            wrap="word",
            state="disabled",
            bg=PALETTE["light"],
            fg=PALETTE["dark"],
            insertbackground=PALETTE["dark"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE["light_gray"],
            highlightcolor=PALETTE["orange"],
            padx=12,
            pady=10,
            font=(CJK_FONT, 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.tag_configure("error", foreground=PALETTE["crail"], font=(CJK_FONT, 10, "bold"))
        self.log_text.tag_configure("warn", foreground=PALETTE["orange"])
        self.log_text.tag_configure("info", foreground=PALETTE["dark"])
        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.log_text.yview,
            style="Sage.Vertical.TScrollbar",
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

        RoundedButton(frame, "清空窗口日志", self._clear_logs, width=126).grid(row=1, column=0, sticky="w", pady=(10, 0))

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
        self.api_key_entry.set_show("" if self.show_key_var.get() else "*")

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

    def _on_resize(self, event: tk.Event) -> None:
        if event.widget is not self.root or not hasattr(self, "mapping_tree"):
            return

        size = (event.width, event.height)
        if size == self._last_root_size or size == self._pending_resize_size:
            return
        self._pending_resize_size = size
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(120, self._apply_responsive_columns)

    def _apply_responsive_columns(self) -> None:
        self._resize_after_id = None
        if not self._pending_resize_size:
            return
        event_width, _event_height = self._pending_resize_size
        self._last_root_size = self._pending_resize_size
        self._pending_resize_size = None
        table_width = max(self.mapping_tree.winfo_width(), int(event_width * 0.32), 360)
        source_width = max(170, table_width // 2)
        target_width = max(170, table_width - source_width)
        widths = (source_width, target_width)
        if widths == self._last_column_widths:
            return
        self._last_column_widths = widths
        self.mapping_tree.column("source", width=source_width, stretch=True)
        self.mapping_tree.column("target", width=target_width, stretch=True)

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
        tag = "info"
        if "[ERROR]" in line:
            tag = "error"
        elif "[WARN]" in line or "[WARNING]" in line:
            tag = "warn"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n", tag)
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
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
            self._resize_after_id = None
        if self._save_after_id:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        self.server.stop()
        self.root.destroy()


def run_gui(config_store: ConfigStore, log_bus: LogBus) -> None:
    root = tk.Tk()
    ProxyGui(root, config_store, log_bus)
    root.mainloop()
