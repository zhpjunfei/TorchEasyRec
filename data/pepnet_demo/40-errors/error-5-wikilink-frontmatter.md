______________________________________________________________________

## date: 2026-06-08 tags: [error, wikilink, frontmatter, batch-edit, obsidian, markdown] status: closed related: \["\[[index]\]"\]

# 错误 5: wikilink/frontmatter 损坏

## 现象

编辑某些文件后, Obsidian 中所有 wikilink 无法跳转, frontmatter 不渲染. 表现为 `[[wikilink]]` 显示为纯文本 `[wikilink]`.

## 触发

2026-06-08, 多次 `edit` 操作更新 MD 文件内容. 涉及 20+ 个文件.

## 根因

1. **Frontmatter `---` 被吞**: edit 在替换字符串时, 匹配到 `---` 行并进行替换, 导致 frontmatter 定界符丢失.
1. **Wikilink 被转义**: 某些 markdown 工具或编辑过程在 `[[` 前自动加 `\` 或 `\\`, 变成 `\[[` → Obsidian 不识别.

## 诊断耗时

约 30min — 先误认为是 Obsidian 插件问题, 后用 grep 确认 `\[` 和 `## date:` 模式才找到根因.

## 修复

全局 Python 脚本: 一次性恢复 frontmatter `---` 定界符 + 去除所有 `\` 转义. 可逆, 不丢数据.

## 预防

- 批量编辑后跑验证: grep 检查 `[` 模式或丢失的 `---`
- 在 Obsidian 中打开确认 frontmatter 渲染
- 避免在 frontmatter 行上做 substring replacement
