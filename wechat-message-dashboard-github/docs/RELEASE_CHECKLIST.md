# GitHub 发布前检查清单

- [ ] 运行 `python -m unittest discover -s test -v`。
- [ ] 确认 `config.json`、`output/`、数据库和聊天导出未被跟踪。
- [ ] 运行 `git status --short --ignored` 检查忽略规则。
- [ ] 运行 `git diff --cached` 复核待提交内容。
- [ ] 确定仓库是公开还是私有。第一次发布建议先设为私有。
- [ ] 如果要公开，选择合适的开源许可证并添加 `LICENSE`。
- [ ] 公开前确认所有截图和演示数据均为虚构内容。
