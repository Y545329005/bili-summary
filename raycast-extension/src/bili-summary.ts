import { exec } from "node:child_process";
import { promisify } from "node:util";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join, dirname } from "node:path";

const execAsync = promisify(exec);
const HOME = homedir();
const PROJECT_DIR = join(HOME, "Desktop/cc");
const HISTORY_FILE = join(HOME, ".bili-summary", "history.json");
const CONFIG_FILE = join(HOME, ".bili-summary", "config.json");

/** Try to resolve DEEPSEEK_API_KEY from multiple sources.
 *  Raycast (GUI app) doesn't inherit shell env vars, so we check:
 *  1. process.env (works for terminal-launched Raycast)
 *  2. ~/.bili-summary/config.json
 *  3. Parse ~/.zshrc for the export line
 */
async function resolveApiKey(): Promise<string | null> {
  // 1. Direct env
  if (process.env.DEEPSEEK_API_KEY) return process.env.DEEPSEEK_API_KEY;

  // 2. Config file
  if (existsSync(CONFIG_FILE)) {
    try {
      const raw = await readFile(CONFIG_FILE, "utf-8");
      const cfg = JSON.parse(raw);
      if (cfg.deepseek_api_key) return cfg.deepseek_api_key;
    } catch { /* ignore */ }
  }

  // 3. Parse shell profiles
  for (const rc of [".zshrc", ".zprofile", ".bashrc", ".bash_profile"]) {
    const rcPath = join(HOME, rc);
    if (existsSync(rcPath)) {
      try {
        const raw = await readFile(rcPath, "utf-8");
        const m = raw.match(
          /DEEPSEEK_API_KEY\s*=\s*["']?(sk-[a-zA-Z0-9]+)["']?/
        );
        if (m) return m[1];
      } catch { /* ignore */ }
    }
  }

  return null;
}

export interface SummaryResult {
  markdown: string;
  charCount: number;
  filePath: string;
}

export interface HistoryEntry {
  bvid: string;
  title: string;
  owner: string;
  duration: string;
  createdAt: string;
  filePath: string;
  charCount: number;
}

function resolvePython(): string {
  // Try python3 first, fall back to python
  return "python3";
}

function escapeShell(arg: string): string {
  return `'${arg.replace(/'/g, "'\\''")}'`;
}

/** Run bili-summary CLI and return the output file path + progress logs. */
export async function runBiliSummary(
  url: string,
  outputDir: string = "/tmp"
): Promise<SummaryResult> {
  const outputPath = join(
    outputDir,
    `bili-summary-${Date.now()}.md`
  );

  const python = resolvePython();
  const cmd = `cd ${escapeShell(PROJECT_DIR)} && ${python} -m bili_summary ${escapeShell(url)} -o ${escapeShell(outputPath)} 2>&1`;

  console.log("Running:", cmd);

  try {
    // Resolve API key (Raycast doesn't inherit shell env)
    const apiKey = await resolveApiKey();
    const env: Record<string, string> = { ...process.env as Record<string, string> };
    if (apiKey) {
      env.DEEPSEEK_API_KEY = apiKey;
    }

    const { stdout, stderr } = await execAsync(cmd, {
      timeout: 300_000,
      maxBuffer: 1024 * 1024,
      env,
    });

    const output = (stdout || "") + (stderr || "");
    console.log("CLI output:", output);

    // Read the result file
    if (!existsSync(outputPath)) {
      throw new Error(
        `总结文件未生成: ${outputPath}\n\nCLI 输出:\n${output.slice(-500)}`
      );
    }

    const markdown = await readFile(outputPath, "utf-8");
    return {
      markdown,
      charCount: markdown.length,
      filePath: outputPath,
    };
  } catch (error: any) {
    const msg = error?.stderr || error?.stdout || error?.message || String(error);
    throw new Error(`总结失败:\n${msg.slice(-1000)}`);
  }
}

/** Save a history entry to local JSON file. */
export async function saveHistory(entry: HistoryEntry): Promise<void> {
  const { writeFile, mkdir } = await import("node:fs/promises");
  await mkdir(dirname(HISTORY_FILE), { recursive: true });

  let entries: HistoryEntry[] = [];
  if (existsSync(HISTORY_FILE)) {
    try {
      const raw = await readFile(HISTORY_FILE, "utf-8");
      entries = JSON.parse(raw);
    } catch {
      entries = [];
    }
  }

  // Dedup by bvid
  entries = entries.filter((e) => e.bvid !== entry.bvid);
  entries.unshift(entry);

  // Keep last 100
  entries = entries.slice(0, 100);

  await writeFile(HISTORY_FILE, JSON.stringify(entries, null, 2), "utf-8");
}

/** Load history entries. */
export async function loadHistory(): Promise<HistoryEntry[]> {
  if (!existsSync(HISTORY_FILE)) return [];
  try {
    const raw = await readFile(HISTORY_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

/** Extract BV号 from a B站 URL or raw BV号 string. */
export function extractBvid(input: string): string | null {
  // Already a BV号
  const bvMatch = input.match(/BV[a-zA-Z0-9]{10}/);
  if (bvMatch) return bvMatch[0];

  // Short link
  const shortMatch = input.match(/b23\.tv\/([a-zA-Z0-9]+)/);
  if (shortMatch) return null; // Can't resolve short links without HTTP

  return null;
}

/** Check if a string looks like a valid B站 link or BV号. */
export function isValidBiliInput(input: string): boolean {
  return /BV[a-zA-Z0-9]{10}/.test(input) || /bilibili\.com\/video\//.test(input) || /b23\.tv\//.test(input);
}

/** Parse metadata from markdown header (title, owner, duration, bvid). */
export function parseMarkdownMeta(markdown: string): {
  title: string;
  owner: string;
  bvid: string;
  duration: string;
} {
  const lines = markdown.split("\n");
  const title = lines[0]?.replace(/^#\s*/, "") || "未知标题";
  const metaLine = lines[2] || "";

  const owner = metaLine.match(/\*\*UP主\*\*:\s*(.+?)(?:\s*\||$)/)?.[1] || "未知";
  const bvid = metaLine.match(/BV[a-zA-Z0-9]{10}/)?.[0] || "";
  const duration = metaLine.match(/\*\*时长\*\*:\s*(.+?)(?:\s*\||$)/)?.[1] || "";

  return { title, owner, bvid, duration };
}
