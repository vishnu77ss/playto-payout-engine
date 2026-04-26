# Diagrams

Three Excalidraw scenes for the project — the same diagrams you see rendered as Mermaid in `EXPLAINER.md`, but in a format you can edit visually.

| File | What it shows |
|---|---|
| `er-diagram.excalidraw` | Database tables and their relationships |
| `workflow-diagram.excalidraw` | Lifecycle of a payout from request to terminal state |
| `architecture-diagram.excalidraw` | Frontend, backend, Postgres, Redis, Celery worker, Celery beat |

## How to view / edit

1. Open https://excalidraw.com in any browser.
2. Top-left menu → **Open** → pick the `.excalidraw` file.
3. Edit freely, export as PNG/SVG via **Export image** if you want to embed in the README.

## Why two formats (Mermaid + Excalidraw)?

- **Mermaid** (in `EXPLAINER.md`) renders inline on GitHub without any work — reviewers see it immediately.
- **Excalidraw** is here because the brief specifically asked for it, and it is editable. If a reviewer wants to tweak the architecture and re-export, they can.
