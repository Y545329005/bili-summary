import {
  Action,
  ActionPanel,
  List,
  Icon,
  showToast,
  Toast,
  open,
  Clipboard,
  Detail,
} from "@raycast/api";
import { useEffect, useState } from "react";
import { loadHistory, HistoryEntry } from "./bili-summary";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";

export default function Command() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedMarkdown, setSelectedMarkdown] = useState<string | null>(null);
  const [selectedTitle, setSelectedTitle] = useState<string>("");

  useEffect(() => {
    async function init() {
      const history = await loadHistory();
      setEntries(history);
      setIsLoading(false);
    }
    init();
  }, []);

  async function handleOpen(entry: HistoryEntry) {
    if (existsSync(entry.filePath)) {
      try {
        const content = await readFile(entry.filePath, "utf-8");
        setSelectedMarkdown(content);
        setSelectedTitle(entry.title);
      } catch {
        await showToast({
          style: Toast.Style.Failure,
          title: "读取文件失败",
          message: entry.filePath,
        });
      }
    } else {
      await showToast({
        style: Toast.Style.Failure,
        title: "文件已不存在",
        message: entry.filePath,
      });
    }
  }

  if (selectedMarkdown) {
    return (
      <Detail
        markdown={selectedMarkdown}
        navigationTitle={selectedTitle}
        actions={
          <ActionPanel>
            <Action.CopyToClipboard
              title="复制全文 Markdown"
              content={selectedMarkdown}
            />
            <Action
              title="返回列表"
              icon={Icon.ArrowLeft}
              onAction={() => {
                setSelectedMarkdown(null);
                setSelectedTitle("");
              }}
              shortcut={{ modifiers: ["cmd"], key: "[" }}
            />
          </ActionPanel>
        }
      />
    );
  }

  return (
    <List isLoading={isLoading} searchBarPlaceholder="搜索历史总结...">
      {entries.length === 0 && !isLoading ? (
        <List.EmptyView
          icon={Icon.Document}
          title="暂无历史总结"
          description="使用「总结 B 站视频」命令生成第一篇总结吧"
        />
      ) : (
        entries.map((entry) => (
          <List.Item
            key={`${entry.bvid}-${entry.createdAt}`}
            icon={Icon.Document}
            title={entry.title}
            subtitle={`${entry.owner} · ${entry.duration}`}
            accessories={[
              { text: `${entry.charCount} 字` },
              {
                text: new Date(entry.createdAt).toLocaleDateString("zh-CN", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                }),
              },
            ]}
            actions={
              <ActionPanel>
                <Action
                  title="查看总结"
                  icon={Icon.Eye}
                  onAction={() => handleOpen(entry)}
                />
                <Action
                  title="在编辑器中打开"
                  icon={Icon.Window}
                  onAction={() => open(entry.filePath)}
                  shortcut={{ modifiers: ["cmd"], key: "o" }}
                />
                <Action.CopyToClipboard
                  title="复制 BV 号"
                  content={entry.bvid}
                  icon={Icon.Link}
                  shortcut={{ modifiers: ["cmd"], key: "c" }}
                />
              </ActionPanel>
            }
          />
        ))
      )}
    </List>
  );
}
