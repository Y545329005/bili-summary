import {
  Action,
  ActionPanel,
  Clipboard,
  Detail,
  Toast,
  showToast,
  open,
} from "@raycast/api";
import { useEffect, useState } from "react";
import {
  runBiliSummary,
  isValidBiliInput,
  saveHistory,
  parseMarkdownMeta,
  extractBvid,
} from "./bili-summary";

export default function Command() {
  const [state, setState] = useState<"loading" | "done" | "error">("loading");
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [filePath, setFilePath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function run() {
      const clip = await Clipboard.readText();

      if (!clip || !isValidBiliInput(clip)) {
        setError(
          "剪贴板中没有 B 站视频链接。\n\n请先复制一个 B 站视频链接（BV 号或完整 URL），再使用此命令。"
        );
        setState("error");
        return;
      }

      const bvid = extractBvid(clip);
      if (!bvid) {
        setError(`无法解析 BV 号: ${clip}`);
        setState("error");
        return;
      }

      const toast = await showToast({
        style: Toast.Style.Animated,
        title: "正在总结...",
        message: bvid,
      });

      try {
        const result = await runBiliSummary(clip);
        toast.style = Toast.Style.Success;
        toast.title = "总结完成";
        toast.message = `${result.charCount} 字符`;
        setMarkdown(result.markdown);
        setFilePath(result.filePath);
        setState("done");

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
        setState("error");
      }
    }
    run();
  }, []);

  if (state === "loading") {
    return (
      <Detail
        markdown="# 🤖 正在生成深度总结...\n\n> 提取字幕 → 调用 DeepSeek → 结构化输出\n\n请稍候..."
        isLoading={true}
      />
    );
  }

  if (state === "error" || error) {
    return (
      <Detail
        markdown={`# ❌ 总结失败\n\n\`\`\`\n${error}\n\`\`\``}
        actions={
          <ActionPanel>
            <Action.OpenInBrowser
              title="在浏览器打开 B 站"
              url="https://www.bilibili.com"
            />
          </ActionPanel>
        }
      />
    );
  }

  return (
    <Detail
      markdown={markdown!}
      navigationTitle="总结结果"
      actions={
        <ActionPanel>
          <Action.CopyToClipboard
            title="复制全文 Markdown"
            content={markdown!}
          />
          <Action
            title="在编辑器中打开"
            onAction={() => filePath && open(filePath)}
            shortcut={{ modifiers: ["cmd"], key: "o" }}
          />
        </ActionPanel>
      }
    />
  );
}
