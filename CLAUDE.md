# CLAUDE.md

@AGENTS.md

The file above holds the project rules, commands and conventions. This file adds what is specific to working with Claude Code here.

## How to work in this repo

- **Start from the requirement.** Look up the SRD ID in [docs/srd.md](docs/srd.md) before writing code, and check [docs/architecture.md section 10](docs/architecture.md#10-status-by-module) to see whether the backend already has it. The frontend builds on endpoints that exist; backend changes are allowed when a screen needs them, but keep the SRD rule and add tests.
- **New screens follow the design process** in [docs/design.md section 10](docs/design.md#10-designing-a-new-screen): gather Dribbble and Pinterest references, publish a picking board as an artifact, wait for the pick, then build to match the picked references closely in Oweru navy and gold. For Pinterest, use the Chrome extension when it is connected; Dribbble works through Playwright.
- **Check UI in a real browser** at phone width (about 390 px) and desktop, in Swahili and English, before calling it done. Remove screenshots from the repository afterwards.
- **Restart Django after backend edits** when the dev server runs with `--noreload`; it only loads code at start.
- **Report test results honestly.** Some tests need PostgreSQL features (advisory locks, geography area, triggers) and fail on lighter local setups. Run the same tests with your change stashed and report only the difference.

## Local preview (optional)

Some machines have a `config.settings.local_preview` settings file (SpatiaLite, in-memory uploads). It is excluded from git and is not the official setup. If it is missing, use the development settings in AGENTS.md. Preview accounts are local test data only.

## Style

- Replies, docs, commit messages and UI copy: no em dash. Use a comma, colon, parentheses or a full stop.
- No AI attribution in commits or PRs: no `Co-Authored-By` trailer for Claude and no "Generated with Claude Code" line.
