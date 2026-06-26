/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `summarize` command */
  export type Summarize = ExtensionPreferences & {}
  /** Preferences accessible in the `summarize-clipboard` command */
  export type SummarizeClipboard = ExtensionPreferences & {}
  /** Preferences accessible in the `open-history` command */
  export type OpenHistory = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `summarize` command */
  export type Summarize = {
  /** BV 号或 B 站链接（留空自动读取剪贴板） */
  "url": string
}
  /** Arguments passed to the `summarize-clipboard` command */
  export type SummarizeClipboard = {}
  /** Arguments passed to the `open-history` command */
  export type OpenHistory = {}
}

