# API 端点参考

在线调试：启动服务后访问 `http://localhost:8765/docs`

---

## 端点列表

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/summarize` | 触发总结 `{"url":"BV...","model":"deepseek-reasoner"}` |
| `GET` | `/api/summaries` | 列表 `?search=关键词&tag=AI&rating=A&limit=50` |
| `GET` | `/api/summaries/{id}` | 单篇详情 |
| `PUT` | `/api/summaries/{id}` | 更新标签/笔记/评级 |
| `DELETE` | `/api/summaries/{id}` | 删除 |
| `POST` | `/api/sync/feishu` | 同步到飞书 `{"id": 1}` |
| `GET` | `/api/stats` | 统计信息 |

---

## 示例

### 触发总结

```bash
curl -X POST http://localhost:8765/api/summarize \
  -H "Content-Type: application/json" \
  -d '{"url": "BV1xx411c7mD", "model": "deepseek-reasoner"}'
```

### 搜索总结

```bash
curl "http://localhost:8765/api/summaries?search=储能&rating=A"
```

### 更新标签

```bash
curl -X PUT http://localhost:8765/api/summaries/1 \
  -H "Content-Type: application/json" \
  -d '{"tags": ["AI", "半导体"], "rating": "A"}'
```

### 同步到飞书

```bash
curl -X POST http://localhost:8765/api/sync/feishu \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'
```
