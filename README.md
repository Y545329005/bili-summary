# bili-summary

哔哩哔哩长视频内容总结工具 —— 自动提取字幕，用 DeepSeek 生成结构化 Markdown 总结。

## 快速开始

```bash
# 安装
pip install -e .
playwright install chromium

# 设置 API Key
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"

# 登录 B站
bili-summary --login

# 使用
bili-summary "https://www.bilibili.com/video/BV1xx411c7mD"
```

## 文档

| 文档 | 说明 |
|------|------|
| [使用指南](docs/user-guide.md) | 安装配置、三种使用方式、常见问题 |
| [API 参考](docs/api-reference.md) | 全部 REST API 端点及示例 |
| [飞书同步](docs/feishu-setup.md) | 飞书多维表格 + 文档同步配置 |
| [提示词架构](docs/architecture/prompt-v3-review.md) | System Prompt v3 架构评估与演进 |

## 工作原理

```
B站链接 → 解析BV号 → 获取视频元数据 → 提取CC字幕 → DeepSeek总结 → Markdown输出
```

- 字幕优先级：手动中文字幕 > AI 生成中文字幕 > 其他语言
- 长视频字幕超过 8000 字时自动分块总结
- WBI 签名密钥自动缓存 24 小时

## 依赖

- Python ≥ 3.9
- httpx — HTTP 客户端
- openai — DeepSeek API
- playwright — 浏览器登录（仅 `--login` 时使用）
