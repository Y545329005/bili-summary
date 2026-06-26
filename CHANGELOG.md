# Changelog

## [Unreleased]

### Changed — 2026-06-26
- **文档结构重组**：输出文件移入 `output/`，使用指南拆分为 `docs/user-guide.md` + `docs/feishu-setup.md` + `docs/api-reference.md`
- **README 瘦身**：精简为入口页，指向 docs/ 获取详细文档
- **依赖修复**：`pyproject.toml` 补全 `fastapi`、`uvicorn`、`jinja2` 依赖声明
- **隐私保护**：`.claude/` 加入 `.gitignore`，pre-push hook 自动扫描密钥 + CHANGELOG 提醒

### Added — 2026-06-26
- `.gitignore`：忽略输出文件、构建产物、IDE 配置、环境变量
- `CHANGELOG.md`：版本变更记录
- `output/.gitkeep`：输出目录占位
- Git pre-push hook：推送前自动扫描隐私信息 + 提醒更新 CHANGELOG

---

## [0.1.0] — 2025-06-25

### Added
- CLI 工具：B站视频字幕提取 + DeepSeek 结构化总结
- Web 知识库（FastAPI + HTMX）：浏览、搜索、编辑总结
- Chrome 浏览器扩展：视频页面一键总结
- Raycast 扩展：快捷键触发总结
- 飞书同步：多维表格 + 飞书文档
- SQLite 知识库持久化存储
- WBI 签名自动缓存
- System Prompt v3（18 节买方研究框架 + Workflow 7 步）
- Information Density Gate 判断机制
