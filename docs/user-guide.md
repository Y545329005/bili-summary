# bili-summary 使用指南

B站视频投资研究总结 —— 一键生成 18 节买方研究笔记，本地知识库 + 飞书同步。

---

## 快速开始

```bash
# 安装（如已安装可跳过）
cd ~/Desktop/cc && pip3 install -e .

# 总结一个视频
bili-summary BV1xx411c7mD

# 启动 Web 知识库
python3 server.py
# → 浏览器打开 http://localhost:8765
```

---

## 三种使用方式

### 方式一：浏览器扩展（最推荐）

在看视频的页面上直接点一下就能总结，最快。

**安装：**
1. Chrome 地址栏输入 `chrome://extensions`
2. 右上角打开「开发者模式」
3. 点击「加载已解压的扩展程序」
4. 选择 `~/Desktop/cc/extension/` 目录
5. 安装完成，扩展栏出现紫色图标

**使用：**
1. 打开任意 B站视频页面
2. 视频标题右侧会出现 `🔬 投资总结` 按钮
3. 点击 → 等待 30-60 秒 → 右侧弹出 18 节分析报告
4. 面板可拖动、可收起、可关闭
5. 切换视频时按钮会自动刷新

**前提：** 需要后台服务运行中（`python3 server.py`）。如果服务未启动，点击按钮会提示启动命令。

---

### 方式二：Web 知识库

用来浏览、搜索、整理所有总结。

**启动：**
```bash
cd ~/Desktop/cc
python3 server.py
```

**功能：**

| 页面 | 路径 | 功能 |
|------|------|------|
| 知识库首页 | `/` | 列表、全文搜索、按评级筛选 |
| 详情页 | `/summary/1` | 完整 Markdown 渲染、编辑标签/评级/笔记 |
| API 文档 | `/docs` | 在线调试所有 API 接口 |

**编辑功能：** 详情页展开「✏️ 编辑标签 / 笔记 / 评级」→ 修改后保存，自动更新数据库。

**HTMX 加持：** 搜索和筛选使用 HTMX 局部刷新，无需整页跳转。

---

### 方式三：CLI / Raycast

命令行和 Raycast 扩展保持可用，总结完成后自动写入知识库。

```bash
# CLI
bili-summary "https://www.bilibili.com/video/BV1xx411c7mD"
bili-summary BV1xx411c7mD -o my_note.md
bili-summary BV1xx411c7mD --model deepseek-chat

# Raycast
# ⌥Space → 输入"总结" → 粘贴链接 → 回车
```

CLI 总结完成后会自动保存到 SQLite 知识库，下次打开 Web UI 即可看到。

---

## 后台自启动（可选）

让 FastAPI 服务开机自启，浏览器扩展随时可用。

创建 `~/Library/LaunchAgents/com.bili-summary.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bili-summary</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/yangqing/Desktop/cc/server.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Users/yangqing/Desktop/cc</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.bili-summary.plist
```

---

## 常见问题

**Q: 浏览器扩展点击没反应？**
A: 确认后台服务已启动：`python3 ~/Desktop/cc/server.py`。服务默认运行在 `127.0.0.1:8765`。

**Q: 总结失败？**
A: 常见原因：
- Cookie 过期：运行 `bili-summary --login` 重新登录
- API Key 未设置：确认 `DEEPSEEK_API_KEY` 环境变量或 `~/.bili-summary/config.json` 中的 `deepseek_api_key`
- 视频无字幕：B站部分视频没有 CC 字幕，无法总结

**Q: 如何查看之前总结的历史？**
A:
- Web UI 首页展示所有历史总结
- Raycast 中使用「Open History」命令
- 所有数据存储在 `~/.bili-summary/knowledge.db`（SQLite）

**Q: 如何切换模型？**
A:
- CLI: `bili-summary BVxxx --model deepseek-chat`
- API: `POST /api/summarize {"url":"BVxxx","model":"deepseek-chat"}`
- 默认 `deepseek-reasoner`，可选 `deepseek-chat`（更快更便宜）
