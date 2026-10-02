# 微信消息看板

> 本项目只在本机读取用户自行准备的已解密 SQLite 归档，生成离线 HTML 看板。不包含、不上传任何微信数据。

个人工作台的一个子模块：从微信 4.x 解密归档（SQLite）中提取聊天数据，一键生成自包含的离线看板 HTML。纯 Python 标准库实现，无第三方依赖。

## 仓库边界

本仓库只收录看板源码、测试和说明文档，不收录：

- 真实微信数据库、聊天内容、联系人、微信号或生成的 HTML/CSV/JSON。
- `config.json`、本机路径、虚拟环境、构建目录和安装包。
- 第三方微信数据提取器源码。请用户自行确保数据来源和使用方式合法合规。

详见 [隐私与数据边界](docs/PRIVACY.md)。

## 功能

- 会话自动分类：工作与项目 / 个人聊天 / 公众号与通知 / 营销推送
- 待回复检测与分级：P0（被点名 / 24h 内来信未回）、P1（数日 / 长期未回）
- 24h 新增聊天窗口、主线任务聚合、项目节点与约定提取
- 公众号、营销号统计
- 输出单文件 `output/微信消息看板.html`，双击即可离线浏览

## 目录结构

```
wechat-board/
├── run.py               # 一键编排：数据层 -> 构建
├── config.json          # 本地配置（含归档路径，已 gitignore）
├── config.example.json  # 配置模板
├── start_dev.ps1        # Windows 启动脚本（创建 venv + 运行）
├── start_dev.sh         # Linux/macOS 启动脚本
├── src/
│   ├── gen_data.py      # 数据层：解析归档 -> conversations.json
│   ├── build_board.py   # 构建层：注入模板 -> 自包含 HTML
│   └── board_template.html  # 看板前端模板（7 个 Tab）
├── output/              # 生成产物（conversations.json + 最终 HTML）
└── test/                # 自测用例
```

## 快速开始

1. 复制配置模板并填写归档信息：

   ```
   cp config.example.json config.json
   ```

   `config.json` 字段说明：
   - `db_dir`：微信归档目录（含 `message_0.db`、`contact.db`、`biz_message_0.db` 等）
   - `self`：本人 `wxid`（形如 `wxid_xxxxxxxx`）
   - `self_aliases`：本人昵称别名（用于群聊「@我」点名检测，可选）
   - `output_dir`：产物输出目录，默认 `output`

2. 一键生成：

   - Windows：`.\start_dev.ps1`
   - Linux/macOS：`./start_dev.sh`

   或直接：`python run.py`（可加 `--db-dir` / `--self` / `--out` 覆盖配置）。

3. 打开 `output/微信消息看板.html` 查看结果。

## 测试

```bash
python -m unittest discover -s test -v
```

GitHub Actions 会在每次提交和 Pull Request 时自动运行同一组测试。

## 分步执行（可选）

```
python src/gen_data.py   --db-dir <归档目录> --self <wxid> --out output/conversations.json
python src/build_board.py --src output/conversations.json --tpl src/board_template.html --out output/微信消息看板.html
```

## 数据说明

- 归档数据需为微信 4.x 已解密的 SQLite 结构（可通过 WeChatDataAnalysis 等工具离线导出）。
- 待回复、点名、任务、节点均为启发式推断（归档不含未读 / 草稿等原生状态），结果仅供参考。
- 本地版会在 HTML 和 CSV 中保留会话 `username/wxid` 原始标识，不进行脱敏。生成文件包含敏感聊天信息，请仅保存在可信设备上。

## Windows 单文件版

运行 `build_windows.ps1` 可生成 `dist/微信消息看板.exe`。目标电脑不需要安装 Python：双击 EXE，在图形界面中选择已解密的微信数据库目录、填写本人 wxid，然后点击“生成看板”。配置保存在当前用户的 `%APPDATA%/微信消息看板/config.json`，默认输出到“文档/微信消息看板”。

## 集成到个人工作台

本模块为纯离线批处理，可作为工作台（树莓派 5 + Express + SQLite）的数据前置：
1. Windows 端离线导出微信归档；
2. 将归档目录同步到工作台机器，运行本模块生成 `conversations.json` 与 HTML；
3. 工作台后端读取 `conversations.json` 入库或直接静态托管 HTML。

## 许可说明

当前尚未指定开源许可证。在仓库所有者选定并添加 `LICENSE` 之前，请勿默认代码已获得复制、修改或再分发授权。
