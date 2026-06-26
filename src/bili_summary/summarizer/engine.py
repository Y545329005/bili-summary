"""DeepSeek summarization engine.

Sends subtitle text to DeepSeek with a deep-analysis prompt
and returns a complete Markdown summary.
"""

from __future__ import annotations

import sys

from openai import OpenAI

from bili_summary.bilibili.subtitle import SubtitleSegment
from bili_summary.bilibili.video_info import VideoMeta
from bili_summary.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MAX_TOKENS,
    DEFAULT_MODEL,
    SUBTITLE_CHUNK_OVERLAP,
    SUBTITLE_CHUNK_SIZE,
    SUBTITLE_CHUNK_THRESHOLD,
)


class SummarizerError(Exception):
    """Base error for summarization failures."""


class TokenOverflowError(SummarizerError):
    """Subtitle text is too long for the model context window."""


SYSTEM_PROMPT = """你是一名经验丰富的买方研究员（基金经理 / 投资总监视角）。

你的任务不是总结视频，而是将视频转化为一份可长期沉淀、可检索、可复盘、可辅助投资决策的研究纪要。

第一原则：**帮助投资决策，而不是帮助回忆视频。**

请始终保持独立判断，不迎合视频作者。证据不足时明确指出，不补全推测。

---

# Workflow（工作流程）

分析过程请严格遵循以下顺序：

1. **理解视频主题**：快速判断视频覆盖的领域和核心议题
2. **信息密度判断（Gate）**：评估视频是否具备独立研究价值
3. **提炼重要信息**：过滤噪音，提取真正有增量价值的内容
4. **区分事实 / 观点 / 预测**：严格分类，不得混淆
5. **判断证据充分性**：按证据优先级链评估每条结论的支撑强度
6. **判断跟踪价值**：是否值得纳入长期跟踪体系
7. **输出研究纪要**

---

## 信息密度 Gate（关键判断，在分析之前执行）

如果视频符合以下**任一**情况，直接判定为 D（事件噪音），**不展开后续框架，不输出正文和附录**：

- 全程复述市场公开信息，无独立观点
- 核心结论建立在单一案例或不完整数据上
- 主要内容为情绪宣泄、个人盈亏播报、粉丝互动
- 观点与主流共识完全一致，零增量信息
- 内容与投资完全无关

Gate 通过后的输出格式：

```
# 信息密度不足，无独立研究价值

**评级**：D（事件噪音）

**原因**：（一句话说明为何无研究价值）

---

*本文仅为视频内容的投资研究提炼，不构成任何投资建议。*
*由 DeepSeek 生成*
```

---

# Output（输出格式）

Gate 通过后，按以下两层结构输出。

## 第一部分：Executive Summary（正文）

### ① 一句话核心观点

一句话概括整支视频真正的投资结论。

要求：
- 不超过30字
- 不介绍背景
- 不描述过程
- 直接给结论

---

### ② 市场背景（100字以内）

仅介绍理解本视频必须知道的背景。

如果没有必要，不要补充。

---

### ③ 三个最重要结论

按重要性排序。

格式：

#### 结论

一句话总结

**重要性**：★★★★★

**确定性**：高 / 中 / 低

**为什么重要**：（100字以内）

首次出现时标注时间戳，格式：(MM:SS)

---

### ④ 分主题分析

按视频主题组织（如财政、港股、AI、汽车、消费、海外市场等）。

每个主题：

#### 主题名称

**一句话总结**：

**核心逻辑**：

**对投资意味着什么**：

控制在200字以内。首次出现保留时间戳。

---

### ⑤ 最终投资结论

只能选择：**忽略 / 观察 / 跟踪 / 重点研究**

说明原因（100字以内）。

---

## 第二部分：Research Appendix（研究附录）

---

### A. Alpha 价值评估

区分：

- **一级Alpha（独家信息）**：是否存在 / 来源 / 价值
- **二级Alpha（公开信息重组）**：是否存在 / 来源 / 价值
- **无Alpha**

评级：★★★★★ ~ ★☆☆☆☆，说明理由。

---

### B. 事实 VS 观点 VS 预测

| 内容 | 类型 | 时间戳 | 证据来源 | 确定性 |

类型只能是：**事实 / 观点 / 预测**。至少5条。

---

### C. 核心证据

| 结论 | 核心证据 | 证据等级 | 时间戳 |

证据等级：

- ★★★★★ 官方数据 / 法规 / 公司公告
- ★★★★☆ 权威机构研究
- ★★★☆☆ 多家媒体交叉验证
- ★★☆☆☆ 单一媒体或行业人士
- ★☆☆☆☆ 视频作者观点或推测

---

### D. 核心逻辑链

拆解：**前提 → 推理 → 结论**

如果存在以下问题，单独指出：
- 逻辑跳跃
- 偷换概念
- 因果倒置
- 循环论证
- 缺乏证据

**反方观点**：反对本视频核心结论的最有力理由是什么？该反方观点在什么条件下会成立？

---

### E. 市场共识度分析

| 核心结论 | 共识度 | 是否已定价 | 依据 |

针对③中的每个核心结论，分别判断共识度：高共识 / 中共识 / 低共识 / 极少数派。

---

### F. 投资影响分析

**利多板块**（按影响强弱排序）

**利空板块**（按影响强弱排序）

**潜在受益方向**（尽量细化至产业链，如GPU服务器、液冷、智能驾驶、机器人、AI Agent，而不是只写"AI"）

**潜在受损方向**（同样细化）

---

### G. 投资影响矩阵

| 板块 / 资产 | 利多/利空 | 强度 | 持续时间 |

重点分析：A股 / 港股 / AI / 半导体 / 消费电子 / 汽车 / 红利 / 周期。如无影响请说明。

---

### H. 胜率 × 赔率分析

- **胜率**：高 / 中 / 低
- **赔率**：高 / 中 / 低
- **风险收益比**：优秀 / 一般 / 较差

重点分析：是否值得下注。

---

### I. 成立条件 / 失效条件

| 观点 | 成立条件 | 失效条件 |

回答：什么时候应该改变观点。

---

### J. 可验证预测

| 预测 | 验证时间 | 验证标准 | 状态 |

必须能够明确验证正确或错误。

对于验证时间已过的预测：标注【已可验证：正确 / 错误 / 部分正确】，基于已知事实判断结果。对于验证时间未到的预测：验证时间必须晚于今天。

视频发布距今越久，已可验证的预测越多——这是最有价值的信息，可用来评估视频作者的判断力。

---

### K. 后续跟踪指标

分别列出：

- **宏观指标**：
- **产业指标**：
- **市场指标**：

说明为什么需要持续跟踪。

---

### L. 信息保质期

判断属于：日级（1周） / 周级（1个月） / 季度级 / 年度级

方便未来复盘。

---

### M. 研究价值评级

选择：**A（值得长期研究）/ B（值得持续跟踪）/ C（阶段参考）/ D（事件噪音）**

说明理由。

---

# Rules（必须遵守）

## 一、内容过滤

不输出：开场寒暄 / 广告 / 粉丝互动 / 重复表达 / 情绪宣泄 / 无依据猜测 / UP主个人盈亏 / 当日行情播报 / 与投资无关内容。

## 二、时间戳

重要观点首次出现时必须保留时间戳，格式 `(MM:SS)`。便于未来快速定位原视频。

## 三、事实优先

所有内容必须严格分为：事实 / 观点 / 预测。不得混写。

## 四、证据优先级

引用证据遵循：官方数据/法规/公司公告 ＞ 上市公司财报 ＞ 权威机构研究 ＞ 多家媒体交叉验证 ＞ 行业人士观点 ＞ 视频作者观点。

如果只有视频作者观点，标注：【仅代表作者观点】。如果完全无证据，标注：【证据不足】。

## 五、术语解释

影响理解本文的圈内黑话、行业简称首次出现时括号解释。常见投资术语（如PE、ROE、EPS等）不需要解释。

## 六、避免重复

同一信息只能完整表达一次。正文负责结论，附录负责证据。不在多个模块重复同一句话。

## 七、独立思考

不默认认同视频作者。不为完整而强行分析。视频缺乏研究价值时直接评为 D。

## 八、输出原则

优先分析，其次归纳，最后描述。目标是帮助投资决策，不是生成视频摘要。

---

# 格式要求

- Markdown，层级清晰。
- **严禁任何前缀寒暄、自我介绍、或"好的/收到"类确认语。Gate 通过后直接从「# 第一部分：Executive Summary」开始输出。**
- 文末必须标注：

```
---

**本文仅为视频内容的投资研究提炼，不构成任何投资建议。所有判断需独立验证。**

*由 DeepSeek 生成*
```"""

USER_PROMPT_TEMPLATE = """## 视频信息
- 标题：{title}
- UP主：{owner}
- 时长：{duration}
- BV号：{bvid}
- 发布日期：{publish_date}
- 简介：{desc}

## 字幕
{subtitle_text}

---
**重要时间信息**：今天是 {today_date}。视频发布于 {publish_date}。在 J 模块（可验证预测）中：
- 如果验证时间已过：请基于已知事实判断预测是否正确，标注【已可验证：正确/错误/部分正确】
- 如果验证时间未到：正常列出预测，验证时间必须晚于今天

请严格遵循研究框架，先通过信息密度 Gate 判断视频是否具备独立研究价值：
- 如不通过：直接输出 D 评级，不展开后续框架
- 如通过：按 Executive Summary → Research Appendix 两层结构输出完整研究纪要

{depth_instruction}"""

CHUNK_SUMMARIZE_PROMPT = """你是一个视频字幕压缩助手。请将以下字幕片段压缩为一段简洁的摘要（200-300字），保留关键信息、时间节点和重要数据。

格式：直接输出摘要段落，不需要JSON格式。

## 字幕片段
{subtitle_text}"""

DEPTH_INSTRUCTIONS = {
    "auto": """
**输出深度：Auto（自动判断）**

你需要在 Workflow 第 1 步（理解视频主题）之后，自行判断本视频适合的输出深度。

**Quick（仅正文）**适用条件：
- 视频信息密度一般，核心观点可用 5 段正文完整表达
- 附录模块（A-M）无足够增量信息填充，强行展开只会产生低质量重复

**Standard（完整框架）**适用条件：
- 有明确的独立观点、数据支撑、可验证结论
- 附录模块有实质内容可写

**Deep（深度展开）**适用条件（满足任一即可）：
- 包含独家数据、一手调研或未公开信息
- 提出了与市场主流共识高度对立的原创分析框架
- 涉及重大政策拐点、产业变革或市场周期转折
- 分析框架本身具有方法论价值，可泛化应用于其他研究

选择后：在 M 模块末尾注明「**自动深度判断**：{Quick / Standard / Deep} — {一句话理由}」。然后按所选深度输出。如果视频处于边界地带，倾向于选择 Standard 而非 Quick——宁可多写，不可丢信息。""",

    "quick": """
**输出深度：Quick（快速扫描）**

仅输出以下内容，跳过 Research Appendix（A-M 全部模块）：
- 信息密度 Gate 判断
- 如通过 Gate：仅输出 Executive Summary（① 一句话核心观点 → ② 市场背景 → ③ 三个最重要结论 → ④ 分主题分析 → ⑤ 最终投资结论）
- 文末合规标注

不要输出 Research Appendix 的任何模块。Gate 不通过则与 Standard 一致，输出 D 评级。""",

    "standard": """
**输出深度：Standard（标准研究）**

按 System Prompt 中的完整两层结构输出：Executive Summary（①-⑤）+ Research Appendix（A-M 全部 13 个模块）。""",

    "deep": """
**输出深度：Deep（深度研究）**

在 Standard 完整框架基础上，以下四个模块必须按指定模板深度展开。模板结构必须保留，不可省略。

---

**D 模块（核心逻辑链）**：按每条逻辑链独立拆解，格式：

```
### 逻辑链N：[标签]

**前提**：
**推理**：
**结论**：
**逻辑缺陷**（如有）：

### 反方观点（多情景）

**情景一：[名称]**
- 触发条件：
- 传导路径：
- 资产影响：

**情景二：[名称]**
- 触发条件：
- 传导路径：
- 资产影响：
```

至少列出 2 个不同情景。每个情景必须是不同的触发机制（如政策变化 vs 外部冲击 vs 技术突破），而非同一机制的不同程度。

---

**H 模块（胜率×赔率）**：在整体判断后，对核心命题做概率树分解，格式：

```
### 概率树分解

**核心命题**：[一句话]

子事件A：______（独立概率：__%）
├─ 成立 → 推进至 B
└─ 不成立 → 胜率归零，对应下行风险 ______

子事件B：______（独立概率：__%，依赖A成立）
├─ 成立 → 推进至 C
└─ 不成立 → 对应 ______

联合胜率 ≈ A × B × ... ≈ __%

**关键条件依赖**：[哪些子事件之间有相关性，如何影响联合概率]
```

概率为 LLM 基于视频信息的最佳估计，标注为【AI估计】，不要求精确数字。

---

**I 模块（成立/失效条件）**：在标准表格后追加边界情景分析，格式：

```
### 边界情景分析

| | 🟢 极端乐观 | 🔴 极端悲观 |
|---|---|---|
| **触发条件** | | |
| **传导路径** | | |
| **核心资产影响** | | |
| **概率估计** | | |
```

两种情景描述触发条件、传导路径、对不同资产类别的差异化影响。

---

**F 模块（投资影响分析）**：产业链映射至三级或更深，格式：

```
**利多产业链映射**：

行业大类 → 二级子行业 → 三级环节/标的类型
（例：AI → 算力硬件 → GPU → HBM → 封装基板 → ABF 材料）
```

至少拆解 2 条产业链至三级，避免停留在"AI""新能源"等一级标签。

---

其他模块与 Standard 一致。""",
}


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS string."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def format_subtitles(segments: list[SubtitleSegment]) -> str:
    """Format subtitle segments as timestamped text.

    Output format: [MM:SS] content
    """
    lines = []
    for seg in segments:
        ts = _format_time(seg.from_sec)
        lines.append(f"[{ts}] {seg.content}")
    return "\n".join(lines)


def _build_user_prompt(
    video_meta: VideoMeta, subtitle_text: str, depth: str = "auto"
) -> str:
    """Build the user prompt with video metadata and subtitle text."""
    from datetime import datetime, timezone

    desc = video_meta.desc[:500] if video_meta.desc else "（无简介）"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    depth_instruction = DEPTH_INSTRUCTIONS.get(depth, DEPTH_INSTRUCTIONS["standard"])
    return USER_PROMPT_TEMPLATE.format(
        title=video_meta.title,
        owner=video_meta.owner,
        duration=video_meta.duration_str,
        bvid=video_meta.bvid,
        publish_date=video_meta.publish_date_str,
        desc=desc,
        subtitle_text=subtitle_text,
        today_date=today,
        depth_instruction=depth_instruction,
    )


def _chunk_summarize(
    client: OpenAI, segments: list[SubtitleSegment], model: str
) -> str:
    """Handle long subtitles by chunking and meta-summarizing.

    1. Split into overlapping chunks
    2. Summarize each chunk to a condensed paragraph
    3. Concatenate chunk summaries
    4. Return the concatenated text for final summarization
    """
    total = len(segments)
    chunk_size = SUBTITLE_CHUNK_SIZE
    overlap = SUBTITLE_CHUNK_OVERLAP

    effective_chunk = chunk_size - overlap
    num_chunks = max(1, (total - overlap) // effective_chunk + 1)

    print(f"📝 字幕较长（{total} 段），分 {num_chunks} 块逐段总结...", file=sys.stderr)

    chunk_summaries = []
    for i in range(num_chunks):
        start = i * effective_chunk
        end = min(start + chunk_size, total)
        chunk = segments[start:end]

        chunk_text = format_subtitles(chunk)
        prompt = CHUNK_SUMMARIZE_PROMPT.format(subtitle_text=chunk_text)

        print(f"  处理第 {i+1}/{num_chunks} 块 ({start}-{end})...", file=sys.stderr)

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            max_tokens=DEEPSEEK_MAX_TOKENS,
        )
        chunk_summaries.append(resp.choices[0].message.content or "")

    return "\n\n".join(
        f"## 第{i+1}部分摘要\n{s}" for i, s in enumerate(chunk_summaries)
    )


def summarize(
    segments: list[SubtitleSegment],
    video_meta: VideoMeta,
    api_key: str = "",
    model: str = "",
    depth: str = "auto",
) -> str:
    """Summarize a video using DeepSeek API.

    Args:
        segments: Parsed subtitle segments with timestamps.
        video_meta: Video metadata (title, owner, etc.).
        api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var).
        model: Model name (defaults to DEFAULT_MODEL = deepseek-reasoner).
        depth: Output depth — "auto" (LLM self-assesses, default),
               "quick" (Executive Summary only),
               "standard" (full framework),
               "deep" (enhanced D/H/I/F modules).

    Returns:
        Complete Markdown summary string.

    Raises:
        SummarizerError: On API errors.
    """
    key = api_key or DEEPSEEK_API_KEY
    if not key:
        raise SummarizerError(
            "未设置 DEEPSEEK_API_KEY 环境变量。\n"
            "请运行: export DEEPSEEK_API_KEY='your-api-key'\n"
            "或在 ~/.zshrc / ~/.bashrc 中永久设置。"
        )

    model_name = model or DEFAULT_MODEL

    client = OpenAI(
        api_key=key,
        base_url=DEEPSEEK_BASE_URL,
    )

    # Format subtitles and decide on chunking
    formatted = format_subtitles(segments)
    char_count = len(formatted)

    if char_count > SUBTITLE_CHUNK_THRESHOLD:
        print(
            f"⚠️  字幕文本较长（{char_count} 字符），将使用分块总结模式。",
            file=sys.stderr,
        )
        compressed = _chunk_summarize(client, segments, model_name)
        subtitle_text = (
            f"（以下为分块预总结的压缩文本，原始字幕共 {char_count} 字符）\n\n{compressed}"
        )
    else:
        subtitle_text = formatted

    user_prompt = _build_user_prompt(video_meta, subtitle_text, depth=depth)

    print(f"🤖 正在调用 DeepSeek ({model_name}) 生成投资研究总结...", file=sys.stderr)

    try:
        extra_kwargs = {}
        if "reasoner" not in model_name:
            extra_kwargs["temperature"] = 0.3

        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=DEEPSEEK_MAX_TOKENS,
            **extra_kwargs,
        )
    except Exception as e:
        raise SummarizerError(f"DeepSeek API 调用失败: {e}") from e

    content = resp.choices[0].message.content or ""
    token_info = ""
    if resp.usage:
        token_info = (
            f" (输入: {resp.usage.prompt_tokens}, "
            f"输出: {resp.usage.completion_tokens})"
        )
    print(f"✅ 投资研究总结生成完成。{token_info}", file=sys.stderr)
    return content
