#!/usr/bin/env bash
# 微信消息看板模块 - 一键启动脚本（Linux/macOS）
# 作用：创建/复用 venv 虚拟环境，运行 run.py 一键生成看板
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. 首次运行创建虚拟环境（仅标准库，无第三方依赖）
if [ ! -d "$ROOT/venv" ]; then
    echo "==> 创建虚拟环境 venv ..."
    python3 -m venv "$ROOT/venv"
fi

# 2. 运行一键脚本，透传额外参数
"$ROOT/venv/bin/python" "$ROOT/run.py" "$@"