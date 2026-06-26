import {
  Action,
  ActionPanel,
  Clipboard,
  Detail,
  Form,
  Icon,
  Toast,
  showToast,
  popToRoot,
  open,
} from "@raycast/api";
import { useState } from "react";
import {
  runBiliSummary,
  extractBvid,
  isValidBiliInput,
  saveHistory,
  parseMarkdownMeta,
} from "./bili-summary";

interface CommandProps {
  arguments?: {
    url?: string;
  };
}

export default function Command(props: CommandProps) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filePath, setFilePath] = useState<string | null>(null);

  async function handleSubmit(values: { url: string }) {
    let url = values.url.trim();

    // Read clipboard if empty
    if (!url) {
      const clip = await Clipboard.readText();
      if (clip && isValidBiliInput(clip)) {
        url = clip.trim();
      } else {
        setError("请输入 BV 号或 B 站链接，或先复制一个 B 站视频链接到剪贴板。");
        return;
      }
    }

    const bvid = extractBvid(url);
    if (!bvid) {
      setError(`无法从输入中解析 BV 号: ${url}`);
      return;
    }

    setIsLoading(true);
    setError(null);

    const toast = await showToast({
      style: Toast.Style.Animated,
      title: "正在提取字幕...",
      message: bvid,
    });

    try {
      const result = await runBiliSummary(url);
      toast.style = Toast.Style.Success;
      toast.title = "总结完成";
      toast.message = `${result.charCount} 字符`;
      setMarkdown(result.markdown);
      setFilePath(result.filePath);

      // Save to history
      const meta = parseMarkdownMeta(result.markdown);
      await saveHistory({
        bvid,
        title: meta.title,
        owner: meta.owner,
        duration: meta.duration,
        createdAt: new Date().toISOString(),
        filePath: result.filePath,
        charCount: result.charCount,
      });
    } catch (e: any) {
      toast.style = Toast.Style.Failure;
      toast.title = "总结失败";
      setError(e?.message || String(e));
    } finally {
      setIsLoading(false);
    }
  }

  // ── Error state ──
  if (error) {
    return (
      <Detail
        markdown={`# ❌ 总结失败\n\n\`\`\`\n${error}\n\`\`\``}
        actions={
          <ActionPanel>
            <Action.Push
              title="重试"
              icon={Icon.ArrowClockwise}
              target={<Command />}
            />
          </ActionPanel>
        }
      />
    );
  }

  // ── Loading state ──
  if (isLoading) {
    return (
      <Detail
        markdown="# 🤖 正在生成深度总结...\n\n> 提取字幕 → 调用 DeepSeek → 结构化输出\n\n请稍候，长视频可能需要 30-60 秒。"
        isLoading={true}
      />
    );
  }

  // ── Result state ──
  if (markdown) {
    return (
      <Detail
        markdown={markdown}
        navigationTitle="总结结果"
        actions={
          <ActionPanel>
            <Action.CopyToClipboard
              title="复制全文 Markdown"
              content={markdown}
              icon={Icon.Clipboard}
            />
            <Action
              title="在 Markdown 编辑器中打开"
              icon={Icon.Window}
              onAction={() => filePath && open(filePath)}
              shortcut={{ modifiers: ["cmd"], key: "o" }}
            />
            <Action
              title="复制纯文本（去除格式）"
              icon={Icon.Text}
              onAction={async () => {
                const plainText = markdown.replace(/[#*>\-|`\[\]()]/g, "").replace(/\n{3,}/g, "\n\n");
                await Clipboard.copy(plainText);
                await showToast({ title: "已复制纯文本" });
              }}
            />
            <Action.Push
              title="总结另一个视频"
              icon={Icon.ArrowClockwise}
              target={<Command />}
              shortcut={{ modifiers: ["cmd"], key: "n" }}
            />
          </ActionPanel>
        }
      />
    );
  }

  // ── Input state ──
  return (
    <Form
      actions={
        <ActionPanel>
          <Action.SubmitForm
            title="开始总结"
            icon={Icon.Stars}
            onSubmit={handleSubmit}
          />
          <Action
            title="从剪贴板总结"
            icon={Icon.Clipboard}
            onAction={async () => {
              const clip = await Clipboard.readText();
              if (clip && isValidBiliInput(clip)) {
                await handleSubmit({ url: clip });
              } else {
                setError("剪贴板中没有找到 B 站视频链接。");
              }
            }}
            shortcut={{ modifiers: ["cmd"], key: "return" }}
          />
        </ActionPanel>
      }
    >
      <Form.TextField
        id="url"
        title="B 站链接 / BV 号"
        placeholder="BV1vBjo6hEdL 或 https://www.bilibili.com/video/..."
        autoFocus
        info="留空则自动读取剪贴板中的 B 站链接"
      />
      <Form.Description
        title="快捷键"
        text="⌘↩ 一键从剪贴板读取并总结 | ⌘N 总结另一个 | ⌘O 在编辑器中打开"
      />
    </Form>
  );
}
