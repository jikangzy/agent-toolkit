# Agent Toolkit

A personal monorepo for reusable agent capabilities, including Skills, MCP servers, orchestration tools, shared schemas, and examples.

## Repository layout

```text
agent-toolkit/
├── skills/       # Reusable agent Skills
├── mcps/         # MCP servers and integrations
├── tools/        # Standalone agent/orchestration tools
├── schemas/      # Shared machine-readable contracts
├── examples/     # End-to-end examples and fixtures
└── docs/         # Architecture and development notes
```

## Current capabilities

### Book Video

The first experiment separates creative planning from deterministic media production:

```text
Book title
   ↓
WorkBuddy / story-producer
   ↓
storyboard.json
   ↓
Codex / video-renderer
   ↓
final.mp4
```

- `skills/book-video/story-producer/`: creates a fact-grounded Chinese short-video storyboard from a book title.
- `skills/book-video/video-renderer/`: consumes a locked storyboard and renders media assets, speech, subtitles, and the final video.
- `schemas/book-video/storyboard.schema.json`: contract between the two stages.
- `examples/book-video/storyboard.example.json`: sample payload for testing.

## Reserved tool space

`tools/` is reserved for standalone runtimes, CLIs, orchestrators, and local services. A future OpenSpec-related tool can live under a path such as:

```text
tools/openspec-agent-orchestrator/
```

No OpenSpec migration is part of the current Book Video experiment.

## Conventions

- Skills own agent behavior and prompt-level workflows.
- MCPs expose reusable external capabilities through MCP protocol.
- Tools are standalone runtimes, CLIs, orchestrators, or local services.
- Schemas define contracts shared across agents/tools.
- Examples should be runnable or directly usable as fixtures.
- Provider-specific media APIs should sit behind adapters so workflows remain vendor-neutral.
