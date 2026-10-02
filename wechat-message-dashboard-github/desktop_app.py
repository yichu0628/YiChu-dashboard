# -*- coding: utf-8 -*-
"""微信消息看板 Windows 桌面入口。"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def resource_path(*parts: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root.joinpath(*parts)


SRC = resource_path("src")
sys.path.insert(0, str(SRC))
from build_board import build  # noqa: E402
from gen_data import generate  # noqa: E402


APP_NAME = "微信消息看板"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / APP_NAME


class QueueWriter:
    def __init__(self, messages: queue.Queue):
        self.messages = messages

    def write(self, value: str) -> int:
        if value:
            self.messages.put(("log", value))
        return len(value)

    def flush(self) -> None:
        pass


class BoardApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("780x610")
        self.minsize(680, 540)
        self.messages: queue.Queue = queue.Queue()
        self.last_output: Path | None = None
        cfg = self.load_config()

        self.db_dir = tk.StringVar(value=cfg.get("db_dir", ""))
        self.self_wxid = tk.StringVar(value=cfg.get("self", ""))
        self.aliases = tk.StringVar(value=", ".join(cfg.get("self_aliases", [])))
        self.output_dir = tk.StringVar(value=cfg.get("output_dir", str(DEFAULT_OUTPUT_DIR)))
        self.status = tk.StringVar(value="请选择微信数据库目录并填写本人 wxid")
        self.build_ui()
        self.after(100, self.drain_messages)

    @staticmethod
    def load_config() -> dict:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        root = ttk.Frame(self, padding=24)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text=APP_NAME, font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(root, text="本地读取已解密的微信 SQLite 数据，并生成离线 HTML 看板。原始 wxid 会完整保留。",
                  foreground="#555").pack(anchor="w", pady=(4, 20))

        form = ttk.Frame(root)
        form.pack(fill="x")
        self.add_path_row(form, 0, "数据库目录", self.db_dir, self.choose_db)
        self.add_entry_row(form, 1, "本人 wxid", self.self_wxid)
        self.add_entry_row(form, 2, "本人昵称别名", self.aliases)
        self.add_path_row(form, 3, "输出目录", self.output_dir, self.choose_output)
        ttk.Label(form, text="昵称别名可用逗号分隔，用于识别群聊中的 @我。", foreground="#666").grid(
            row=4, column=1, sticky="w", pady=(0, 12))

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(10, 12))
        self.generate_button = ttk.Button(actions, text="生成看板", command=self.start_generate)
        self.generate_button.pack(side="left")
        ttk.Button(actions, text="打开最近结果", command=self.open_result).pack(side="left", padx=8)
        ttk.Button(actions, text="打开输出目录", command=self.open_output_dir).pack(side="left")

        ttk.Label(root, textvariable=self.status, foreground="#1769aa").pack(anchor="w", pady=(0, 8))
        self.log = tk.Text(root, height=16, wrap="word", font=("Consolas", 10), state="disabled")
        self.log.pack(fill="both", expand=True)
        self.append_log("提示：程序只读取数据库，不会修改微信原始文件。\n")

    @staticmethod
    def add_entry_row(parent, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, width=14).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)
        parent.columnconfigure(1, weight=1)

    def add_path_row(self, parent, row: int, label: str, variable: tk.StringVar, command) -> None:
        self.add_entry_row(parent, row, label, variable)
        ttk.Button(parent, text="浏览…", command=command).grid(row=row, column=2, padx=(8, 0), pady=6)

    def choose_db(self) -> None:
        path = filedialog.askdirectory(title="选择包含 contact.db、message_*.db 的目录")
        if path:
            self.db_dir.set(path)

    def choose_output(self) -> None:
        path = filedialog.askdirectory(title="选择看板输出目录")
        if path:
            self.output_dir.set(path)

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_generate(self) -> None:
        db_dir = Path(self.db_dir.get().strip().strip('"'))
        self_wxid = self.self_wxid.get().strip()
        output_dir = Path(self.output_dir.get().strip().strip('"'))
        if not db_dir.is_dir() or not (db_dir / "contact.db").is_file():
            messagebox.showerror(APP_NAME, "数据库目录无效：应包含 contact.db 和 message_*.db。")
            return
        if not self_wxid:
            messagebox.showerror(APP_NAME, "请填写本人 wxid。")
            return
        aliases = [x.strip() for x in self.aliases.get().replace("，", ",").split(",") if x.strip()]
        cfg = {"db_dir": str(db_dir), "self": self_wxid, "self_aliases": aliases,
               "output_dir": str(output_dir)}
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        self.generate_button.configure(state="disabled")
        self.status.set("正在生成，请稍候…")
        self.append_log("\n开始生成看板…\n")
        threading.Thread(target=self.generate_worker, args=(db_dir, self_wxid, aliases, output_dir), daemon=True).start()

    def generate_worker(self, db_dir: Path, self_wxid: str, aliases: list[str], output_dir: Path) -> None:
        writer = QueueWriter(self.messages)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / "conversations.json"
            html_path = output_dir / "微信消息看板.html"
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                generate(str(db_dir), self_wxid, str(json_path), aliases)
                build(str(json_path), str(SRC / "board_template.html"), str(html_path))
            self.messages.put(("done", str(html_path)))
        except Exception:
            self.messages.put(("error", traceback.format_exc()))

    def drain_messages(self) -> None:
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "log":
                    self.append_log(value)
                elif kind == "done":
                    self.last_output = Path(value)
                    self.generate_button.configure(state="normal")
                    self.status.set("生成完成")
                    self.append_log(f"\n完成：{value}\n")
                    messagebox.showinfo(APP_NAME, "看板已生成。")
                    self.open_result()
                elif kind == "error":
                    self.generate_button.configure(state="normal")
                    self.status.set("生成失败，请查看日志")
                    self.append_log("\n生成失败：\n" + value)
                    messagebox.showerror(APP_NAME, "生成失败，请查看窗口中的详细日志。")
        except queue.Empty:
            pass
        self.after(100, self.drain_messages)

    def open_result(self) -> None:
        target = self.last_output or Path(self.output_dir.get()) / "微信消息看板.html"
        if target.is_file():
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            messagebox.showinfo(APP_NAME, "还没有生成看板。")

    def open_output_dir(self) -> None:
        target = Path(self.output_dir.get())
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)  # type: ignore[attr-defined]


def packaged_self_test() -> int:
    """供构建流程验证打包后的 SQLite 与模板资源。"""
    import sqlite3

    with sqlite3.connect(":memory:") as connection:
        assert connection.execute("SELECT 1").fetchone() == (1,)
    assert (SRC / "board_template.html").is_file()
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(packaged_self_test())
    BoardApp().mainloop()
