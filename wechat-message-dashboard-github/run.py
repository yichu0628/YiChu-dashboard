# -*- coding: utf-8 -*-
"""
一键生成微信消息看板：数据层 -> 构建 -> 自包含 HTML

用法：
    python run.py                    # 读取 config.json
    python run.py --config other.json
    python run.py --db-dir D:/archive --self wxid_xxx --out D:/board.html
"""
import os
import sys
import json
import time
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
sys.path.insert(0, SRC)

from gen_data import generate   # noqa: E402
from build_board import build   # noqa: E402


def load_config(path):
    """读取 JSON 配置（文件不存在时返回空字典）
    @param path: str - 配置文件绝对路径
    @returns dict - 配置字典
    """
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    """解析命令行参数并依次执行数据生成与看板构建
    """
    ap = argparse.ArgumentParser(description="一键生成微信消息看板")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"), help="配置文件路径")
    ap.add_argument("--db-dir", help="微信归档目录（覆盖配置）")
    ap.add_argument("--self", help="本人 wxid（覆盖配置）")
    ap.add_argument("--out", help="最终 HTML 输出路径（覆盖配置）")
    args = ap.parse_args()

    cfg = load_config(args.config)
    db_dir = args.db_dir or cfg.get("db_dir")
    self_wxid = args.self or cfg.get("self")
    if not db_dir or not self_wxid:
        print("缺少必要配置：请设置 db_dir 与 self（参考 config.example.json）")
        sys.exit(1)

    out_dir = os.path.join(HERE, cfg.get("output_dir", "output"))
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "conversations.json")
    out_html = args.out or os.path.join(out_dir, "微信消息看板.html")

    aliases = cfg.get("self_aliases") or []

    t0 = time.time()
    print("==> [1/2] 解析微信归档数据 ...")
    generate(db_dir, self_wxid, json_path, aliases)
    print("\n==> [2/2] 构建看板 HTML ...")
    build(json_path, os.path.join(SRC, "board_template.html"), out_html)
    print(f"\n==> 完成，总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()