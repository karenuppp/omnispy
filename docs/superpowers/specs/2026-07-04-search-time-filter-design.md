# X 搜索时间范围筛选功能

## 问题

`search_x_tweets` 工具缺少时间范围参数。当用户输入"2026年6月关于香港的热帖"时，LLM 无法将时间约束转化为 X 搜索语法，导致查询失败。

具体来说：
- X 搜索原生支持 `since:YYYY-MM-DD until:YYYY-MM-DD` 语法
- 工具函数和 spider 层未暴露对应参数
- Agent prompt 未指导 LLM 如何解析中文日期范围

## 方案

在 `search_x_tweets` 工具新增 `since` / `until` 参数（格式 `YYYY-MM-DD`），spider 层拼装到 X 搜索 URL 中。

### 改动范围

| 文件 | 改动 |
|------|------|
| `spider.py` | `search_tweets()` 新增 `since`/`until` 参数 → `_build_search_query()` 新增时间片 |
| `tools.py` | `search_x_tweets.tool_info` 新增两个参数声明 |
| `x_agent.py` | role prompt 增加中文日期→日期范围的教学示例 |

### 关键逻辑

`_build_search_query()` 新增时间片段：

```
输入: since="2026-06-01", until="2026-06-30"
输出: 香港 since:2026-06-01 until:2026-06-30
```

只传一个参数时（例如只传 `since`），只拼装对应的片段。

### Agent prompt 新增教学

```
"搜索2026年6月关于香港的帖子"
  → search_x_tweets(keywords=["香港"], since="2026-06-01", until="2026-06-30", sort="top")

"搜索最近一周关于AI的帖子"
  → search_x_tweets(keywords=["AI"], since="2026-06-27", sort="latest")
```

### 边界情况

- 非法日期格式：不校验，让 X 搜索自行处理（返回空结果）
- 只有 `since` 没有 `until`：正常拼装，X 返回从该日期至今的结果
- 中文月份解析：LLM 需将"N月"映射到具体月份，prompt 给出示例

### 测试

- `_build_search_query` 新增参数化测试：`since` + `until`、仅 `since`、非法日期
- tool_info 存在性测试：新增两个参数字段
