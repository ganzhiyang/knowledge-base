# Knowledge base

Reusable agent skills distilled from completed projects.

| Skill | Use it for |
| --- | --- |
| [apple-shortcuts](skills/apple-shortcuts/SKILL.md) | Build, repair, sign and distribute Apple Shortcuts; integrate typed automation input and app APIs; validate the shipped artifact. |

Install a skill folder under `~/.codex/skills/` (or your configured Codex skills
directory). Once Codex discovers it, invoke it by name. Example:

```text
Use $apple-shortcuts to create an installable Shortcut for this project.
It should accept shared URLs, connect to my app without pasting a permanent
API key, and queue submissions while offline.
```

The skill is project-independent. Apple Pay is a worked reference, not its only
supported use case. Native signing/inspection requires compatible macOS tools;
JSON/plist inspection and comparison use Python's standard library.
