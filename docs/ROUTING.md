# Routing Model

`_skill-router` is a meta-skill. Its job is to resolve conflicts before Codex loads a business skill.

## Runtime Shape

```text
user request
  -> global instruction or router skill description
  -> read ~/.codex/skills/_skill-router/SKILL.md
  -> choose minimal skill set
  -> load the chosen business skill body
  -> do the work
```

The router is still a skill. It is not a plugin, daemon, hook, or hard security boundary.

## Selection Rules

- Pick one primary skill for the main deliverable.
- Add helper skills only when they are prerequisites.
- Prefer the narrow specialist over an umbrella skill.
- Prefer explicit platforms when the user names a platform.
- Prefer output-format skills when the deliverable is an artifact.
- Prefer process skills when the user asks for coding, debugging, planning, review, or completion discipline.
- Do not default to duplicate, covered, demoted, or weaker skills.

## Examples

| User request | Default route |
|---|---|
| "做一个汇报 PPT" | `ppt-master` |
| "用 Canva 做一版 deck" | `canva-branded-presentation` |
| "打开 localhost 截图看看" | `browser` |
| "gstack 多视口批量 QA" | `gstack-browse` or a narrower gstack QA skill |
| "CI 挂了，修一下" | `gh-fix-ci` |
| "处理 PR review comments" | `gh-address-comments` |
| "新建 Figma 文件" | `figma-create-new-file`, then `figma-use` |
| "这个 bug 怎么修" | `systematic-debugging`, then implementation/TDD as needed |
| "做 HyperFrames 3D 视频" | `hyperframes` plus `three` |
| "处理 PDF 版式" | `pdf` |
| "评估这个 GitHub skill 仓库" | `skill-intake` |

## Updating The Router

When adding a new skill:

1. Run intake.
2. Decide whether it is a default winner, explicit-only skill, fallback, duplicate, or rejected skill.
3. Add one concise rule to `_skill-router/SKILL.md`.
4. Avoid adding every possible trigger word if a narrower platform route is enough.
5. Restart Codex if the skill itself was newly installed.
