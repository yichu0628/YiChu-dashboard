# 变更记录

## [1.0.0] - 2026-09-13

### 新增
- 将微信消息看板整理为可复用模块（个人工作台子模块）。
- 数据层 `src/gen_data.py`：会话分类、待回复分级、24h 新增、主线任务、项目节点、公众号 / 营销号统计。
- 构建层 `src/build_board.py`：数据精简、去除敏感 username、注入模板生成自包含 HTML。
- 一键编排 `run.py` 与配置 `config.json` / `config.example.json`。
- 统一启动脚本 `start_dev.ps1`（Windows）与 `start_dev.sh`（Linux/macOS）。
- 7 Tab 看板前端 `src/board_template.html`：总览 / 待回复 / 工作与项目 / 项目节点与约定 / 个人聊天 / 公众号与通知 / 营销推送。

### 变更
- 移除数据层与构建层中的硬编码路径，改为配置 + 命令行参数驱动。
- 拆分 `gen_data2.py` 为可导入函数（`generate`）与命令行入口，便于编排复用。
