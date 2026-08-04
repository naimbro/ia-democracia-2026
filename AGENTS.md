# AGENTS.md

## Project

Standalone course website for **Inteligencia Artificial y Democracia 2026**.

## Tech stack

- Plain HTML with inline CSS.
- No framework, no build step, no package manager.
- Deploys through GitHub Pages from `main`.

## Publishing conventions

- When the user asks to push changes, use the repository's configured `origin`
  and existing Git credentials with standard `git` commands.
- GitHub CLI (`gh`) is not required for a direct `git push`; require it only for
  GitHub-specific operations such as opening or managing pull requests.
- This site deploys from `main`, so a requested direct push may be committed and
  pushed to `origin/main` after checking the diff and staging only in-scope files.

## Editing conventions

- Main page: `index.html`.
- Language: Spanish.
- Keep the existing visual style unless explicitly asked to redesign.
- External links should use `target="_blank"`.
- Do not add build tools, frameworks, or shared CSS unless explicitly requested.

