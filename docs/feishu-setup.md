# 飞书同步配置

将总结推送到飞书多维表格 + 飞书文档，形成云端知识库。

---

## 配置飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn)，创建企业自建应用
2. 权限配置：
   - `docx:document` — 创建和编辑文档
   - `bitable:app` — 多维表格读写
   - `drive:drive` — 云空间访问（如需知识库）
3. 发布应用并获取 `app_id` 和 `app_secret`
4. 在飞书中创建一个多维表格，获取 `app_token` 和 `table_id`

---

## 配置本地文件

编辑 `~/.bili-summary/config.json`：

```json
{
  "deepseek_api_key": "sk-xxx",
  "feishu": {
    "app_id": "cli_xxx",
    "app_secret": "xxx",
    "bitable_app_token": "xxx",
    "bitable_table_id": "xxx",
    "wiki_folder_token": ""
  }
}
```

- `wiki_folder_token` 可选，填写后文档会创建在指定知识库文件夹中

---

## 同步操作

三种触发方式：
1. **Web UI** — 详情页点击「📤 同步到飞书」按钮
2. **API** — `POST /api/sync/feishu {"id": 1}`
3. **自动**（计划中）— 总结完成后自动同步

同步内容：
- **多维表格**：标题、UP主、时长、BV号、研究评级、投资结论、标签、字数、同步时间
- **飞书文档**：完整 Markdown 内容（自动转换为飞书 Block 格式）

---

## 常见问题

**Q: 飞书同步报错？**
A:
- 确认 `~/.bili-summary/config.json` 中 feishu 字段填写完整
- 确认飞书应用已发布并开通了所需权限
- 确认多维表格已创建且应用有权限访问
